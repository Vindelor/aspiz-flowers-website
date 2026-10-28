from django.conf import settings
from django.urls import reverse
from urllib.parse import quote

from apps.products.models import Category, turkish_slugify

# ---------------------------------------------------------------------------
# Footer'ın üstündeki "Türkiye haritası + sipariş bildirimleri" bölümü
# (templates/components/turkey_map.html, static/vendor/js/turkey-map.js).
#
# Her satır: (şehir, müşteri adı veya None, harita x %, harita y %, tür,
#             kategori slug parçaları, link metni, kategori yoksa arama kelimesi)
#   tür "order" -> "<link> aldı",  tür "ship" -> "<link> kargolandı"
# x/y değerleri templates/components/turkey_map.html'deki noktalı haritanın (592x264) üzerinde
# şehrin enlem/boylamından hesaplandı. Şehir/isim/ürün değiştirmek için sadece
# bu listeyi düzenleyin.
# Link: slug'ı eşleşen kategori varsa o kategori sayfası, yoksa ürün listesinde
# arama (?q=) sayfasına gider — yani kategori adlarını admin'den değiştirseniz
# bile link kırılmaz.
# ---------------------------------------------------------------------------
TURKEY_MAP_NOTIFICATIONS = [
    ("İstanbul", "Arkan", 16.2, 19.5, "order", ("gul",), "toptan yapay gül", "gül"),
    ("İzmir", "Deniz", 6.5, 58.8, "order", ("karanfil",), "toptan yapay karanfil", "karanfil"),
    ("Ankara", "Elif", 36.5, 35.9, "order", ("kasimpati", "krizantem"), "toptan yapay kasımpatı", "kasımpatı"),
    ("Bursa", "Mehmet", 16.6, 32.1, "order", ("papatya",), "toptan yapay papatya", "papatya"),
    ("Antalya", "Zeynep", 25.2, 81.8, "order", ("aycicegi",), "toptan yapay ayçiçeği", "ayçiçeği"),
    ("Adana", "Burak", 49.4, 80.3, "order", ("gerbera",), "toptan yapay gerbera", "gerbera"),
    ("Trabzon", "Ayşe", 72.5, 19.7, "order", ("sakayik",), "toptan yapay şakayık", "şakayık"),
    ("Konya", "Emre", 34.5, 67.1, "order", ("cipso", "gypsophila"), "toptan yapay cipso", "cipso"),
    ("Gaziantep", "Selin", 60.3, 79.2, "order", ("okaliptus",), "toptan yapay okaliptus", "okaliptus"),
    ("Erzurum", "Can", 80.7, 36.4, "order", ("sarmasik",), "toptan yapay sarmaşık", "sarmaşık"),
    ("Fatsa", None, 60.9, 19.2, "ship", ("bitki",), "toptan yapay bitki", "bitki"),
    ("Midyat", None, 81.0, 73.9, "ship", ("agac",), "toptan yapay ağaç", "ağaç"),
    ("Safranbolu", None, 35.6, 15.9, "ship", ("aranjman",), "toptan yapay aranjman", "aranjman"),
    ("Ürgüp", None, 47.3, 55.6, "ship", ("kadife",), "toptan kadife gül", "kadife gül"),
    ("Kars", None, 90.2, 25.6, "ship", ("gul",), "toptan 7li yapay gül demeti", "7li gül demeti"),
]


def _find_category_slug(categories, tokens):
    """En iyi eşleşen kategori slug'ı (tam eşleşme > başlangıç > içerir)."""
    best_slug, best_score = None, 0
    for cat in categories:
        slug = cat.slug or turkish_slugify(cat.name)
        for token in tokens:
            if slug == token:
                score = 3
            elif slug.startswith(token):
                score = 2
            elif token in slug:
                score = 1
            else:
                continue
            if score > best_score:
                best_slug, best_score = slug, score
    return best_slug


def _turkey_map_notifications(categories):
    items = []
    for city, who, x, y, kind, tokens, text, fallback_q in TURKEY_MAP_NOTIFICATIONS:
        slug = _find_category_slug(categories, tokens)
        if slug:
            url = reverse("products:by_category", args=[slug])
        else:
            url = f"{reverse('products:list')}?q={quote(fallback_q)}"
        items.append({
            "city": city,
            "who": who,
            "kind": kind,
            "text": text,
            "url": url,
            # Python float -> str: tr yerelinde şablon "16,2" yazıp CSS'i bozmasın.
            "x": f"{x:.1f}",
            "y": f"{y:.1f}",
            # Balon, noktanın hangi tarafına açılsın (harita dışına taşmasın).
            "h": "l" if x > 50 else "r",
            "v": "down" if y < 28 else "up",
        })
    return items


def nav_categories(request):
    """
    Exposes {{ nav_categories }} to every template (header nav needs the
    category list on literally every page, not just the product list
    views). Runs one cheap query per request; fine at the category counts
    a shop like this has (tens, not thousands).

    Also exposes {{ shop_whatsapp_display }}: the same number used for the
    WhatsApp order-notification API (WHATSAPP_ADMIN_PHONE, e.g. "905XXXXXXXXX"),
    reused here so the header/footer show your real number instead of a
    hardcoded placeholder. Falls back to a clearly-marked placeholder string
    if that setting isn't configured yet.

    Also exposes {{ turkey_map_notifications }} for the pre-footer Turkey map
    (see TURKEY_MAP_NOTIFICATIONS above). It reuses the same category list, so
    it adds no extra query.
    """
    raw_phone = settings.WHATSAPP_ADMIN_PHONE
    categories = list(Category.objects.all())
    return {
        "nav_categories": categories,
        "shop_whatsapp_display": raw_phone or "+90 5xx xxx xx xx",
        "turkey_map_notifications": _turkey_map_notifications(categories),
    }
