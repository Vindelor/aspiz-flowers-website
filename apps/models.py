import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from PIL import Image, ImageOps

MAX_UPLOAD_MB = 8
MAX_DIMENSION = 1600  # px, longest side after resize


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
            self.slug = slugify(self.name)
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
            self.slug = slugify(self.name)
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
        tiers = sorted(self.price_tiers.all(), key=lambda t: t.min_quantity)
        if not tiers:
            return None
        return {"min": tiers[-1].price, "max": tiers[0].price}


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
        side and re-encodes as JPEG at quality 82, which in practice takes
        a ~6MB photo down to ~200-400KB with no visible quality loss on
        screen. Runs once, at upload time, so it costs nothing later.
        """
        img = Image.open(self.image)
        img = ImageOps.exif_transpose(img)  # fix sideways phone photos
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=82, optimize=True)
        buffer.seek(0)

        original_name = self.image.name.rsplit(".", 1)[0]
        self.image = ContentFile(buffer.read(), name=f"{original_name}.jpg")

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
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["min_quantity"]
        unique_together = ("product", "min_quantity")

    def __str__(self):
        return f"{self.product.name}: {self.min_quantity}+ -> {self.price}"

    def clean(self):
        # Fewer units must never cost less than more units.
        higher_tiers = PriceTier.objects.filter(
            product=self.product, min_quantity__gt=self.min_quantity
        ).exclude(pk=self.pk)
        if higher_tiers.filter(price__gte=self.price).exists():
            raise ValidationError("Daha yüksek kademelerin fiyatı bu kademeye eşit veya daha düşük olmalıdır.")
