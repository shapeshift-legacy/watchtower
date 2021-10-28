from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0037_enable_repv2'),
    ]

    operations = [

        # repv2
        migrations.RunSQL(
            """
                update tracker_erc20token
                set supported = true
                where lower(contract_address) in (
                lower('0xba100000625a3754423978a60c9317c58a424e3D'),
                lower('0xc00e94cb662c3520282e6f5717214004a7f26888')
                );
            """
        )
    ]
