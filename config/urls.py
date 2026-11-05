from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.static import serve as media_serve

from .seo_views import robots_txt
from .sitemaps import SITEMAPS

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("products/", include("apps.products.urls")),
    path("cart/", include("apps.cart.urls")),
    path("orders/", include("apps.orders.urls")),
    path("blog/", include("apps.blog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
elif settings.SERVE_MEDIA_VIA_DJANGO:
    # NOTE: django.conf.urls.static.static() returns [] when DEBUG=False, so it
    # can NOT be used here — media would 404 in production. Register the
    # serve view explicitly instead.
    urlpatterns += [
        re_path(
            r"^%s(?P<path>.*)$" % settings.MEDIA_URL.lstrip("/"),
            media_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]