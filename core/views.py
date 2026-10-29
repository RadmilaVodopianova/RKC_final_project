from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ContactMessageForm
from .models import Category, Favorite, Product


# =========================
# ГЛАВНАЯ СТРАНИЦА
# =========================

def home(request):
    category_previews = (
        Product.objects.filter(is_active=True)
        .exclude(image="")
        .only("id", "category_id", "image")
        .order_by("pk")[:1]
    )
    categories = Category.objects.prefetch_related(
        Prefetch(
            "products",
            queryset=category_previews,
            to_attr="preview_products",
        )
    )

    featured_products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .order_by("pk")[:8]
    )

    return render(
        request,
        "home.html",
        {
            "categories": categories,
            "featured_products": featured_products,
        },
    )


# =========================
# О ПРЕДПРИЯТИИ
# =========================

def about(request):
    return render(request, "about.html")


# =========================
# КОНТАКТЫ
# =========================

def contacts(request):
    if request.method == "POST":
        form = ContactMessageForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Ваше звернення надіслано. "
                "Менеджер зв’яжеться з вами за вказаними контактами.",
            )

            return redirect("contacts")

    else:
        initial = {}

        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)

            initial = {
                "name": request.user.get_full_name(),
                "email": request.user.email,
                "phone": profile.phone if profile else "",
            }

        form = ContactMessageForm(initial=initial)

    return render(
        request,
        "contacts.html",
        {"form": form},
    )


# =========================
# КАТАЛОГ
# =========================

def catalog(request):
    query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()

    products = Product.objects.filter(
        is_active=True
    ).select_related("category")

    categories = Category.objects.all()

    if query:
        products = products.filter(name__icontains=query)

    if selected_category:
        products = products.filter(
            category__slug=selected_category
        )

    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    favorite_product_ids = set()

    if request.user.is_authenticated:
        favorite_product_ids = set(
            Favorite.objects.filter(
                user=request.user
            ).values_list("product_id", flat=True)
        )

    context = {
        "products": page_obj,
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "selected_category": selected_category,
        "favorite_product_ids": favorite_product_ids,
    }

    return render(request, "catalog.html", context)


# =========================
# СТРАНИЦА ТОВАРА
# =========================

def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=pk,
        is_active=True,
    )

    is_favorite = False

    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(
            user=request.user,
            product=product,
        ).exists()

    return render(
        request,
        "product_detail.html",
        {
            "product": product,
            "is_favorite": is_favorite,
        },
    )


# =========================
# ДОБАВЛЕНИЕ / УДАЛЕНИЕ
# ИЗ ИЗБРАННОГО
# =========================


@login_required
@require_POST
def toggle_favorite(request, pk):
    product = get_object_or_404(
        Product,
        pk=pk,
        is_active=True,
    )

    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        product=product,
    )

    if created:
        messages.success(
            request,
            "Товар додано до обраного ❤️",
        )
    else:
        favorite.delete()

        messages.success(
            request,
            "Товар видалено з обраного.",
        )

    # Повернення на попередню сторінку
    next_url = request.POST.get("next", "")

    if next_url:
        from django.utils.http import url_has_allowed_host_and_scheme

        if url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)

    return redirect("catalog")



# =========================
# СТРАНИЦА ИЗБРАННОГО
# =========================

@login_required
def favorites(request):
    favorite_items = Favorite.objects.filter(
        user=request.user,
        product__is_active=True,
    ).select_related(
        "product",
        "product__category",
    )

    return render(
        request,
        "favorites.html",
        {
            "favorite_items": favorite_items,
        },
    )


# =========================
# ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ
# =========================

def privacy(request):
    return render(request, "privacy.html")