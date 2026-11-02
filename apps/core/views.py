from django.db.models import F
from django.shortcuts import render
from django.urls import reverse

from apps.products.models import Category, Product

# "Yeni Ürünler" (by created_at) and "Popüler Ürünler" (badge=POPULAR) each
# already get their own hand-built section below. Every other badge in the
# admin's dropdown (Editörün Seçimi, Yeni Sezon, Özel Seri, Tükenmek Üzere)
# had NO matching homepage section at all — this list is what makes each of
# those show up too, in this display order, whenever a product carries it.
EXTRA_BADGE_SECTION_TITLES = {
    Product.Badge.EDITOR_CHOICE: "Editörün Seçimi",
    Product.Badge.NEW_SEASON: "Yeni Sezon",
    Product.Badge.SPECIAL_SERIES: "Özel Seri",
    Product.Badge.LOW_STOCK: "Tükenmek Üzere",
}


# Manually pinned products (popular_order / new_order / deal_order /
# badge_order = 1, 2, 3 ...) come first in their section; the rest keep the
# section's normal order after them.
def pinned_first(field):
    return F(field).asc(nulls_last=True)


def home(request):
    categories = Category.objects.all()
    active_products = Product.objects.filter(is_active=True).select_related("category")

    badge_sections = []
    for badge_value, title in EXTRA_BADGE_SECTION_TITLES.items():
        products = active_products.filter(badge=badge_value).order_by(pinned_first("badge_order"), "-created_at")[:12]
        if products:
            badge_sections.append({
                "title": title,
                "products": products,
                "see_all_url": f"{reverse('products:list')}?badge={badge_value}",
            })

    # Ordered list of the home page sections that actually have products, so
    # the template can drop the promo banner between the 3rd and 4th section
    # no matter which optional sections (popular / deals / badges) exist.
    popular_products = active_products.filter(badge=Product.Badge.POPULAR).order_by(pinned_first("popular_order"), "-created_at")[:12]
    new_products = active_products.order_by(pinned_first("new_order"), "-created_at")[:12]
    deal_products = active_products.filter(discount_percent__gt=0).order_by(pinned_first("deal_order"), "-created_at")[:12]

    sections = []
    if popular_products:
        sections.append({"title": "Popüler Ürünler", "products": popular_products,
                         "see_all_url": f"{reverse('products:list')}?filter=popular",
                         "promo": True, "bg": ""})
    sections.append({"title": "Yeni Ürünler", "products": new_products,
                     "see_all_url": f"{reverse('products:list')}?filter=new",
                     "promo": False, "bg": "bg-white"})
    if deal_products:
        sections.append({"title": "Fırsat Ürünleri", "products": deal_products,
                         "see_all_url": f"{reverse('products:list')}?filter=deal",
                         "promo": False, "bg": "bg-orange-50"})
    for extra in badge_sections:
        sections.append({**extra, "promo": False, "bg": ""})

    context = {
        "sections": sections,
        "categories": categories,
        "new_products": new_products,
        "deal_products": deal_products,
        "popular_products": popular_products,

        "badge_sections": badge_sections,

        "new_url": f"{reverse('products:list')}?filter=new",
        "deal_url": f"{reverse('products:list')}?filter=deal",
        "popular_url": f"{reverse('products:list')}?filter=popular",
    }
    return render(request, "core/home.html", context)