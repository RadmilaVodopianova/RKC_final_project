from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from core.models import Category, Product

from .cart import Cart


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
