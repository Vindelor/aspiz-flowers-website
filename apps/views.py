from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Category, Product

# Header'daki canlı arama kutusu için: kullanıcı yazarken bu limitten
# fazlasını göstermiyoruz, tamamı için "Tüm sonuçları gör" linki var.
LIVE_SEARCH_LIMIT = 8


def product_list(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    active_filter = request.GET.get("filter")
    # "Tümünü Gör" links for the homepage's per-badge sections (Editörün
    # Seçimi, Yeni Sezon, Özel Seri, Tükenmek Üzere, ...) land here, kept as
    # its own param so it doesn't collide with the new/deal/popular filters
    # above or break their pagination.
    raw_badge = request.GET.get("badge")
    badge_filter = raw_badge if raw_badge in Product.Badge.values else None

    if active_filter == "new":
        products = products.order_by("-created_at")
    elif active_filter == "deal":
        products = products.filter(discount_percent__gt=0).order_by("-discount_percent", "-created_at")
    elif active_filter == "popular":
        products = products.filter(badge=Product.Badge.POPULAR).order_by("-created_at")
    elif badge_filter:
        products = products.filter(badge=badge_filter).order_by("-created_at")
    else:
        active_filter = ""

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
        "badge_filter_label": Product.Badge(badge_filter).label if badge_filter else "",
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
        products = products.order_by("-created_at")
    elif active_filter == "deal":
        products = products.filter(discount_percent__gt=0).order_by("-discount_percent", "-created_at")
    elif active_filter == "popular":
        products = products.filter(badge=Product.Badge.POPULAR).order_by("-created_at")
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


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images", "price_tiers"),
        slug=slug, is_active=True,
    )
    related = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(pk=product.pk)[:6]

    return render(request, "products/detail.html", {"product": product, "related": related})