from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Order, OrderItem

# Status.choices carries the Turkish labels shown to shoppers (Kargoda,
# Teslim Edildi, ...). The admin panel is English-only per store policy,
# so this is a second, admin-only label set for the SAME values — it
# never touches what's stored or what customers see in their order history.
STATUS_LABELS_EN = {
    Order.Status.PENDING: "Pending",
    Order.Status.CONFIRMED: "Confirmed",
    Order.Status.SHIPPED: "Shipped",
    Order.Status.DELIVERED: "Delivered",
    Order.Status.CANCELLED: "Cancelled",
}


class StatusAdminFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return list(STATUS_LABELS_EN.items())

    def queryset(self, request, queryset):
        return queryset.filter(status=self.value()) if self.value() else queryset


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status_en", "total", "whatsapp_notified", "created_at")
    list_filter = (StatusAdminFilter, "whatsapp_notified")
    search_fields = ("id", "user__username", "user__phone")
    inlines = [OrderItemInline]
    actions = ["cancel_orders", "resend_whatsapp"]

    def save_model(self, request, obj, form, change):
        # Picking "Cancelled" in the status dropdown used to skip restocking
        # (only the bulk action did it). Route it through Order.cancel().
        if change and "status" in form.changed_data and obj.status == Order.Status.CANCELLED:
            obj.status = form.initial.get("status", Order.Status.PENDING)
            obj.cancel()
            return
        if change and "status" in form.changed_data and form.initial.get("status") == Order.Status.CANCELLED:
            # Un-cancelling: stock has to be taken again (or the change refused).
            new_status = obj.status
            try:
                obj.reopen(new_status)
            except ValidationError as exc:
                obj.status = Order.Status.CANCELLED
                messages.error(request, f"Status not changed: {exc.messages[0]}")
            return
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        # Deleting an order that is still holding stock must give it back.
        if obj.status != Order.Status.CANCELLED:
            obj.cancel()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for order in queryset:
            if order.status != Order.Status.CANCELLED:
                order.cancel()
        super().delete_queryset(request, queryset)

    @admin.display(description="Status")
    def status_en(self, obj):
        return STATUS_LABELS_EN.get(obj.status, obj.status)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        # Swap the dropdown's labels to English when editing an order in
        # admin — the stored value ("shipped", "delivered", ...) is
        # unchanged, so the site's own Turkish get_status_display() is
        # unaffected.
        if db_field.name == "status":
            kwargs["choices"] = list(STATUS_LABELS_EN.items())
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    @admin.action(description="Cancel selected orders (restocks items)")
    def cancel_orders(self, request, queryset):
        for order in queryset:
            order.cancel()

    @admin.action(description="Resend WhatsApp notification")
    def resend_whatsapp(self, request, queryset):
        from .whatsapp import send_order_notification

        sent = 0
        for order in queryset:
            if send_order_notification(order):
                sent += 1
        self.message_user(request, f"WhatsApp notification sent for {sent} of {queryset.count()} order(s).")