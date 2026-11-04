from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import authenticate, get_user_model
from django.core.files.storage import storages
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Category, Product


class PrivateAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="member@example.test", email="member@example.test", password="Private-pass-2026!",
        )
        category = Category.objects.create(name="Приватна категорія", slug="private")
        self.product = Product.objects.create(name="Приватний товар", category=category)

    def test_guest_cannot_open_any_site_section(self):
        paths = ["/", "/about/", "/contacts/", "/catalog/", "/account/", "/cart/",
                 reverse("product_detail", args=[self.product.pk]), "/orders/create/", "/admin/"]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login") + "?next="))
                self.assertNotIn("Приватний товар", response.content.decode())

    def test_login_is_standalone_without_site_navigation(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Вітаємо!")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'class="main-navigation"')
        self.assertNotContains(response, 'class="site-footer"')
        self.assertNotContains(response, 'class="cart-link"')

    def test_registration_and_admin_login_remain_available(self):
        self.assertEqual(self.client.get(reverse("register")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:login")).status_code, 200)

    def test_guest_json_post_is_rejected_without_changing_cart(self):
        response = self.client.post(reverse("cart_add", args=[self.product.pk]),
                                    {"quantity": "1", "unit": "kg"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["ok"])
        self.assertNotIn("cart", self.client.session)

    def test_registration_creates_inactive_user_and_profile_without_login(self):
        response = self.client.post(reverse("register"), {
            "first_name": "Новий", "last_name": "Клієнт", "email": "new@example.test",
            "password1": "New-private-pass-2026!", "password2": "New-private-pass-2026!",
            "privacy_acknowledged": "on",
        })
        self.assertRedirects(response, reverse("login"))
        pending = get_user_model().objects.get(email="new@example.test")
        self.assertFalse(pending.is_active)
        self.assertTrue(hasattr(pending, "profile"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertIsNone(authenticate(username=pending.email, password="New-private-pass-2026!"))

    def test_pending_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(reverse("login"), {"username": self.user.email, "password": "Private-pass-2026!"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "дочекайтеся схвалення")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_one_email_login_opens_account_and_the_whole_site(self):
        response = self.client.post(reverse("login"), {"username": "MEMBER@example.test", "password": "Private-pass-2026!"})
        self.assertRedirects(response, reverse("account"))
        for path in ("/", "/catalog/", "/about/", "/contacts/", "/privacy/", "/account/", "/cart/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_disabling_account_revokes_existing_session(self):
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/catalog/").status_code, 302)

    def test_logout_closes_site_again(self):
        self.client.force_login(self.user)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get("/catalog/").status_code, 302)

    def test_external_next_url_is_not_followed(self):
        response = self.client.post(reverse("login"), {
            "username": self.user.email, "password": "Private-pass-2026!", "next": "https://outside.example/",
        })
        self.assertRedirects(response, reverse("account"))

    def test_admin_approval_allows_email_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        staff = get_user_model().objects.create_superuser("owner", "owner@example.test", "Owner-pass-2026!")
        self.client.force_login(staff)
        response = self.client.post(reverse("admin:auth_user_changelist"), {
            "action": "approve_access", "_selected_action": [self.user.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNotNone(authenticate(username=self.user.email, password="Private-pass-2026!"))

    def test_normal_user_cannot_approve_access(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("admin:auth_user_changelist"), {
            "action": "approve_access", "_selected_action": [self.user.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_private_pages_and_redirects_are_not_cached(self):
        self.assertIn("no-store", self.client.get("/catalog/").headers["Cache-Control"])
        self.client.force_login(self.user)
        response = self.client.get("/catalog/")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("private", response.headers["Cache-Control"])

    def test_invalid_registration_does_not_create_user(self):
        response = self.client.post(reverse("register"), {"email": "bad"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_registration_cannot_set_active_or_staff_flags(self):
        self.client.post(reverse("register"), {
            "first_name": "Новий", "last_name": "Клієнт", "email": "flags@example.test",
            "password1": "New-private-pass-2026!", "password2": "New-private-pass-2026!",
            "privacy_acknowledged": "on",
            "is_active": "True", "is_staff": "True", "is_superuser": "True",
        })
        pending = get_user_model().objects.get(email="flags@example.test")
        self.assertFalse(pending.is_active)
        self.assertFalse(pending.is_staff)
        self.assertFalse(pending.is_superuser)

    def test_login_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("login"), {"username": self.user.email, "password": "Private-pass-2026!"})
        self.assertEqual(response.status_code, 403)

    def test_public_design_assets_work_but_static_content_images_are_closed(self):
        for relative in ("css/style.css", "js/main.js", "images/logo.png", "images/icons.svg"):
            response = self.client.get(storages["staticfiles"].url(relative))
            self.assertEqual(response.status_code, 200, relative)
            response.close()
        for relative in ("images/production-1.jpg", "images/heritage-banner.webp"):
            response = self.client.get(storages["staticfiles"].url(relative))
            self.assertEqual(response.status_code, 302, relative)

    @override_settings(DEBUG=False)
    def test_content_images_are_closed_with_debug_false_too(self):
        url = storages["staticfiles"].url("images/production-1.jpg")
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_approved_user_can_open_static_content_image(self):
        self.client.force_login(self.user)
        response = self.client.get(storages["staticfiles"].url("images/production-1.jpg"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        response.close()

    def test_private_media_requires_login_in_both_debug_modes(self):
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            (Path(folder) / "photo.jpg").write_bytes(b"private photo")
            for debug in (True, False):
                with self.subTest(debug=debug), override_settings(DEBUG=debug):
                    self.assertEqual(self.client.get("/media/photo.jpg").status_code, 302)
                    self.client.force_login(self.user)
                    response = self.client.get("/media/photo.jpg")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b"".join(response.streaming_content), b"private photo")
                    self.assertIn("no-store", response.headers["Cache-Control"])
                    response.close()
                    self.client.logout()

    def test_media_directory_and_path_traversal_are_not_served(self):
        self.client.force_login(self.user)
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            self.assertEqual(self.client.get("/media/").status_code, 404)
            self.assertEqual(self.client.get("/media/../config/settings.py").status_code, 404)

    def test_guest_unknown_url_does_not_reveal_a_private_error_page(self):
        response = self.client.get("/unknown-private-page/")
        self.assertEqual(response.status_code, 302)


class PrivacyRegistrationTests(TestCase):
    def registration_data(self):
        return {
            "first_name": "Тестовий",
            "last_name": "Клієнт",
            "email": "privacy@example.test",
            "password1": "Privacy-private-pass-2026!",
            "password2": "Privacy-private-pass-2026!",
            "privacy_acknowledged": "on",
        }

    def test_guest_can_read_full_policy_without_private_navigation(self):
        response = self.client.get(reverse("privacy"))
        self.assertContains(response, "Водоп’янов Андрій Миколайович")
        self.assertContains(response, "04 листопада 2026 року")
        self.assertContains(response, "rkcvk.rozdilna@gmail.com")
        self.assertContains(response, "Google Fonts")
        self.assertContains(response, "jsDelivr")
        for section in range(1, 13):
            self.assertContains(response, f'id="policy-section-{section}"')
        self.assertContains(response, f'href="{reverse("register")}"')
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertNotContains(response, 'class="main-navigation"')
        self.assertNotContains(response, 'class="cart-link"')
        self.assertNotContains(response, "fonts.googleapis.com")
        self.assertNotContains(response, "cdn.jsdelivr.net")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_approved_user_reads_policy_inside_site(self):
        user = get_user_model().objects.create_user(
            username="reader@example.test", email="reader@example.test",
            password="Reader-private-pass-2026!",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("privacy"))
        self.assertContains(response, 'class="site-header"')
        self.assertContains(response, 'id="policy-section-12"')

    def test_registration_checkbox_is_required_unchecked_and_links_to_policy(self):
        response = self.client.get(reverse("register"))
        field = response.context["form"]["privacy_acknowledged"]
        self.assertTrue(field.field.required)
        self.assertFalse(field.value())
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'for="id_privacy_acknowledged"')
        self.assertContains(response, f'href="{reverse("privacy")}" target="_blank"')
        self.assertContains(response, "Підтверджую ознайомлення")

    def test_server_rejects_registration_without_acknowledgment(self):
        from .models import Profile

        for value in (None, "False", ""):
            with self.subTest(value=value):
                data = self.registration_data()
                if value is None:
                    del data["privacy_acknowledged"]
                else:
                    data["privacy_acknowledged"] = value
                response = self.client.post(reverse("register"), data)
                self.assertEqual(response.status_code, 200)
                self.assertFormError(
                    response.context["form"], "privacy_acknowledged",
                    "Ознайомтеся з політикою та підтвердьте це галочкою.",
                )
                self.assertFalse(get_user_model().objects.exists())
                self.assertFalse(Profile.objects.exists())
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_acknowledgment_creates_pending_account_without_login(self):
        response = self.client.post(reverse("register"), self.registration_data())
        self.assertRedirects(response, reverse("login"))
        user = get_user_model().objects.get(email="privacy@example.test")
        self.assertFalse(user.is_active)
        self.assertTrue(hasattr(user, "profile"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.get(reverse("privacy"))
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(self.client.get(reverse("catalog")).status_code, 302)

    def test_policy_exception_does_not_open_other_paths(self):
        self.assertEqual(self.client.get(reverse("privacy")).status_code, 200)
        for path in ("/privacy/anything/", "/catalog/", "/account/", "/media/photo.jpg"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)

    def test_login_page_also_links_to_public_policy(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, f'href="{reverse("privacy")}"')
