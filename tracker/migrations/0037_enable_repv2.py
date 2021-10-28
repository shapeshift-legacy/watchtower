from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0036_enable_ht_husd_gusd_link_paxg_knc'),
    ]

    operations = [

        # repv2
        migrations.RunSQL(
            """
                update tracker_erc20token
                set supported = true
                where lower(contract_address) in (
                lower('0x221657776846890989a759BA2973e427DfF5C9bB'));
            """
        )
    ]
