import json

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Category, Product

# Header'daki canlı arama kutusu için: kullanıcı yazarken bu limitten
# fazlasını göstermiyoruz, tamamı için "Tüm sonuçları gör" linki var.
LIVE_SEARCH_LIMIT = 8

# Admin'da bölüm sırası (popular_order, new_order ...) verilen ürünler listenin başında.
def pinned_first(field):
    return F(field).asc(nulls_last=True)


def product_list(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    active_filter = request.GET.get("filter")

    if active_filter == "new":
        products = products.order_by(pinned_first("new_order"), "-created_at")
    elif active_filter == "deal":
        products = products.filter(discount_percent__gt=0).order_by(pinned_first("deal_order"), "-discount_percent", "-created_at")
    elif active_filter == "popular":
        products = products.filter(badge=Product.Badge.POPULAR).order_by(pinned_first("popular_order"), "-created_at")
    else:
        active_filter = ""

    # Ana sayfadaki rozet bölümlerinin "Tümünü Gör" linki (?badge=editor vb.)
    badge_filter = request.GET.get("badge") or ""
    badge_filter_label = ""
    if badge_filter and badge_filter in Product.Badge.values and badge_filter != Product.Badge.NONE:
        products = products.filter(badge=badge_filter).order_by(pinned_first("badge_order"), "-created_at")
        badge_filter_label = dict(Product.Badge.choices)[badge_filter]
    else:
        badge_filter = ""

    category_slug = request.GET.get("category")
    if category_slug:
        products = products.filter(category__slug=category_slug)

    query = request.GET.get("q")
    if query:
        products = products.filter(name__icontains=query)

    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "categories": Category.objects.all(),
        "active_category": category_slug,
        "query": query or "",
        "active_filter": active_filter,
        "badge_filter": badge_filter,
        "badge_filter_label": badge_filter_label,
    }
    return render(request, "products/list.html", context)


def product_search_api(request):
    """
    Header'daki canlı arama kutusu bunu çağırıyor (AJAX/fetch, JSON döner).
    Aynı DB ve aynı filtre mantığı (name__icontains) product_list ile ortak;
    tek fark burada sonuç sayısı sınırlı ve sayfa yerine JSON dönüyor.
    """
    query = (request.GET.get("q") or "").strip()
    results = []

    if len(query) >= 2:
        products = (
            Product.objects.filter(is_active=True, name__icontains=query)
            .select_related("category")
            .prefetch_related("images")
            .order_by("-created_at")[:LIVE_SEARCH_LIMIT]
        )
        for p in products:
            image = p.primary_image
            results.append({
                "id": p.id,
                "name": p.name,
                "category": p.category.name,
                "url": p.get_absolute_url(),
                "image_url": image.image.url if image else "",
                "is_sold_out": p.is_sold_out,
            })

    return JsonResponse({
        "query": query,
        "results": results,
    })


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, is_active=True)
    active_filter = request.GET.get("filter")

    if active_filter == "new":
        products = products.order_by(pinned_first("new_order"), "-created_at")
    elif active_filter == "deal":
        products = products.filter(discount_percent__gt=0).order_by(pinned_first("deal_order"), "-discount_percent", "-created_at")
    elif active_filter == "popular":
        products = products.filter(badge=Product.Badge.POPULAR).order_by(pinned_first("popular_order"), "-created_at")
    else:
        active_filter = ""

    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "category": category,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "categories": Category.objects.all(),
        "active_category": slug,
        "active_filter": active_filter,
    }
    return render(request, "products/list.html", context)


def _product_json_ld(product, base_url, page_url, seo_title, meta_description):
    """schema.org Product + BreadcrumbList (Google zengin sonuç: fiyat, stok)."""
    image = product.primary_image
    product_data = {
        "@type": "Product",
        "@id": page_url + "#product",
        "name": product.seo_h1 or product.name,
        "sku": product.sku,
        "url": page_url,
        "brand": {"@type": "Brand", "name": "ASPIZ FLOWERS"},
        "category": product.category.name,
    }
    if meta_description:
        product_data["description"] = meta_description
    if image:
        product_data["image"] = [base_url + i.image.url for i in product.images.all()]

    price_range = product.price_range
    if price_range:
        availability = "OutOfStock" if product.is_sold_out else "InStock"
        product_data["offers"] = {
            "@type": "AggregateOffer",
            "priceCurrency": "TRY",
            "lowPrice": format(price_range["min"], ".2f"),
            "highPrice": format(price_range["max"], ".2f"),
            "offerCount": len([t for t in product.price_tiers.all() if t.price is not None]),
            "availability": "https://schema.org/" + availability,
            "url": page_url,
        }

    data = {
        "@context": "https://schema.org",
        "@graph": [
            product_data,
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Ana Sayfa",
                     "item": base_url + reverse("core:home")},
                    {"@type": "ListItem", "position": 2, "name": product.category.name,
                     "item": base_url + reverse("products:by_category", args=[product.category.slug])},
                    {"@type": "ListItem", "position": 3, "name": product.name, "item": page_url},
                ],
            },
        ],
    }
    # "</" must never appear inside an inline <script>.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images", "price_tiers"),
        slug=slug, is_active=True,
    )
    related = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(pk=product.pk)[:6]

    base_url = settings.SITE_BASE_URL.rstrip("/")
    page_url = base_url + product.get_absolute_url()
    seo_title = product.seo_title or f"{product.name} | ASPIZ FLOWERS"
    image = product.primary_image

    return render(request, "products/detail.html", {
        "product": product,
        "related": related,
        "seo_title": seo_title,
        "canonical_url": page_url,
        "og_image": (base_url + image.image.url) if image else "",
        "json_ld": _product_json_ld(product, base_url, page_url, seo_title, product.meta_description),
    })
