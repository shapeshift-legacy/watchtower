from celery import task
from celery_once import QueueOnce

from tracker.models import AccountBalance, Address
from common.services import binance_client
from common.utils.networks import BNB
from common.utils.utils import current_time_millis

import logging

logger = logging.getLogger('watchtower.ingester.bnb.common')

@task(base=QueueOnce, once={'graceful': True})
def sync_bnb_account_balances(address):
    logger.info('syncing bnb account balances for %s', address)
    start = current_time_millis()
    address_obj = Address.objects.get(address=address, account__network=BNB)
    account = address_obj.account

    balance = binance_client.get_balance(address)

    AccountBalance.objects.update_or_create(
        account=account,
        address=address,
        network=BNB,
        symbol=BNB,
        identifier=address,
        balance_type='R',
        defaults={
            'balance': balance
        }
    )

    logger.info('synced bnb balances for %s, balance = %s in %sms',
                address, balance, (current_time_millis() - start))
