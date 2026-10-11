from django.db import migrations, models


def dedupe_phones(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    db = schema_editor.connection.alias
    users = User.objects.using(db)

    # Blank phones (legacy email-only accounts): every one gets a placeholder.
    for pk in users.filter(phone="").values_list("pk", flat=True):
        users.filter(pk=pk).update(phone=f"x{pk}")

    # Exact duplicates: keep the best account on the number (active first,
    # then most recently logged in, then newest), placeholder the rest.
    seen = set()
    ordered = users.exclude(phone__startswith="x").order_by(
        "phone", "-is_active", models.F("last_login").desc(nulls_last=True), "-pk"
    )
    for pk, phone in ordered.values_list("pk", "phone"):
        if phone in seen:
            users.filter(pk=pk).update(phone=f"x{pk}")
        else:
            seen.add(phone)


def drop_email_unique_if_present(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    table = User._meta.db_table
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    has_unique = any(
        c["unique"] and not c["primary_key"] and c["columns"] == ["email"]
        for c in constraints.values()
    )
    if not has_unique:
        return
    old_field = User._meta.get_field("email")
    new_field = models.EmailField(blank=True, max_length=254, verbose_name="email address")
    new_field.set_attributes_from_name("email")
    new_field.model = User
    schema_editor.alter_field(User, old_field, new_field)


class Migration(migrations.Migration):
    """
    Phone becomes the real identity (login/register no longer use email at
    all); email is kept as an unused, non-unique column since AbstractUser
    defines it, but nothing reads or writes it anymore.

    Before the UNIQUE constraint on `phone` is added, existing rows that
    would violate it are fixed automatically (see `dedupe_phones`):
    accounts created under the old email login have a blank phone, and a
    few may share the same number. Those rows get a placeholder phone
    ("x<id>") instead of being deleted, so no account or order history is
    lost. Placeholders contain a letter, so they never match a real
    number at login — staff can fill in the real phone from the admin.

    The email step is idempotent: MySQL can't roll back DDL, so an earlier
    failed run of this migration may already have dropped the email
    UNIQUE index. It's only dropped here if it still exists.
    """

    dependencies = [
        ("accounts", "0006_alter_user_options"),
    ]

    operations = [
        migrations.RunPython(
            dedupe_phones,
            migrations.RunPython.noop,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    drop_email_unique_if_present,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="user",
                    name="email",
                    field=models.EmailField(blank=True, max_length=254, verbose_name="email address"),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(max_length=20, unique=True, verbose_name="Telefon"),
        ),
    ]
