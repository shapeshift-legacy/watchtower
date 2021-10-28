from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0026_rename_xpub_field_to_account'),
    ]

    operations = [
        migrations.RunSQL(
            """
            DROP VIEW tracker_totals_v
            """
        )
    ]
