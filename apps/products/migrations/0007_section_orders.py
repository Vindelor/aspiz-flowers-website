from django.db import migrations, models


def _f(text):
    return models.PositiveIntegerField(blank=True, null=True, help_text=text)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_product_home_order"),
    ]

    operations = [
        migrations.RemoveField(model_name="product", name="home_order"),
        migrations.AddField(
            model_name="product", name="popular_order",
            field=_f("Position in the Popular section (1 = first). Blank = automatic."),
        ),
        migrations.AddField(
            model_name="product", name="new_order",
            field=_f("Position in the New Products section (1 = first). Blank = automatic."),
        ),
        migrations.AddField(
            model_name="product", name="deal_order",
            field=_f("Position in the Deals section (1 = first). Blank = automatic."),
        ),
        migrations.AddField(
            model_name="product", name="badge_order",
            field=_f("Position in its badge section: Editor's Choice / New Season / Special Series / Low Stock (1 = first). Blank = automatic."),
        ),
    ]
