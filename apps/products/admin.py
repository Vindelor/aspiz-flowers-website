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


import os
import posixpath

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify

_TR_MAP = str.maketrans({
    "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
})


def seo_filename(raw):
    """'Yapay Kasımpatı Demeti 35 cm' -> 'yapay-kasimpati-demeti-35-cm' (Turkish letters transliterated)."""
    return slugify(str(raw).translate(_TR_MAP))[:70].strip("-")


class ProductImageAdminForm(forms.ModelForm):
    """Adds a "File name" box to every image row so the image file can be renamed
    right here (no delete + re-upload). On a brand-new upload the same box sets the
    name the file is saved under. Extension is kept; Turkish letters / spaces are
    converted to a clean SEO-friendly slug automatically."""

    file_name = forms.CharField(
        label="File name", required=False, max_length=90,
        widget=forms.TextInput(attrs={"size": 38}),
        help_text="Without extension, e.g. yapay-kasimpati-demeti-35-cm-7-bas. Change it and save to rename the file.",
    )

    class Meta:
        model = ProductImage
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rename_to = None
        inst = self.instance
        if inst.pk and inst.image:
            base = posixpath.basename(inst.image.name)
            stem = posixpath.splitext(base)[0]
            self.fields["file_name"].initial = stem
            self.initial["file_name"] = stem
            self.fields["file_name"].help_text = (
                f"Current file: {base}. Change the name and save to rename it "
                "(the image URL changes with it)."
            )

    def clean(self):
        cleaned = super().clean()
        if "file_name" not in self.changed_data:
            return cleaned
        new = seo_filename(cleaned.get("file_name") or "")
        if not new:
            return cleaned  # emptied -> keep the current/original name
        upload = cleaned.get("image")
        if isinstance(upload, UploadedFile):
            # a new file is being uploaded in this same submit -> save it under the chosen name
            ext = os.path.splitext(upload.name)[1].lower()
            upload.name = f"{new}{ext}"
        elif self.instance.pk and self.instance.image:
            fieldfile = self.instance.image
            old = fieldfile.name
            folder, base = posixpath.split(old)
            ext = posixpath.splitext(base)[1]
            target = posixpath.join(folder, f"{new}{ext}")
            if target != old:
                if not fieldfile.storage.exists(old):
                    raise ValidationError("The original image file was not found on disk, so it can't be renamed.")
                if fieldfile.storage.exists(target):
                    raise ValidationError(f"A file named {new}{ext} already exists in this folder. Choose another name.")
                self._rename_to = target
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        if self._rename_to and inst.pk:
            storage = inst.image.storage
            old = inst.image.name
            with storage.open(old, "rb") as fh:
                saved = storage.save(self._rename_to, fh)
            inst.image.name = saved
            storage.delete(old)
        if commit:
            inst.save()
            self._save_m2m()
        return inst


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageAdminForm
    extra = 1
    fields = ("image", "file_name", "alt_text", "is_primary", "order")


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