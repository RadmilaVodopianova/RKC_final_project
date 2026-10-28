from core.models import Product

from .cart import Cart


def cart_counter(request):
    items = request.session.get(Cart.SESSION_KEY, {})

    if not items:
        return {"cart_item_count": 0}

    active_product_ids = set(
        Product.objects.filter(
            pk__in=[item["product_id"] for item in items.values()],
            is_active=True,
        ).values_list("pk", flat=True)
    )

    count = sum(
        1
        for item in items.values()
        if item["product_id"] in active_product_ids
    )

    return {"cart_item_count": count}
