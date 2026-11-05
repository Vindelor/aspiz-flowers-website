"""
Yeşillikler sayfası için hazırlanan SEO içeriğini (SEO title, meta description,
H1, ürün açıklaması, görsel ALT metinleri) ürünlere yazar.

Kullanım:
    python manage.py load_seo_yesillikler --dry-run   # sadece ne yapacağını göster
    python manage.py load_seo_yesillikler             # gerçekten yaz

Ürünler slug ile bulunur (URL'deki son kısım). Bulunamayan ürün atlanır ve
raporlanır. Komut tekrar çalıştırılabilir (aynı değerleri yeniden yazar).
ALT metinleri, ürünün görsellerine "order" sırasıyla (aynıysa id sırasıyla) atanır.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import Product

SEO_DATA = [
    {
        "slug": "yapay-cicek-luks-okaliptus-demeti-45-cm-16li",
        "seo_title": "16’lı Yapay Okaliptüs Demeti 45 cm | ASPIZ FLOWERS",
        "meta_description": "45 cm uzunluğundaki 16’lı yapay okaliptüs demetini inceleyin. Oval yapraklı dallarıyla buket ve dekoratif aranjman çalışmalarında kullanılabilir.",
        "seo_h1": "Yapay Okaliptüs Demeti 45 cm – 16’lı",
        "description": (
            "## 45 cm 16’lı Yapay Okaliptüs Demeti\n\n"
            "45 cm uzunluğundaki 16’lı yapay okaliptüs demeti, yuvarlak ve oval yaprak formuyla dekoratif çiçek düzenlemelerinde kullanılabilecek bir üründür. Bir arada sunulan dallar, buket ve farklı çiçek kompozisyonlarına hacim kazandıran tamamlayıcı bir görünüm oluşturur.\n\n"
            "Okaliptüs yapraklarının karakteristik yuvarlak formu, ürünü klasik çiçek demetlerinden ayıran temel görsel özelliktir. Dallar tek başına bir vazoda sergilenebileceği gibi farklı yapay çiçeklerle birlikte aranjman çalışmalarında da değerlendirilebilir.\n\n"
            "45 cm ölçüsü ve 16’lı ürün bilgisi, seçim yaparken dikkate alınabilecek temel özelliklerdir. Ürünün yaprak görünümünü, dal yapısını ve genel formunu fotoğraflar üzerinden inceleyerek dekoratif tasarımınıza uygunluğunu değerlendirebilirsiniz.\n\n"
            "Farklı bir yaprak görünümüne sahip okaliptüs modeli arayanlar, 80 cm uzunluğundaki [koyu yeşil ve yoğun yapraklı yapay okaliptüs modelini](/products/yapay-cicek-yogun-yaprakli-koyu-yesil-okaliptus-sa/) de inceleyebilir."
        ),
        "alts": [
            "45 cm 16’lı yapay okaliptüs demetinin oval yapraklı dalları",
            "Yapay okaliptüs demetindeki yuvarlak yaprakların yakın görünümü",
            "45 cm yapay okaliptüs dallarının beyaz vazoda sergilenmiş görünümü",
        ],
    },
    {
        "slug": "yapay-bitki-7-dalli-yildiz-cimi-demeti-_-yesillik",
        "seo_title": "7 Dallı Yapay Yıldız Çimi 44 cm | ASPIZ FLOWERS",
        "meta_description": "44 cm yüksekliğindeki 7 dallı yapay yıldız çimi demetini keşfedin. İnce yapraklı formu ve kolay temizlenebilir yüzeyiyle ürün detaylarını inceleyin.",
        "seo_h1": "7 Dallı Yapay Yıldız Çimi Demeti 44 cm",
        "description": (
            "## 44 cm 7 Dallı Yapay Yıldız Çimi Demeti\n\n"
            "44 cm yüksekliğindeki 7 dallı yapay yıldız çimi demeti, ince ve uzun yaprak formuyla dekoratif bitki düzenlemelerinde kullanılabilecek bir modeldir. Bir arada bulunan yapraklı dallar, vazolarda veya farklı dekoratif düzenlemelerde doğal çim görünümünü yansıtan bir form oluşturur.\n\n"
            "Ürünün ince yaprak yapısı, geniş ve iri yapraklı yapay bitki modellerinden ayrılmasını sağlar. Bu görünüm sayesinde farklı bitki ve çiçek modelleriyle birlikte değerlendirilebilir.\n\n"
            "Ürün görsellerinde belirtilen bilgilere göre model kumaş dokulu bir yüzeye sahiptir ve su veya nemli bir bezle temizlenebilir. Sulama gerektirmeyen yapısı, gerçek bitkilerdeki düzenli bakım ihtiyacını ortadan kaldırır.\n\n"
            "7 dal ve 44 cm ölçüsü, ürün seçiminde dikkate alınabilecek temel özelliklerdir. Sipariş öncesinde ürün görsellerini inceleyerek modelin formunu ve ölçüsünü değerlendirebilirsiniz.\n\n"
            "Farklı bitki modellerini karşılaştırmak isteyenler, [Yeşillikler kategorisindeki diğer ürünleri](/products/category/yesillikler/) de inceleyebilir."
        ),
        "alts": [
            "44 cm yedi dallı yapay yıldız çimi demetinin vazoda görünümü",
            "Yapay yıldız çimi özellikleri, 7 dal ve 44 cm ölçü bilgisi",
        ],
    },
    {
        "slug": "yapay-cicek-yogun-yaprakli-koyu-yesil-okaliptus-sa",
        "seo_title": "80 cm Koyu Yeşil Yapay Okaliptüs | ASPIZ FLOWERS",
        "meta_description": "Yoğun ve koyu yeşil yaprak görünümüne sahip 80 cm yapay okaliptüs modelini inceleyin. Ürün görsellerinde ölçü ve ağırlık bilgileri yer alır.",
        "seo_h1": "Yoğun Yapraklı Koyu Yeşil Yapay Okaliptüs 80 cm",
        "description": (
            "## 80 cm Yoğun Yapraklı Koyu Yeşil Yapay Okaliptüs\n\n"
            "Yoğun yapraklı koyu yeşil yapay okaliptüs modeli, aşağı doğru uzanan dalları ve sık yaprak görünümüyle dekoratif bitki düzenlemeleri için tasarlanmış bir üründür. Yaprakların yoğun biçimde bir araya gelmesi, ürüne dolgun bir görünüm kazandırır.\n\n"
            "80 cm ölçüsündeki model, sarkıt formuyla klasik dik duran bitki seçeneklerinden ayrılır. Dalları aşağı doğru uzanan yapısı sayesinde duvar, raf ve benzeri dekoratif alanlarda değerlendirilebilecek farklı bir görünüm sunar.\n\n"
            "Ürünün koyu yeşil yaprak formu, fotoğraflarda ayrıntılı biçimde görülebilir. Ölçü ve ağırlık bilgilerini de inceleyerek dekorasyonunuz için uygun olup olmadığını değerlendirebilirsiniz.\n\n"
            "Daha toplu ve demet formunda bir okaliptüs modeli arayanlar, [45 cm uzunluğundaki 16’lı yapay okaliptüs demetini](/products/yapay-cicek-luks-okaliptus-demeti-45-cm-16li/) de inceleyebilir."
        ),
        "alts": [
            "80 cm koyu yeşil yoğun yapraklı yapay okaliptüs bitkisi",
        ],
    },
    {
        "slug": "yapay-luks-18li-starlice-agaci-80-cm",
        "seo_title": "18’li Yapay Starliçe 80 cm | ASPIZ FLOWERS",
        "meta_description": "80 cm boyundaki 18’li yapay Starliçe modelinin geniş yapraklı görünümünü inceleyin. Ürün ölçülerini ve görsellerini değerlendirin.",
        "seo_h1": "18’li Yapay Starliçe Ağacı 80 cm",
        "description": (
            "## 18’li Yapay Starliçe Ağacı 80 cm\n\n"
            "80 cm yüksekliğindeki 18’li yapay Starliçe modeli, geniş ve dikkat çekici yaprak formuyla dekoratif bitki seçenekleri arasında yer alır. Yaprakların yukarı doğru uzanan ve genişleyen görünümü, ürüne belirgin bir bitki formu kazandırır.\n\n"
            "Starliçe görünümündeki bu model, klasik küçük yapraklı dekoratif bitkilerden farklı bir silüete sahiptir. Bu nedenle tek başına sergilendiğinde de bulunduğu alanda belirgin bir yeşil bitki görünümü oluşturabilir.\n\n"
            "Ürünün 80 cm ölçüsü ve 18’li model bilgisi, seçim sırasında değerlendirilmesi gereken temel özelliklerdir. Yaprak formunu ve genel görünümünü ürün fotoğraflarından inceleyerek dekorasyon düzenlemenize uygunluğunu değerlendirebilirsiniz.\n\n"
            "Farklı yaprak formuna sahip bitki seçeneklerini karşılaştırmak isteyenler, [Yeşillikler kategorisindeki diğer ürünleri](/products/category/yesillikler/) inceleyebilir."
        ),
        "alts": [
            "80 cm yapay Starliçe bitkisinin saksı içinde sergilenmiş görünümü",
            "18li yapay Starliçe bitkisinin 80 cm ölçüsünü gösteren ürün fotoğrafı",
        ],
    },
    {
        "slug": "yapay-cicek-teli-36-cm-_-40-cm-aranjman-yapimi-sap",
        "seo_title": "Yeşil Çiçek Teli 36–40 cm | ASPIZ FLOWERS",
        "meta_description": "Aranjman hazırlığında kullanılabilen yeşil çiçek teli modelini inceleyin. Ürün sayfasında 36 cm ve 40 cm bilgilerine göz atın.",
        "seo_h1": "Aranjman Yapımı İçin Yeşil Çiçek Teli",
        "description": (
            "## Aranjman Yapımı İçin Yeşil Çiçek Teli\n\n"
            "Yeşil çiçek teli, yapay çiçek aranjmanlarının hazırlanması ve çiçek saplarının düzenlenmesi sırasında kullanılabilecek yardımcı bir malzemedir. Düz formdaki yapısı, farklı çiçek ve dekoratif parçaların bir araya getirildiği tasarım çalışmalarında değerlendirilmesini sağlar.\n\n"
            "Aranjman hazırlayan çiçekçiler, dekorasyon firmaları ve el işi çalışmaları yapan kullanıcılar için ürünün uzunluğu ve kullanım amacı önemlidir. Yeşil görünümü, çiçek sapları ve bitki parçalarıyla birlikte kullanıldığında düzenlemenin genel görünümüne uyum sağlamasına yardımcı olur.\n\n"
            "Ürün adında 36 cm ve 40 cm ölçüleri belirtilmiştir. Sipariş öncesinde mevcut ölçü seçeneklerini ve ürün detaylarını kontrol ederek ihtiyacınıza uygun modeli tercih edebilirsiniz.\n\n"
            "Aranjman çalışmalarında kullanılabilecek farklı yapay çiçek ve buket seçeneklerini görmek isteyenler, [Aranjmanlar kategorisindeki ürünleri](/products/category/aranjmanlar/) inceleyebilir."
        ),
        "alts": [
            "Yeşil çiçek tellerinin demet hâlinde görünümü",
            "Aranjman yapımında kullanılan düz yeşil çiçek telleri",
            "Yeşil çiçek tellerinin yakın görünümü",
        ],
    },
    {
        "slug": "yapay-cicek-ask-merdiveni-egrelti-otu-bitkisi-12-y",
        "seo_title": "Yapay Aşk Merdiveni 35 cm – 12 Yaprak | ASPIZ FLOWERS",
        "meta_description": "35 cm boyundaki yapay Aşk Merdiveni modelinin ürün görsellerini ve detaylarını inceleyin. Buket ve dekoratif düzenlemelerde kullanıma yönelik bir seçenektir.",
        "seo_h1": "Yapay Aşk Merdiveni 35 cm – 12 Yaprak",
        "description": (
            "## 35 cm Yapay Aşk Merdiveni Bitkisi\n\n"
            "35 cm boyundaki yapay Aşk Merdiveni modeli, ince ve çok parçalı yaprak formuyla dekoratif bitki düzenlemelerinde kullanılabilecek bir seçenektir. Bitkinin dallanan görünümü, küçük ölçekli aranjmanlarda ve farklı yapay bitki modelleriyle birlikte hazırlanan tasarımlarda değerlendirilebilir.\n\n"
            "Aşk Merdiveni formu, klasik geniş yapraklı bitki modellerinden farklı bir görünüm sunar. Bu özellik, ürünü buket ve dekoratif düzenlemelerde tamamlayıcı bir bitki seçeneği hâline getirir.\n\n"
            "Ürünün 35 cm ölçüsü, özellikle daha kısa bitki modellerini tercih eden kullanıcıların seçim yaparken dikkate alabileceği bir özelliktir. Ürün fotoğraflarını inceleyerek yaprak formunu ve genel görünümünü değerlendirebilirsiniz.\n\n"
            "Daha uzun bir alternatif arayanlar, 55 cm ölçüsündeki 18 yapraklı [Aşk Merdiveni modelini](/products/yapay-cicek-ask-merdiveni-egrelti-otu-bitkisi-18-y/) de inceleyebilir."
        ),
        "alts": [
            "35 cm yapay Aşk Merdiveni bitkisinin yaprak formu",
        ],
    },
    {
        "slug": "yapay-cicek-ask-merdiveni-egrelti-otu-bitkisi-18-y",
        "seo_title": "Yapay Aşk Merdiveni 55 cm – 18 Yaprak | ASPIZ FLOWERS",
        "meta_description": "55 cm boyundaki yapay Aşk Merdiveni modelini inceleyin. Yaprak formu ve ürün görselleri, dekoratif düzenlemeler için model seçimini kolaylaştırır.",
        "seo_h1": "Yapay Aşk Merdiveni 55 cm – 18 Yaprak",
        "description": (
            "## 55 cm Yapay Aşk Merdiveni Bitkisi\n\n"
            "55 cm boyundaki yapay Aşk Merdiveni modeli, genişleyen yaprak görünümü ve dallı formuyla dekoratif düzenlemelerde değerlendirilebilecek bir bitkidir. Ürünün yaprak yapısı, bulunduğu alanda daha dolgun bir bitki görünümü oluşturmasına yardımcı olur.\n\n"
            "Aşk Merdiveni formu, farklı yapay bitki ve çiçek modelleriyle birlikte kullanılabilecek bir dekorasyon seçeneğidir. Buket hazırlığı, vitrin düzenlemesi ve çeşitli dekoratif tasarımlarda diğer bitkilerle birlikte değerlendirilebilir.\n\n"
            "Ürünün 55 cm ölçüsü, bu modeli daha kısa bitki seçeneklerinden ayıran temel özelliklerden biridir. Fotoğraflarda gösterilen yaprak formunu ve genel yayılımını inceleyerek ürünün kullanım alanınıza uygunluğunu değerlendirebilirsiniz.\n\n"
            "Daha kısa bir seçenek arayanlar, 35 cm ölçüsündeki 12 yapraklı [Aşk Merdiveni modelini](/products/yapay-cicek-ask-merdiveni-egrelti-otu-bitkisi-12-y/) inceleyebilir."
        ),
        "alts": [
            # NOT: 1. ALT'ta "90 cm yayılım" yazıyor (ürün 55 cm). Görselde gerçekten
            # 90 cm yazıyorsa bırakın, değilse düzeltin.
            "Yapay Aşk Merdiveni yapraklarının 90 cm yayılım ölçüsünü gösteren ürün görseli",
            "Yapay Aşk Merdiveni modelinin elde tutularak gösterimi",
            "Yapay Aşk Merdiveni bitkisinin yaprak ve dal yapısını gösteren ürün fotoğrafı",
        ],
    },
]


class Command(BaseCommand):
    help = "Yeşillikler ürünlerinin SEO içeriğini (title, meta, H1, açıklama, ALT) yazar."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Hiçbir şey yazmadan sadece raporla.")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        updated, missing = 0, []

        for item in SEO_DATA:
            try:
                product = Product.objects.prefetch_related("images").get(slug=item["slug"])
            except Product.DoesNotExist:
                missing.append(item["slug"])
                self.stdout.write(self.style.ERROR(f"BULUNAMADI: {item['slug']}"))
                continue

            product.seo_title = item["seo_title"]
            product.meta_description = item["meta_description"]
            product.seo_h1 = item["seo_h1"]
            product.description = item["description"]

            images = sorted(product.images.all(), key=lambda i: (i.order, i.id))
            alts = item["alts"]
            note = ""
            if len(images) != len(alts):
                note = f"  ⚠ {len(images)} görsel var, {len(alts)} ALT metni verildi"

            self.stdout.write(f"{'[dry-run] ' if dry else ''}OK: {product.name}  ({len(images)} görsel){note}")

            if not dry:
                product.save()
                for img, alt in zip(images, alts):
                    img.alt_text = alt
                    img.save(update_fields=["alt_text"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"\n{updated} ürün {'kontrol edildi' if dry else 'güncellendi'}."))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"{len(missing)} ürün bulunamadı — slug'ı admin'de kontrol edin:\n  " + "\n  ".join(missing)))
