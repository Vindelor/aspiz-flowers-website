from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0007_section_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="product", name="seo_title",
            field=models.CharField(
                "SEO title", max_length=70, blank=True,
                help_text="<title> etiketi. Boşsa: '<ürün adı> | ASPIZ FLOWERS'. İdeal: 50-60 karakter."),
        ),
        migrations.AddField(
            model_name="product", name="meta_description",
            field=models.CharField(
                max_length=200, blank=True,
                help_text="Google sonuçlarında görünen açıklama. İdeal: 120-160 karakter."),
        ),
        migrations.AddField(
            model_name="product", name="seo_h1",
            field=models.CharField(
                "H1 (sayfa başlığı)", max_length=200, blank=True,
                help_text="Ürün sayfasındaki ana başlık. Boşsa ürün adı kullanılır."),
        ),
        migrations.AlterField(
            model_name="product", name="description",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Ürün açıklaması. Boş satırla paragraf ayırın. '## Başlık' ile alt başlık (H2), "
                    "[bağlantı metni](/products/category/yesillikler/) ile iç link ekleyebilirsiniz."
                )),
        ),
        migrations.AddField(
            model_name="productimage", name="alt_text",
            field=models.CharField(
                "ALT metni", max_length=200, blank=True,
                help_text="Görselin kısa açıklaması (SEO + erişilebilirlik). Boşsa ürün adı kullanılır."),
        ),
    ]
