from django.conf import settings

from .cart import get_cart


def cart(request):
    """Exposes {{ cart_item_count }} to every template without every view
    having to fetch it manually (used for the header cart badge).

    Deliberately does NOT call get_cart() for a brand-new anonymous visitor
    with no session yet: get_cart() force-creates a session (and a Cart row)
    on every single call, so doing it unconditionally on every page load
    was creating a session + Cart row in the database for every anonymous
    page view, even from visitors who never add anything to cart. Once a
    session already exists (guest added something, or user is logged in),
    this looks up the cart normally.
    """
    if request.path.startswith("/" + settings.ADMIN_URL.strip("/") + "/"):
        return {}
    if not request.user.is_authenticated and not request.session.session_key:
        return {"cart_item_count": 0}
    current_cart = get_cart(request)
    return {"cart_item_count": current_cart.total_items}
