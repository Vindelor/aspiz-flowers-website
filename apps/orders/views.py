from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cart.cart import get_cart, has_price
from apps.cart.models import Cart

from django.core.cache import cache

from .models import Order, OrderItem


class EmptyCartError(Exception):
    pass


MAX_PENDING_ORDERS = 3
CHECKOUT_MAX_PER_HOUR = 5


def checkout_allowed(user_id):
    key = f"checkout_rate:{user_id}"
    if cache.add(key, 1, 3600):
        return True
    try:
        return cache.incr(key) <= CHECKOUT_MAX_PER_HOUR
    except ValueError:
        cache.set(key, 1, 3600)
        return True
from .whatsapp import get_customer_whatsapp_link, send_order_notification


@login_required
def checkout(request):
    order_id = request.GET.get("order")
    if order_id:
        order = get_object_or_404(Order, pk=order_id, user=request.user)
        whatsapp_link = get_customer_whatsapp_link(order)

        if whatsapp_link:
            return redirect(whatsapp_link)

        return render(
            request,
            "orders/checkout.html",
            {
                "order": order,
                "whatsapp_link": None,
                "auto_open_whatsapp": False,
            },
        )

    cart = get_cart(request)

    if not cart.items.exists():
        messages.warning(request, "Sepetiniz boş.")
        return redirect("cart:detail")

    if request.method == "POST":
        # Orders reserve stock immediately and there is no payment step, so
        # without a cap one account could drain the whole catalogue.
        pending = request.user.orders.filter(status=Order.Status.PENDING).count()
        if pending >= MAX_PENDING_ORDERS:
            messages.error(
                request,
                "Bekleyen siparişleriniz var. Yeni sipariş vermeden önce lütfen "
                "mağazamızla WhatsApp üzerinden iletişime geçin.",
            )
            return redirect("cart:detail")
        if not checkout_allowed(request.user.pk):
            messages.error(request, "Çok sık sipariş denemesi yapıldı. Lütfen biraz sonra tekrar deneyin.")
            return redirect("cart:detail")
        # Cart lines can go stale between "add to cart" and checkout: the
        # product may have been deactivated or lost its price meanwhile.
        problems = []
        for item in cart.items.select_related("product"):
            if not item.product.is_active:
                problems.append(f"'{item.product.name}' artık satışta değil.")
            elif not has_price(item.product) or item.unit_price <= 0:
                problems.append(f"'{item.product.name}' için fiyat bilgisi yok.")
        if problems:
            messages.error(request, " ".join(problems) + " Lütfen bu ürünleri sepetten çıkarın.")
            return redirect("cart:detail")
        try:
            with transaction.atomic():
                # Lock the cart row: a double-click / second tab waits here, then
                # sees an empty cart instead of creating a second (empty) order.
                locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
                # Fixed product_id order => concurrent orders lock product rows in
                # the same order, so MySQL can't deadlock them against each other.
                items = list(locked_cart.items.select_related("product").order_by("product_id"))
                if not items:
                    raise EmptyCartError
                order = Order.objects.create(user=request.user)
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )
                locked_cart.items.all().delete()
        except EmptyCartError:
            messages.warning(request, "Sepetiniz boş.")
            return redirect("cart:detail")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, "message") else str(e))
            return redirect("cart:detail")

        # Order is already committed at this point — a WhatsApp failure
        # must never undo a valid order, so this runs outside the atomic
        # block above and only logs/flags on failure (see whatsapp.py).
        # This is a best-effort backend alert via the Meta Business API
        # (requires WHATSAPP_PHONE_NUMBER_ID/ACCESS_TOKEN + an approved
        # template to actually be configured — see whatsapp.py docstring).
        send_order_notification(order)

        messages.success(request, f"Siparişiniz alındı! Sipariş No: #{order.pk}")

        whatsapp_link = get_customer_whatsapp_link(order)
        if whatsapp_link:
            return redirect(whatsapp_link)

        return redirect(f"{reverse('orders:checkout')}?order={order.pk}")

    return render(request, "orders/checkout.html", {"cart": cart})


@login_required
def order_history(request):
    orders = request.user.orders.order_by("-created_at")
    return render(request, "orders/history.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    whatsapp_link = get_customer_whatsapp_link(order)

    if whatsapp_link:
        return redirect(whatsapp_link)

    return redirect(f"{reverse('orders:checkout')}?order={pk}")


@login_required
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if request.method == "POST":
        # Once the customer has been handed off to WhatsApp for this order,
        # the shop already has (or is about to have) the request in a real
        # chat — letting the site silently cancel/restock behind that
        # conversation would confuse staff. So self-service cancel is only
        # available for the (rare) case where no WhatsApp link exists yet,
        # e.g. WHATSAPP_ADMIN_PHONE isn't configured.
        if get_customer_whatsapp_link(order):
            messages.error(
                request,
                "Bu sipariş WhatsApp üzerinden mağazamıza iletildi, bu yüzden "
                "sitede iptal edilemiyor. Değişiklik için lütfen WhatsApp "
                "sohbeti üzerinden bizimle iletişime geçin.",
            )
        elif order.status in (Order.Status.PENDING, Order.Status.CONFIRMED):
            order.cancel()
            messages.info(request, f"Sipariş #{order.pk} iptal edildi.")
    return redirect("orders:detail", pk=order.pk)