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
        response = client.post(self.url, {"quantity": "1", "unit": "kg"},
                               HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 403)

    def test_valid_csrf_is_accepted(self):
        client = Client(enforce_csrf_checks=True)
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

    def test_sends_one_complete_email_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.create_order()
        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse("order_detail", args=[order.pk]))
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 1)
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
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(len(mail.outbox), 1)

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
        self.assertEqual(len(mail.outbox), 1)

    def test_email_uses_saved_product_names(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
            self.product.name = "Нова назва товару"
            self.product.save(update_fields=["name"])
        self.assertIn("Ковбаса тестова", mail.outbox[0].body)
        self.assertNotIn("Нова назва товару", mail.outbox[0].body)

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
