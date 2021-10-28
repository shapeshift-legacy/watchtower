from celery import task
from celery_once import QueueOnce

from tracker.models import AccountBalance, Address
from common.services import ripple
from common.utils.networks import XRP
from common.utils.utils import current_time_millis

import logging

logger = logging.getLogger('watchtower.ingester.xrp.common')

@task(base=QueueOnce, once={'graceful': True})
def sync_xrp_account_balances(address):
    logger.info('syncing xrp account balances for %s', address)
    start = current_time_millis()
    address_obj = Address.objects.get(address=address, account__network=XRP)
    account = address_obj.account

    balance = ripple.get_balance(address)
    if balance is None:
        balance = 0
    
    AccountBalance.objects.update_or_create(
        account=account,
        address=address,
        network=XRP,
        symbol=XRP,
        identifier=address,
        balance_type='R',
        defaults={
            'balance': balance
        }
    )

    logger.info('synced xrp balances for %s, balance = %s in %sms',
                address, balance, (current_time_millis() - start))
