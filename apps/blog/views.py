import json

from django.conf import settings
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_safe

# <title> / H1 text exactly as written in the article.
PAGE_TITLE = "Toptan Yapay Çiçek ve Yapay Bitki Tedarikçisi | ASPIZ FLOWERS"

# First sentence of the article's intro paragraph (meta description).
# Edit freely — Google usually shows ~150-160 characters.
META_DESCRIPTION = (
    "ASPIZ FLOWERS, İstanbul İSTOÇ’ta yapay çiçek, yapay bitki ve "
    "dekoratif yeşillik ürünleri sunar."
)


def _json_ld(base_url, page_url):
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": page_url + "#webpage",
                "url": page_url,
                "name": PAGE_TITLE,
                "description": META_DESCRIPTION,
                "inLanguage": "tr-TR",
                "publisher": {"@id": base_url + "/#organization"},
            },
            {
                "@type": "Organization",
                "@id": base_url + "/#organization",
                "name": "ASPIZ FLOWERS",
                "url": base_url + "/",
                "logo": base_url + static("src/img/logo.svg"),
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": (
                        "Mahmutbey, 2433. Sokak İSTOÇ Toptancılar Çarşısı "
                        "D:15.Ada No : 32"
                    ),
                    "postalCode": "34218",
                    "addressLocality": "Bağcılar",
                    "addressRegion": "İstanbul",
                    "addressCountry": "TR",
                },
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Anasayfa",
                        "item": base_url + reverse("core:home"),
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": "Blog",
                        "item": page_url,
                    },
                ],
            },
        ],
    }
    # "</" must never appear inside an inline <script>.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


@require_safe
def index(request):
    base_url = settings.SITE_BASE_URL.rstrip("/")
    page_url = base_url + reverse("blog:index")
    return render(request, "blog/index.html", {
        "page_title": PAGE_TITLE,
        "meta_description": META_DESCRIPTION,
        "canonical_url": page_url,
        "json_ld": _json_ld(base_url, page_url),
    })