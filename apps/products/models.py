import io
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from PIL import Image, ImageOps

MAX_UPLOAD_MB = 8
MAX_DIMENSION = 1600  # px, longest side after resize

# Django's slugify() drops the Turkish dotless "ı" entirely (it has no
# Unicode decomposition to "i", unlike ç/ü/ö/ş/ğ which transliterate fine),
# e.g. "Sarmaşık" -> "sarmask" or "Saksı" -> "saks" instead of "saksi".
# Mapping the Turkish-specific letters explicitly first avoids that.
_TURKISH_CHAR_MAP = str.maketrans({
    "ı": "i", "İ": "I", "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U", "ş": "s", "Ş": "S",
    "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
})


def turkish_slugify(value):
    return slugify(value.translate(_TURKISH_CHAR_MAP))


def validate_image_size(file):
    limit_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if file.size > limit_bytes:
        raise ValidationError(f"Görsel boyutu {MAX_UPLOAD_MB} MB'den fazla olamaz.")


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.ImageField(upload_to="categories/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = turkish_slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    class Badge(models.TextChoices):
        NONE = "none", "Rozet yok"
        EDITOR_CHOICE = "editor", "Editörün Seçimi"
        NEW_SEASON = "new", "Yeni Sezon"
        DEAL = "deal", "Fırsat"
        POPULAR = "popular", "Popüler"
        SPECIAL_SERIES = "special", "Özel Seri"
        LOW_STOCK = "low_stock", "Tükenmek Üzere"
        # SOLD_OUT is derived automatically from stock_quantity == 0,
        # not chosen manually — see is_sold_out property below.

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField("SKU", max_length=30, unique=True)
    description = models.TextField(blank=True)

    badge = models.CharField(max_length=20, choices=Badge.choices, default=Badge.NONE)
    discount_percent = models.PositiveIntegerField(default=0)  # e.g. 15 -> "-%15" ribbon

    # Stock: this is the ONLY field that should ever be touched automatically
    # by order logic (see OrderItem.save in apps/orders/models.py). Admin
    # can still override it manually from the Django Admin if needed, but
    # normal order flow keeps it in sync without any manual step.
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = turkish_slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    @property
    def is_sold_out(self):
        return self.stock_quantity <= 0

    @property
    def is_low_stock(self):
        return 0 < self.stock_quantity <= self.low_stock_threshold

    @property
    def display_badge(self):
        """Stock state always overrides a manually chosen badge."""
        if self.is_sold_out:
            return "Tükendi"
        if self.is_low_stock:
            return self.get_badge_display() if self.badge != self.Badge.NONE else "Tükenmek Üzere"
        return self.get_badge_display() if self.badge != self.Badge.NONE else None

    BADGE_COLOR_MAP = {
        Badge.EDITOR_CHOICE: "from-teal-500 to-emerald-600",
        Badge.NEW_SEASON: "from-sky-500 to-blue-600",
        Badge.DEAL: "from-emerald-500 to-green-600",
        Badge.POPULAR: "from-pink-500 to-rose-600",
        Badge.SPECIAL_SERIES: "from-purple-500 to-violet-600",
        Badge.LOW_STOCK: "from-orange-500 to-red-500",
    }

    @property
    def badge_gradient_classes(self):
        if self.is_sold_out:
            return "from-wine-700 to-wine-900"
        return self.BADGE_COLOR_MAP.get(self.badge, "from-wine-700 to-wine-900")

    @property
    def primary_image(self):
        # NOTE: uses .all() (not .filter()) on purpose — when the view calls
        # prefetch_related("images"), .all() reuses the already-fetched list
        # from memory. .filter()/.order_by() would silently ignore that
        # prefetch and run one extra query PER PRODUCT (N+1), which is fine
        # at 10 products but turns a 24-product page into 25+ queries.
        images = list(self.images.all())
        for image in images:
            if image.is_primary:
                return image
        return images[0] if images else None

    @property
    def price_range(self):
        """
        Only tiers with a real price count toward the shown range — a
        contact-only tier (PriceTier.price left blank, e.g. '≥400 adet: DM')
        has no numeric value to range against. See has_contact_tier /
        contact_tier for surfacing that tier separately in templates.
        """
        tiers = [t for t in self.price_tiers.order_by("min_quantity") if t.price is not None]
        if not tiers:
            return None
        return {"min": tiers[-1].price, "max": tiers[0].price}

    @property
    def contact_tier(self):
        """The single 'DM for price' tier, if this product has one (see
        PriceTier.clean: at most one such tier is allowed, and it must be
        the highest-quantity tier)."""
        return self.price_tiers.filter(price__isnull=True).order_by("min_quantity").first()

    @property
    def has_contact_tier(self):
        return self.contact_tier is not None

    @property
    def highest_priced_tier(self):
        """The highest-quantity tier that still has a real price — used as
        the default quantity-box highlight/selection, since the contact-only
        ('DM') tier (if any) isn't something the qty input can default to."""
        tiers = [t for t in self.price_tiers.order_by("min_quantity") if t.price is not None]
        return tiers[-1] if tiers else None

    @property
    def original_price_range(self):
        """
        Reference (pre-discount) price range, shown struck-through next to
        price_range on cards/detail when discount_percent is set. PriceTier
        rows always store the CURRENT (already discounted) price, so this
        reverse-computes what it would be without the discount.
        """
        if not self.discount_percent:
            return None
        pr = self.price_range
        if not pr:
            return None
        factor = Decimal(100 - self.discount_percent) / Decimal(100)
        if factor <= 0:
            return None
        return {
            "min": (pr["min"] / factor).quantize(Decimal("0.01")),
            "max": (pr["max"] / factor).quantize(Decimal("0.01")),
        }


class ProductImage(models.Model):
    """
    Admin swaps these manually from Django Admin whenever the daily photos
    change — no automation needed here by design.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/", validators=[validate_image_size])
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def _compress(self):
        """
        Phone-camera photos are routinely 4000px wide and 5-10MB. At
        200-300 products that's 1-3GB of storage and, worse, every one of
        those full-size files gets served straight to visitors' phones on
        the product grid. This downsizes to MAX_DIMENSION on the longest
        side and re-encodes as WEBP at quality 82, which in practice takes
        a ~6MB photo down to ~200-400KB with no visible quality loss on
        screen. Runs once, at upload time, so it costs nothing later.
        """
        img = Image.open(self.image)
        img = ImageOps.exif_transpose(img)  # fix sideways phone photos
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=82, method=6)
        buffer.seek(0)

        original_name = self.image.name.rsplit(".", 1)[0]
        self.image = ContentFile(buffer.read(), name=f"{original_name}.webp")

    def save(self, *args, **kwargs):
        if self.image and self._state.adding:
            self._compress()
        super().save(*args, **kwargs)
        if self.is_primary:
            # keep exactly one primary image per product
            ProductImage.objects.filter(product=self.product).exclude(pk=self.pk).update(is_primary=False)


class PriceTier(models.Model):
    """
    Wholesale tiered pricing, e.g. 40₺ for 400+, 38₺ for 800+, 36₺ for 1200+
    (matches the reference product page: Min. 400 ad / 800-1.199 / ≥1.200).
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_tiers")
    min_quantity = models.PositiveIntegerField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=(
            "Boş bırakılırsa bu kademe 'DM' (mesajla fiyat) olarak gösterilir — "
            "örn. 400 adet ve üzeri için sabit fiyat yerine WhatsApp'tan fiyat alınır. "
            "Sadece en yüksek adetli kademe boş bırakılabilir."
        ),
    )

    class Meta:
        ordering = ["min_quantity"]
        unique_together = ("product", "min_quantity")

    def __str__(self):
        price_label = f"{self.price}" if self.price is not None else "DM"
        return f"{self.product.name}: {self.min_quantity}+ -> {price_label}"

    @property
    def is_contact_price(self):
        return self.price is None

    def clean(self):
        if self.product_id is None:
            return

        # Fewer units must never cost less than more units (contact-only
        # tiers have no numeric price, so they're skipped on both sides).
        if self.price is not None:
            higher_tiers = PriceTier.objects.filter(
                product=self.product, min_quantity__gt=self.min_quantity
            ).exclude(pk=self.pk).exclude(price__isnull=True)
            if higher_tiers.filter(price__gte=self.price).exists():
                raise ValidationError("Daha yüksek kademelerin fiyatı bu kademeye eşit veya daha düşük olmalıdır.")

        # A contact-only ("DM") tier only makes sense as the highest-quantity
        # tier — every lower tier must still have a real, checkout-usable price.
        if self.price is None:
            lower_tiers_without_price = PriceTier.objects.filter(
                product=self.product, min_quantity__lt=self.min_quantity, price__isnull=True
            ).exclude(pk=self.pk)
            if lower_tiers_without_price.exists():
                raise ValidationError("Fiyat tablosunda yalnızca en yüksek kademe (en yüksek minimum miktar) boş (DM) bırakılabilir.")