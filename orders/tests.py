from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.models import Category, Product

from .admin import OrderAdmin
from .cart import Cart
from .models import Order


class CartAddResponseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cart-member", email="cart@example.test")
        self.client.force_login(self.user)
        category = Category.objects.create(name="Тестова категорія", slug="test-cart")
        self.product = Product.objects.create(category=category, name="Тестовий товар")
        self.url = reverse("cart_add", args=[self.product.pk])

    def post_json(self, quantity="1", unit="kg"):
        return self.client.post(self.url, {"quantity": quantity, "unit": unit},
                                HTTP_ACCEPT="application/json")

    def test_json_adds_decimal_kilograms(self):
        response = self.post_json("1.25")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cart_count"], 1)
        item = self.client.session[Cart.SESSION_KEY][f"{self.product.pk}_kg"]
        self.assertEqual(Decimal(item["quantity"]), Decimal("1.25"))

    def test_units_are_separate_positions(self):
        self.post_json()
        response = self.post_json(unit="pcs")
        self.assertEqual(response.json()["cart_count"], 2)
        self.assertEqual(len(self.client.session[Cart.SESSION_KEY]), 2)

    def test_repeated_add_increments_quantity_not_position_count(self):
        self.post_json()
        response = self.post_json()
        self.assertEqual(response.json()["cart_count"], 1)
        item = self.client.session[Cart.SESSION_KEY][f"{self.product.pk}_kg"]
        self.assertEqual(Decimal(item["quantity"]), Decimal("2"))

    def test_fractional_pieces_are_rejected(self):
        response = self.post_json("1.5", "pcs")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertFalse(self.client.session.get(Cart.SESSION_KEY))

    def test_cumulative_limit_keeps_previous_quantity(self):
        self.post_json("1000")
        response = self.post_json()
        self.assertEqual(response.status_code, 400)
        item = self.client.session[Cart.SESSION_KEY][f"{self.product.pk}_kg"]
        self.assertEqual(Decimal(item["quantity"]), Decimal("1000"))

    def test_json_message_does_not_reappear_after_navigation(self):
        self.post_json()
        response = self.client.get(reverse("cart_detail"))
        self.assertNotContains(response, "Товар додано до кошика.")

    def test_regular_post_redirects_and_shows_message(self):
        response = self.client.post(self.url, {"quantity": "1", "unit": "kg"}, follow=True)
        self.assertRedirects(response, reverse("cart_detail"))
        self.assertContains(response, "Товар додано до кошика.", count=1)

    def test_regular_invalid_post_redirects(self):
        response = self.client.post(self.url, {"quantity": "1.5", "unit": "pcs"})
        self.assertRedirects(response, reverse("cart_detail"))
        self.assertFalse(self.client.session.get(Cart.SESSION_KEY))

    def test_inactive_product_is_unavailable(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        self.assertEqual(self.post_json().status_code, 404)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_missing_csrf_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, {"quantity": "1", "unit": "kg"},
                               HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 403)

    def test_valid_csrf_is_accepted(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("catalog"))
        response = client.post(self.url, {"quantity": "1", "unit": "kg"},
                               HTTP_ACCEPT="application/json",
                               HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)

    def test_invalid_unit_is_rejected(self):
        self.assertEqual(self.post_json(unit="box").status_code, 400)

    def test_counter_excludes_inactive_cart_items(self):
        self.post_json()
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        other = Product.objects.create(category=self.product.category, name="Інший товар")
        response = self.client.post(reverse("cart_add", args=[other.pk]),
                                    {"quantity": "1", "unit": "kg"},
                                    HTTP_ACCEPT="application/json")
        self.assertEqual(response.json()["cart_count"], 1)


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    DEFAULT_FROM_EMAIL="sender@example.test",
    MANAGER_EMAIL="manager@example.test",
)
class ManagerOrderEmailTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mail-customer", email="customer@example.test", password="Test-email-2026!",
        )
        self.client.force_login(self.user)
        category = Category.objects.create(name="Для перевірки листів", slug="email-test")
        self.product = Product.objects.create(category=category, name="Ковбаса тестова")
        self.other = Product.objects.create(category=category, name="Сосиски тестові")
        self.client.post(reverse("cart_add", args=[self.product.pk]),
                         {"quantity": "1.25", "unit": "kg"}, HTTP_ACCEPT="application/json")
        self.client.post(reverse("cart_add", args=[self.other.pk]),
                         {"quantity": "2", "unit": "pcs"}, HTTP_ACCEPT="application/json")
        self.payload = {
            "full_name": "Тестовий клієнт", "email": "customer@example.test",
            "phone": "+380000000000", "comment": "Тестовий коментар",
        }

    def create_order(self):
        return self.client.post(reverse("order_create"), self.payload)

    def test_sends_one_complete_email_per_recipient_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.create_order()
        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse("order_detail", args=[order.pk]))
        self.assertEqual(len(callbacks), 2)
        self.assertEqual(len(mail.outbox), 2)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["manager@example.test"])
        self.assertEqual(message.from_email, "sender@example.test")
        self.assertEqual(message.reply_to, ["customer@example.test"])
        self.assertIn(f"№{order.customer_number}", message.subject)
        self.assertIn(f"ID {order.pk}", message.subject)
        for text in ("Ковбаса тестова — 1,25 кг", "Сосиски тестові — 2 шт",
                     "customer@example.test", "+380000000000", "Тестовий коментар"):
            self.assertIn(text, message.body)
        self.assertFalse(self.client.session.get(Cart.SESSION_KEY))

    def test_email_is_deferred_until_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.create_order()
            self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(callbacks), 2)
        for callback in callbacks:
            callback()
        self.assertEqual(len(mail.outbox), 2)

    def test_invalid_order_does_not_send_email(self):
        self.payload["phone"] = "wrong"
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.create_order()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_anonymous_user_cannot_create_order_or_email(self):
        self.client.logout()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.create_order()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_resubmitting_empty_cart_does_not_duplicate_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
            self.create_order()
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_email_uses_saved_product_names(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
            self.product.name = "Нова назва товару"
            self.product.save(update_fields=["name"])
        for message in mail.outbox:
            self.assertIn("Ковбаса тестова", message.body)
            self.assertNotIn("Нова назва товару", message.body)

    def test_mail_failure_does_not_lose_order(self):
        with patch("orders.views.EmailMessage.send", side_effect=OSError("QA mail unavailable")):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.create_order()
        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse("order_detail", args=[order.pk]))
        self.assertEqual(order.items.count(), 2)
        self.assertFalse(self.client.session.get(Cart.SESSION_KEY))

    def test_rolled_back_order_does_not_send_email(self):
        with patch("orders.views.OrderItem.full_clean", side_effect=ValidationError("QA rollback")):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertLogs("django.request", level="ERROR"):
                    with self.assertRaises(ValidationError):
                        self.create_order()
        self.assertFalse(Order.objects.exists())
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_viewing_and_editing_status_do_not_resend_manager_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
        order = Order.objects.get(user=self.user)
        self.client.get(reverse("order_detail", args=[order.pk]))
        order.status = Order.Status.PROCESSING
        order.save(update_fields=["status", "updated_at"])
        manager_messages = [message for message in mail.outbox if message.to == ["manager@example.test"]]
        self.assertEqual(len(manager_messages), 1)

    def test_customer_receives_complete_confirmation(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
        order = Order.objects.get(user=self.user)
        confirmations = [message for message in mail.outbox if message.subject.startswith("Вашу заявку")]
        self.assertEqual(len(confirmations), 1)
        message = confirmations[0]
        self.assertEqual(message.to, ["customer@example.test"])
        self.assertEqual(message.from_email, "sender@example.test")
        self.assertEqual(message.reply_to, ["manager@example.test"])
        self.assertEqual(message.subject, f"Вашу заявку №{order.customer_number} створено")
        for text in (
            "Тестовий клієнт", "Статус під час створення: Нова.",
            "Ковбаса тестова — 1,25 кг", "Сосиски тестові — 2 шт",
            "Тестовий коментар", "manager@example.test", "строки виготовлення",
            "http://testserver" + reverse("order_detail", args=[order.pk]),
        ):
            self.assertIn(text, message.body)

    def test_confirmation_uses_email_entered_in_order(self):
        self.payload["email"] = "contact@example.test"
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
        confirmations = [message for message in mail.outbox if message.subject.startswith("Вашу заявку")]
        self.assertEqual(len(confirmations), 1)
        self.assertEqual(confirmations[0].to, ["contact@example.test"])

    def test_confirmation_link_uses_https_for_secure_request(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("order_create"), self.payload, secure=True)
        order = Order.objects.get(user=self.user)
        confirmation = next(message for message in mail.outbox if message.subject.startswith("Вашу заявку"))
        self.assertIn("https://testserver" + reverse("order_detail", args=[order.pk]), confirmation.body)

    def test_confirmation_keeps_initial_status_snapshot(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
            order = Order.objects.get(user=self.user)
            order.status = Order.Status.PROCESSING
            order.save(update_fields=["status", "updated_at"])
        confirmation = next(message for message in mail.outbox if message.subject.startswith("Вашу заявку"))
        self.assertIn("Статус під час створення: Нова.", confirmation.body)
        self.assertNotIn("Статус під час створення: В обробці.", confirmation.body)

    def test_viewing_and_status_change_do_not_repeat_confirmation(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
        order = Order.objects.get(user=self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(reverse("order_detail", args=[order.pk]))
            order.status = Order.Status.PROCESSING
            order.save(update_fields=["status", "updated_at"])
        confirmations = [message for message in mail.outbox if message.subject.startswith("Вашу заявку")]
        updates = [message for message in mail.outbox if message.subject.startswith("Оновлення заявки")]
        self.assertEqual(len(confirmations), 1)
        self.assertEqual(len(updates), 1)
        self.assertEqual(len(mail.outbox), 3)

    def test_manager_failure_does_not_prevent_customer_confirmation(self):
        original_send = mail.EmailMessage.send

        def send_message(message, *args, **kwargs):
            if message.to == ["manager@example.test"]:
                raise OSError("QA manager mailbox unavailable")
            return original_send(message, *args, **kwargs)

        with patch("orders.views.EmailMessage.send", autospec=True, side_effect=send_message):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.create_order()
        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse("order_detail", args=[order.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["customer@example.test"])
        self.assertFalse(self.client.session.get(Cart.SESSION_KEY))

    def test_customer_failure_does_not_lose_order_or_manager_email(self):
        original_send = mail.EmailMessage.send

        def send_message(message, *args, **kwargs):
            if message.to == ["customer@example.test"]:
                raise OSError("QA customer mailbox unavailable")
            return original_send(message, *args, **kwargs)

        with patch("orders.views.EmailMessage.send", autospec=True, side_effect=send_message):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.create_order()
        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse("order_detail", args=[order.pk]))
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["manager@example.test"])
        self.assertFalse(self.client.session.get(Cart.SESSION_KEY))

    @override_settings(MANAGER_EMAIL="customer@example.test")
    def test_same_address_receives_two_different_role_messages(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(message.to == ["customer@example.test"] for message in mail.outbox))
        self.assertEqual(len({message.subject for message in mail.outbox}), 2)
        self.assertEqual(sum(message.subject.startswith("Вашу заявку") for message in mail.outbox), 1)


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    DEFAULT_FROM_EMAIL="sender@example.test",
    MANAGER_EMAIL="manager@example.test",
)
class OrderStatusEmailTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            customer_number=7, full_name="Тестовий клієнт", email="customer@example.test",
            phone="+380000000000",
        )

    def save_status(self, status):
        self.order.status = status
        self.order.save(update_fields=["status", "updated_at"])

    def test_creation_does_not_send_status_email(self):
        self.assertEqual(len(mail.outbox), 0)

    def test_real_changes_send_one_email_each(self):
        for index, status in enumerate((Order.Status.PROCESSING, Order.Status.CONFIRMED,
                                        Order.Status.COMPLETED, Order.Status.CANCELLED), 1):
            with self.subTest(status=status):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    self.save_status(status)
                self.assertEqual(len(callbacks), 1)
                self.assertEqual(len(mail.outbox), index)
                message = mail.outbox[-1]
                self.assertEqual(message.to, ["customer@example.test"])
                self.assertEqual(message.reply_to, ["manager@example.test"])
                self.assertIn("№7", message.subject)
                self.assertIn(status.label, message.body)

    def test_unchanged_status_does_not_send_email(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.order.save()
            self.save_status(Order.Status.NEW)
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_unsaved_status_is_not_notified(self):
        self.order.status = Order.Status.PROCESSING
        self.order.comment = "Оновлено лише коментар"
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.order.save(update_fields=["comment", "updated_at"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)
        self.assertEqual(callbacks, [])

    def test_email_uses_saved_contact_address(self):
        self.order.email = "unsaved@example.test"
        with self.captureOnCommitCallbacks(execute=True):
            self.save_status(Order.Status.PROCESSING)
        self.assertEqual(mail.outbox[0].to, ["customer@example.test"])

    def test_rollback_does_not_send_email(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    self.save_status(Order.Status.CONFIRMED)
                    raise ValueError("QA rollback")
            except ValueError:
                pass
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_single_save_sends_one_email(self):
        request = RequestFactory().post("/admin/orders/order/")
        self.order.status = Order.Status.CONFIRMED
        with self.captureOnCommitCallbacks(execute=True):
            OrderAdmin(Order, admin.site).save_model(request, self.order, form=None, change=True)
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_bulk_action_sends_once_per_changed_order(self):
        other = Order.objects.create(
            customer_number=8, full_name="Інший клієнт", email="other@example.test",
            phone="+380000000000",
        )
        request = RequestFactory().post("/admin/orders/order/")
        request.session = {}
        request._messages = FallbackStorage(request)
        queryset = Order.objects.filter(pk__in=[self.order.pk, other.pk])
        model_admin = OrderAdmin(Order, admin.site)
        with self.captureOnCommitCallbacks(execute=True):
            model_admin.mark_confirmed(request, queryset)
            model_admin.mark_confirmed(request, queryset)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({message.to[0] for message in mail.outbox},
                         {"customer@example.test", "other@example.test"})

    def test_repeated_ready_does_not_duplicate_receivers(self):
        config = apps.get_app_config("orders")
        config.ready()
        config.ready()
        with self.captureOnCommitCallbacks(execute=True):
            self.save_status(Order.Status.PROCESSING)
        self.assertEqual(len(mail.outbox), 1)

    def test_mail_failure_keeps_status_change(self):
        with patch("orders.apps.EmailMessage.send", side_effect=OSError("QA mail unavailable")):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    self.save_status(Order.Status.CONFIRMED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_deferred_emails_keep_each_status_snapshot(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.save_status(Order.Status.PROCESSING)
            self.save_status(Order.Status.CONFIRMED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(callbacks), 2)
        for callback in callbacks:
            callback()
        self.assertIn("В обробці", mail.outbox[0].subject)
        self.assertIn("Погоджена", mail.outbox[1].subject)

    def test_raw_fixture_save_does_not_send_email(self):
        self.order.status = Order.Status.PROCESSING
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.order.save_base(raw=True, update_fields=["status"])
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    DEFAULT_FROM_EMAIL="sender@example.test",
    MANAGER_EMAIL="manager@example.test",
)
class OrderCancellationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="cancel-owner", email="owner@example.test")
        self.other = get_user_model().objects.create_user(username="cancel-other", email="other@example.test")
        self.order = Order.objects.create(
            user=self.owner, customer_number=3, full_name="Тестовий клієнт",
            email="owner@example.test", phone="+380000000000",
        )
        self.url = reverse("order_cancel", args=[self.order.pk])
        self.detail_url = reverse("order_detail", args=[self.order.pk])
        self.client.force_login(self.owner)

    def test_owner_can_cancel_new_order_and_receives_one_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url)
        self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.order.customer_number, 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.test"])
        self.assertIn("Скасована", mail.outbox[0].body)
        self.assertContains(self.client.get(self.detail_url), "Заявку №3 скасовано.")

    def test_get_does_not_cancel_order(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)

    def test_anonymous_request_redirects_to_login(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)

    def test_another_user_gets_404(self):
        self.client.force_login(self.other)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)
        self.assertEqual(callbacks, [])

    def test_non_new_statuses_are_not_cancelled(self):
        for status in (Order.Status.PROCESSING, Order.Status.CONFIRMED,
                       Order.Status.COMPLETED, Order.Status.CANCELLED):
            with self.subTest(status=status):
                Order.objects.filter(pk=self.order.pk).update(status=status)
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    response = self.client.post(self.url)
                self.assertRedirects(response, self.detail_url)
                self.order.refresh_from_db()
                self.assertEqual(self.order.status, status)
                self.assertEqual(callbacks, [])

    def test_repeated_post_does_not_repeat_status_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url)
            self.client.post(self.url)
        self.assertEqual(len(mail.outbox), 1)

    def test_button_is_shown_only_for_new_order(self):
        action = f'action="{self.url}"'
        self.assertContains(self.client.get(self.detail_url), action)
        for status in (Order.Status.PROCESSING, Order.Status.CONFIRMED,
                       Order.Status.COMPLETED, Order.Status.CANCELLED):
            Order.objects.filter(pk=self.order.pk).update(status=status)
            self.assertNotContains(self.client.get(self.detail_url), action)

    def test_missing_csrf_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)

    def test_valid_csrf_allows_cancellation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        client.get(self.detail_url)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(self.url, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertRedirects(response, self.detail_url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_foreign_order_detail_is_also_404(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)

    def test_cancellation_keeps_order_items(self):
        item = self.order.items.create(product_name="Збережена назва", quantity="2", unit="pcs")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url)
        item.refresh_from_db()
        self.assertEqual(item.product_name, "Збережена назва")
        self.assertEqual(item.quantity, Decimal("2"))
        self.assertEqual(item.order_id, self.order.pk)

    def test_stale_page_cannot_cancel_processing_order(self):
        self.assertContains(self.client.get(self.detail_url), f'action="{self.url}"')
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.PROCESSING)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.client.post(self.url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(callbacks, [])

    def test_mail_failure_does_not_prevent_cancellation(self):
        with patch("orders.apps.EmailMessage.send", side_effect=OSError("QA mail unavailable")):
            with self.assertLogs(level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.url)
        self.assertRedirects(response, self.detail_url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
