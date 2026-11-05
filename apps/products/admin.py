from django import forms
from django.contrib import admin

from .models import Category, PriceTier, Product, ProductImage

# Badge.choices carries the Turkish labels shown to shoppers on the site
# (Yeni Sezon, Popüler, ...). The admin panel is English-only per store
# policy, so this is a second, admin-only label set for the SAME values —
# it never touches what's stored or what customers see.
BADGE_LABELS_EN = {
    Product.Badge.NONE: "No badge",
    Product.Badge.EDITOR_CHOICE: "Editor's Choice",
    Product.Badge.NEW_SEASON: "New Season",
    Product.Badge.DEAL: "Deal",
    Product.Badge.POPULAR: "Popular",
    Product.Badge.SPECIAL_SERIES: "Special Series",
    Product.Badge.LOW_STOCK: "Low Stock",
}


class BadgeAdminFilter(admin.SimpleListFilter):
    title = "badge"
    parameter_name = "badge"

    def lookups(self, request, model_admin):
        return list(BADGE_LABELS_EN.items())

    def queryset(self, request, queryset):
        return queryset.filter(badge=self.value()) if self.value() else queryset


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "is_primary", "order")


class ContactPriceField(forms.DecimalField):
    """Same as a normal price field, but also accepts the literal word
    "DM" (any case) as input, which is stored as NULL — i.e. this tier
    will show a WhatsApp "Mesaj" button instead of a fixed price.
    An existing NULL price is shown back to the admin user as "DM" too."""

    widget = forms.TextInput(attrs={"style": "width: 6em;"})

    def to_python(self, value):
        if isinstance(value, str) and value.strip().upper() == "DM":
            return None
        return super().to_python(value)

    def prepare_value(self, value):
        return "DM" if value in (None, "") else value


class PriceTierAdminForm(forms.ModelForm):
    price = ContactPriceField(
        required=False,
        help_text="Sayı girin, ya da sadece \"DM\" yazın (fiyat yerine WhatsApp'tan mesaj butonu gösterilir).",
    )

    class Meta:
        model = PriceTier
        fields = "__all__"


class PriceTierInline(admin.TabularInline):
    model = PriceTier
    form = PriceTierAdminForm
    extra = 1
    fields = ("min_quantity", "price")
    # Type "DM" in the price field on the highest-quantity row to show that
    # tier as "DM" (contact for price) instead of a fixed amount — see
    # PriceTier.clean, which still enforces this only on the top tier.


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "popular_order", "new_order", "deal_order", "badge_order", "stock_quantity", "stock_state", "badge_en", "is_active")
    list_filter = ("category", BadgeAdminFilter, "is_active")
    list_editable = ("popular_order", "new_order", "deal_order", "badge_order", "stock_quantity", "is_active")  # quick daily edit without opening the product
    search_fields = ("name", "sku")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, PriceTierInline]

    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "sku", "description")}),
        ("SEO", {
            "fields": ("seo_title", "meta_description", "seo_h1"),
            "description": "Google sonuçlarında ve sayfa başlığında görünen alanlar. Boş bırakılırsa otomatik değerler kullanılır.",
        }),
        ("Badge & discount", {"fields": ("badge", "discount_percent")}),
        ("Stock", {"fields": ("stock_quantity", "low_stock_threshold")}),
        ("Homepage ordering", {
            "fields": ("popular_order", "new_order", "deal_order", "badge_order"),
            "classes": ("collapse",),
        }),
        ("Status", {"fields": ("is_active",)}),
    )

    @admin.display(description="Stock status")
    def stock_state(self, obj):
        if obj.is_sold_out:
            return "🔴 Out of stock"
        if obj.is_low_stock:
            return "🟡 Low stock"
        return "🟢 In stock"

    @admin.display(description="Badge")
    def badge_en(self, obj):
        return BADGE_LABELS_EN.get(obj.badge, obj.badge)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        # Swap the dropdown's labels to English when editing a product in
        # admin — the stored value ("popular", "deal", ...) is unchanged,
        # so the site's own Turkish get_badge_display() is unaffected.
        if db_field.name == "badge":
            kwargs["choices"] = list(BADGE_LABELS_EN.items())
        return super().formfield_for_choice_field(db_field, request, **kwargs)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    prepopulated_fields = {"slug": ("name",)}