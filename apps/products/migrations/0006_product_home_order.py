from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_pricetier_price_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="home_order",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Display position in homepage sections (1 = first). Leave blank for automatic order.",
            ),
        ),
    ]
