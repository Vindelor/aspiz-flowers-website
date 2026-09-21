from django.conf import settings

from apps.products.models import Category, Product


def nav_categories(request):
    """
    Exposes {{ nav_categories }} to every template (header nav needs the
    category list on literally every page, not just the product list
    views). Runs one cheap query per request; fine at the category counts
    a shop like this has (tens, not thousands).

    Also exposes {{ featured_products }}: a handful of "Popüler" (badge)
    products, used by the header's circular slider. Previously that slider
    just repeated the category nav bar right above it — this gives each
    of the two its own purpose instead of showing the same thing twice.

    Also exposes {{ shop_whatsapp_display }}: the same number used for the
    WhatsApp order-notification API (WHATSAPP_ADMIN_PHONE, e.g. "905XXXXXXXXX"),
    reused here so the header/footer show your real number instead of a
    hardcoded placeholder. Falls back to a clearly-marked placeholder string
    if that setting isn't configured yet.
    """
    raw_phone = settings.WHATSAPP_ADMIN_PHONE
    featured_products = (
        Product.objects.filter(is_active=True, badge=Product.Badge.POPULAR)
        .select_related("category")
        .prefetch_related("images")
        .order_by("-created_at")[:12]
    )
    return {
        "nav_categories": Category.objects.all(),
        "featured_products": featured_products,
        "shop_whatsapp_display": raw_phone or "+90 5xx xxx xx xx",
    }