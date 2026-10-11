from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Phone becomes the real identity (login/register no longer use email at
    all); email is kept as an unused, non-unique column since AbstractUser
    defines it, but nothing reads or writes it anymore.

    ⚠️ Run this only after checking for duplicate/blank `phone` values on
    production — the new UNIQUE constraint on `phone` will fail to apply if
    any two rows share a value (this includes multiple blank "" rows, most
    likely stale unverified registrations). A quick check before migrating:

        python manage.py shell -c "
        from apps.accounts.models import User
        from django.db.models import Count
        dupes = (User.objects.values('phone')
                 .annotate(c=Count('id')).filter(c__gt=1))
        print(list(dupes))
        "

    If that prints anything, delete/fix those rows first (inactive rows with
    a blank/duplicate phone are almost always abandoned, never-verified
    registrations and are safe to delete).
    """

    dependencies = [
        ("accounts", "0006_alter_user_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="email address"),
        ),
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(max_length=20, unique=True, verbose_name="Telefon"),
        ),
    ]
