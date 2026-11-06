from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from .models import Category, Favorite, Product


class FavoriteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="favorite@example.test", email="favorite@example.test",
            password="Favorite-test-only-2026!",
        )
        cls.other_user = get_user_model().objects.create_user(
            username="other@example.test", email="other@example.test",
            password="Other-favorite-test-2026!",
        )
        category = Category.objects.create(name="Тестова категорія", slug="favorite-tests")
        cls.product = Product.objects.create(name='Тестовий товар "Родинний"', category=category)
        cls.inactive = Product.objects.create(name="Прихований товар", category=category, is_active=False)

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("toggle_favorite", args=[self.product.pk])

    def post_json(self, action="add"):
        return self.client.post(self.url, {"favorite_action": action}, HTTP_ACCEPT="application/json")

    def test_json_add_and_remove_return_actual_state(self):
        response = self.post_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product_id"], self.product.pk)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(response.json()["is_favorite"])
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.product).exists())
        response = self.post_json("remove")
        self.assertFalse(response.json()["is_favorite"])
        self.assertFalse(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_explicit_retries_do_not_toggle_or_duplicate_favorite(self):
        for unused in range(2):
            self.assertTrue(self.post_json("add").json()["is_favorite"])
        self.assertEqual(Favorite.objects.filter(user=self.user, product=self.product).count(), 1)
        for unused in range(2):
            self.assertFalse(self.post_json("remove").json()["is_favorite"])
        self.assertFalse(Favorite.objects.exists())

    def test_changes_are_limited_to_current_user(self):
        Favorite.objects.create(user=self.other_user, product=self.product)
        self.post_json("add")
        self.post_json("remove")
        self.assertTrue(Favorite.objects.filter(user=self.other_user, product=self.product).exists())
        self.assertFalse(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_json_does_not_queue_duplicate_messages_for_next_page(self):
        response = self.post_json()
        self.assertEqual(list(get_messages(response.wsgi_request)), [])
        self.assertNotIn("messages", response.cookies)

    def test_plain_post_keeps_toggle_and_redirect_behavior(self):
        target = reverse("catalog") + "?q=Тестовий&page=2"
        response = self.client.post(self.url, {"next": target})
        self.assertRedirects(response, target, fetch_redirect_response=False)
        self.assertTrue(Favorite.objects.filter(user=self.user).exists())
        self.assertEqual(str(list(get_messages(response.wsgi_request))[0]), "Товар додано до обраного ❤️")
        response = self.client.post(self.url, {"next": reverse("favorites")})
        self.assertRedirects(response, reverse("favorites"))
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())

    def test_plain_post_rejects_external_next(self):
        for target in ("https://outside.example/", "//outside.example/"):
            with self.subTest(target=target):
                response = self.client.post(self.url, {"next": target})
                self.assertRedirects(response, reverse("catalog"), fetch_redirect_response=False)

    def test_json_without_explicit_action_keeps_legacy_toggle(self):
        first = self.client.post(self.url, HTTP_ACCEPT="application/json")
        second = self.client.post(self.url, HTTP_ACCEPT="application/json")
        self.assertTrue(first.json()["is_favorite"])
        self.assertFalse(second.json()["is_favorite"])

    def test_invalid_action_does_not_change_favorites(self):
        response = self.post_json("unexpected")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertFalse(Favorite.objects.exists())

    def test_inactive_and_unknown_products_return_404(self):
        for pk in (self.inactive.pk, self.inactive.pk + 10000):
            with self.subTest(pk=pk):
                response = self.client.post(reverse("toggle_favorite", args=[pk]), HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, 404)
        self.assertFalse(Favorite.objects.exists())

    def test_get_cannot_change_favorites(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(Favorite.objects.exists())

    def test_guest_json_is_rejected_without_mutation(self):
        self.client.logout()
        response = self.post_json()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Favorite.objects.exists())

    def test_inactive_user_json_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.post_json()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Favorite.objects.exists())

    def test_csrf_is_required_and_valid_token_is_accepted(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, {"favorite_action": "add"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Favorite.objects.exists())
        client.get(reverse("product_detail", args=[self.product.pk]))
        token = client.cookies["csrftoken"].value
        response = client.post(self.url, {"favorite_action": "add"},
                               HTTP_ACCEPT="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_favorite"])

    def test_templates_expose_state_and_render_favorites_empty_state(self):
        catalog = self.client.get(reverse("catalog"))
        self.assertContains(catalog, 'data-favorite-form')
        self.assertContains(catalog, 'aria-pressed="false"')
        self.post_json()
        detail = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertContains(detail, 'aria-pressed="true"')
        self.assertContains(detail, "data-favorite-label")
        favorites = self.client.get(reverse("favorites"))
        self.assertContains(favorites, "data-favorite-card")
        self.assertContains(favorites, "data-favorites-empty hidden")
        self.post_json("remove")
        empty = self.client.get(reverse("favorites"))
        self.assertContains(empty, "Поки що немає обраних товарів")
        self.assertNotContains(empty, "data-favorite-card")
        self.assertNotContains(empty, "data-favorites-empty hidden")
