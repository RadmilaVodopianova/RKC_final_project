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


class CatalogSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="search@example.test", email="search@example.test",
            password="Search-test-only-2026!",
        )
        cls.category = Category.objects.create(name="Варені", slug="search-vareni")
        cls.other_category = Category.objects.create(name="Копченості", slug="search-kopchenosti")
        cls.product = Product.objects.create(name="Брестська 1с.вар.", category=cls.category)
        cls.lowercase = Product.objects.create(name="ковбаса домашня", category=cls.category)
        cls.ukrainian = Product.objects.create(
            name="Їжак Єгерська Ґаздівська Індича", category=cls.category,
        )
        cls.other = Product.objects.create(name="Брестська копчена", category=cls.other_category)
        cls.inactive = Product.objects.create(
            name="БРЕСТ прихована", category=cls.category, is_active=False,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("catalog")

    def search(self, query, **parameters):
        response = self.client.get(self.url, {"q": query, **parameters})
        self.assertEqual(response.status_code, 200)
        return response

    def test_cyrillic_search_ignores_letter_case(self):
        for query in ("Брест", "брест", "БРЕСТ", "бРеСт"):
            with self.subTest(query=query):
                response = self.search(query)
                self.assertEqual(
                    {product.pk for product in response.context["products"]},
                    {self.product.pk, self.other.pk},
                )

    def test_uppercase_query_matches_lowercase_stored_name(self):
        response = self.search("ДОМАШНЯ")
        self.assertEqual([product.pk for product in response.context["products"]], [self.lowercase.pk])

    def test_ukrainian_specific_letters_match_in_both_cases(self):
        for query in ("їжак", "ЇЖАК", "єгерська", "ЄГЕРСЬКА", "ґаздівська", "ҐАЗДІВСЬКА", "індича", "ІНДИЧА"):
            with self.subTest(query=query):
                response = self.search(query)
                self.assertEqual([product.pk for product in response.context["products"]], [self.ukrainian.pk])

    def test_special_characters_are_literal_search_text(self):
        for query in (".", "[", "(", "+", "*", "%", "_", "?", "|", "^", "$", chr(92), "x.*y"):
            with self.subTest(query=query):
                product = Product.objects.create(name="Тест " + query + " буквальний", category=self.category)
                response = self.search(query)
                expected = {
                    item.pk for item in Product.objects.filter(is_active=True)
                    if query.casefold() in item.name.casefold()
                }
                self.assertEqual({item.pk for item in response.context["products"]}, expected)
                product.delete()

    def test_search_keeps_category_and_excludes_inactive_products(self):
        response = self.search("брест", category=self.category.slug)
        self.assertEqual([product.pk for product in response.context["products"]], [self.product.pk])
        self.assertEqual(response.context["selected_category"], self.category.slug)

    def test_search_trims_whitespace_and_returns_no_unrelated_products(self):
        response = self.search("  бРеСт  ", category=self.category.slug)
        self.assertEqual(response.context["query"], "бРеСт")
        self.assertEqual([product.pk for product in response.context["products"]], [self.product.pk])
        self.assertEqual(self.search("неіснуючий товар").context["page_obj"].paginator.count, 0)

    def test_empty_query_shows_active_products(self):
        response = self.search("   ")
        self.assertEqual(response.context["page_obj"].paginator.count, 4)

    def test_search_preserves_pagination_links_and_favorite_state(self):
        Product.objects.bulk_create([
            Product(name=f"Пошуковий {number:02}", category=self.category)
            for number in range(25)
        ])
        Favorite.objects.create(user=self.user, product=self.product)
        response = self.search("брест", category=self.category.slug)
        self.assertIn(self.product.pk, response.context["favorite_product_ids"])
        first = self.search("ПОШУКОВИЙ", category=self.category.slug)
        self.assertEqual(first.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(first.context["products"]), 24)
        from urllib.parse import parse_qs, urlsplit
        from html.parser import HTMLParser

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.urls.extend(value for name, value in attrs if name == "href")

        links = Links()
        links.feed(first.content.decode())
        pages = [parse_qs(urlsplit(url).query) for url in links.urls]
        self.assertIn(
            {"q": ["ПОШУКОВИЙ"], "category": [self.category.slug], "page": ["2"]},
            pages,
        )
        second = self.search("ПОШУКОВИЙ", category=self.category.slug, page=2)
        self.assertEqual(len(second.context["products"]), 1)
        self.assertFalse(
            {item.pk for item in first.context["products"]}
            & {item.pk for item in second.context["products"]}
        )
