from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0018_indexaddress'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW tracker_totals_v AS
            SELECT xpub.network asset, SUM(bc.amount) / (10 ^ 8) total, false as erc20_token
            FROM tracker_xpub xpub
                   JOIN tracker_transaction tx ON xpub.id = tx.xpub_id
                   JOIN tracker_balancechange bc ON xpub.id = bc.xpub_id AND tx.id = bc.transaction_id
                   JOIN tracker_address addr ON bc.address_id = addr.id
            WHERE xpub.network != 'ETH'
            GROUP BY xpub.network
            UNION ALL
            SELECT 'ETH', SUM(bc.amount) / (10 ^ 18), false
            FROM tracker_xpub xpub
                   JOIN tracker_transaction tx ON xpub.id = tx.xpub_id
                   JOIN tracker_balancechange bc ON xpub.id = bc.xpub_id AND tx.id = bc.transaction_id
                   JOIN tracker_address addr ON bc.address_id = addr.id
            WHERE xpub.network = 'ETH'
              AND NOT tx.is_erc20_token_transfer
            UNION ALL
            SELECT erc20.symbol, SUM(bc.amount) / (10 ^ erc20.precision), true
            FROM tracker_xpub xpub
                   JOIN tracker_transaction tx ON xpub.id = tx.xpub_id
                   JOIN tracker_balancechange bc ON xpub.id = bc.xpub_id AND tx.id = bc.transaction_id
                   JOIN tracker_address addr ON bc.address_id = addr.id
                   JOIN tracker_erc20token erc20 ON tx.erc20_token_id = erc20.id
            WHERE xpub.network = 'ETH'
              AND tx.is_erc20_token_transfer
            GROUP BY erc20.symbol, erc20.precision
            """
        )
    ]
