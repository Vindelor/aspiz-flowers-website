from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.products.models import Category, Product


class StaticViewSitemap(Sitemap):
    """Ana sayfa, tüm ürünler, blog."""
    protocol = "https"
    changefreq = "weekly"

    _PRIORITY = {"core:home": 1.0, "products:list": 0.9, "blog:index": 0.6}

    def items(self):
        return list(self._PRIORITY)

    def location(self, name):
        return reverse(name)

    def priority(self, name):
        return self._PRIORITY[name]


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Category.objects.all()

    def location(self, category):
        return reverse("products:by_category", args=[category.slug])


class ProductSitemap(Sitemap):
    """Sadece aktif ürünler (pasif/gizli ürünler sitemap'e girmez)."""
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7
    limit = 5000

    def items(self):
        return Product.objects.filter(is_active=True).order_by("-updated_at")

    def lastmod(self, product):
        return product.updated_at

    def location(self, product):
        return product.get_absolute_url()


SITEMAPS = {
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
}
