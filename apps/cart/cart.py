"""
Cart resolution + merge logic, kept out of views.py so it stays testable
and reusable (e.g. from a future API endpoint).
"""
from django.core.exceptions import ValidationError

from .models import Cart, CartItem


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _user_cart(user):
    """
    The user's cart, tolerant of duplicates.

    Cart.user is a plain ForeignKey (not unique), so two simultaneous first
    requests can each create a cart for the same user. get_or_create() then
    raised MultipleObjectsReturned on EVERY page (the header badge calls
    get_cart on each request) and the account was unusable. Take the oldest
    cart instead of crashing.
    """
    cart = Cart.objects.filter(user=user).order_by("pk").first()
    return cart or Cart.objects.create(user=user)


def _guest_cart(session_key):
    cart = Cart.objects.filter(session_key=session_key, user__isnull=True).order_by("pk").first()
    return cart or Cart.objects.create(session_key=session_key)


def get_cart(request):
    """
    Returns the current user's/session's cart, creating it if needed.
    Also merges any anonymous session cart into the account cart the
    moment a user is authenticated (covers the "logged in mid-shopping"
    case cleanly, instead of silently losing the guest cart).
    """
    session_key = _ensure_session(request)

    if request.user.is_authenticated:
        cart = _user_cart(request.user)

        guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
        if guest_cart and guest_cart.pk != cart.pk:
            for item in guest_cart.items.all():
                existing = cart.items.filter(product=item.product).first()
                if existing:
                    existing.quantity += item.quantity
                    existing.save(update_fields=["quantity"])
                else:
                    item.cart = cart
                    item.save(update_fields=["cart"])
            guest_cart.delete()
        return cart

    return _guest_cart(session_key)


def merge_guest_cart(user, guest_session_key):
    """
    login() rotates the session key, so the guest cart (stored under the OLD
    key) can no longer be found by get_cart(). The login view reads the key
    BEFORE login() and calls this right after it.
    """
    if not guest_session_key:
        return
    guest_cart = Cart.objects.filter(session_key=guest_session_key, user__isnull=True).first()
    if not guest_cart:
        return
    cart = _user_cart(user)
    for item in guest_cart.items.select_related("product"):
        existing = cart.items.filter(product=item.product).first()
        if existing:
            existing.quantity = min(existing.quantity + item.quantity, max(item.product.stock_quantity, 1))
            existing.save(update_fields=["quantity"])
        else:
            item.cart = cart
            item.save(update_fields=["cart"])
    guest_cart.delete()


def has_price(product):
    """True only if the product has at least one tier with a real price."""
    return product.price_tiers.filter(price__isnull=False).exists()


def add_to_cart(request, product, quantity=1):
    if not has_price(product):
        raise ValidationError(f"'{product.name}' için fiyat bilgisi yok. Lütfen WhatsApp'tan bize ulaşın.")
    cart = get_cart(request)

    if quantity < 1:
        raise ValidationError("Adet en az 1 olmalı.")
    if quantity > product.stock_quantity:
        raise ValidationError(
            f"Yetersiz stok: '{product.name}' için sadece {product.stock_quantity} adet var."
        )

    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
    if not created:
        new_quantity = item.quantity + quantity
        if new_quantity > product.stock_quantity:
            raise ValidationError(
                f"Yetersiz stok: '{product.name}' için sadece {product.stock_quantity} adet var."
            )
        item.quantity = new_quantity
        item.save(update_fields=["quantity"])
    return cart


def update_quantity(request, product_id, quantity):
    cart = get_cart(request)
    item = cart.items.filter(product_id=product_id).first()
    if not item:
        return cart
    if quantity < 1:
        item.delete()
        return cart
    if quantity > item.product.stock_quantity:
        raise ValidationError(
            f"Yetersiz stok: '{item.product.name}' için sadece {item.product.stock_quantity} adet var."
        )
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return cart


def remove_from_cart(request, product_id):
    cart = get_cart(request)
    cart.items.filter(product_id=product_id).delete()
    return cart
