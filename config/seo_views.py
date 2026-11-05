from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def robots_txt(request):
    """
    NOT: Admin panel yolunu (ADMIN_URL) bilerek buraya YAZMIYORUZ; robots.txt
    herkese açıktır ve gizli panel adresini ifşa etmiş olurdu. Panel zaten
    giriş istiyor ve arama motorlarına link verilmiyor.
    """
    base_url = settings.SITE_BASE_URL.rstrip("/")
    lines = [
        "User-agent: *",
        "Disallow: /cart/",
        "Disallow: /orders/",
        "Disallow: /accounts/",
        "Disallow: /products/search/",
        # Filtre / arama / sayfalama parametreli kopya sayfalar
        "Disallow: /*?q=",
        "Disallow: /*?filter=",
        "Disallow: /*?badge=",
        "",
        f"Sitemap: {base_url}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
