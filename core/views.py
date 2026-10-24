from django.shortcuts import get_object_or_404, render

from .models import Category, Product

from django.contrib import messages
from django.shortcuts import redirect

from .forms import ContactMessageForm
def home(request):
    return render(request, "home.html")


def about(request):
    return render(request, "about.html")


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
        products = products.filter(category__slug=selected_category)

    context = {
        "products": products,
        "categories": categories,
        "query": query,
        "selected_category": selected_category,
    }

    return render(request, "catalog.html", context)
def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=pk,
        is_active=True,
    )

    return render(
        request,
        "product_detail.html",
        {"product": product},
    )