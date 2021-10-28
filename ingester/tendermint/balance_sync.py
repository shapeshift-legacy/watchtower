from celery import task
from celery_once import QueueOnce

from tracker.models import AccountBalance, Address
from common.services import get_gaia_client
from common.utils.utils import current_time_millis

import logging

logger = logging.getLogger('watchtower.ingester.tendermint.common')

@task(base=QueueOnce, once={'graceful': True})
def sync_account_balances(network, address):
    logger.info('syncing %s account balances for %s', network, address)
    start = current_time_millis()
    address_obj = Address.objects.get(address=address, account__network=network)
    account = address_obj.account
    gaia = get_gaia_client(network)
    balance = gaia.get_balance(address)

    AccountBalance.objects.update_or_create(
        account=account,
        address=address,
        network=network,
        symbol=network,
        identifier=address,
        balance_type='R',
        defaults={
            'balance': balance
        }
    )

    logger.info('synced %s balances for %s, balance = %s in %sms',
                network, address, balance, (current_time_millis() - start))
