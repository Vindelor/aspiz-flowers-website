from django.db import migrations


class Migration(migrations.Migration):
    """
    0005 swapped EmailLoginCode for LoginCode only in Django's *state*; the
    old table `accounts_emaillogincode` stayed in the database, still with a
    real FOREIGN KEY to accounts_user and no ON DELETE rule.

    Result: deleting a never-verified user that still had an old e-mail-era
    code row (register_view does exactly that when someone re-registers the
    same phone) raised IntegrityError 1451 -> HTTP 500, and the person could
    never register that number.

    The table holds only expired one-time e-mail codes from the retired
    e-mail login, so it is dropped. Irreversible on purpose (nothing to
    restore).
    """

    dependencies = [
        ("accounts", "0007_phone_only_auth"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS `accounts_emaillogincode`",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
