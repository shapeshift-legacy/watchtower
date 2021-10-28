from celery import task
from celery_once import QueueOnce

from tracker.models import AccountBalance, Address
from common.services import fio
from common.utils.networks import FIO
from common.utils.utils import current_time_millis

import logging

logger = logging.getLogger('watchtower.ingester.fio.common')

@task(base=QueueOnce, once={'graceful': True})
def sync_fio_account_balances(address):
    logger.info('syncing fio account balances for %s', address)
    start = current_time_millis()
    address_obj = Address.objects.get(address=address, account__network=FIO)
    account = address_obj.account

    balance = fio.get_balance(address)

    AccountBalance.objects.update_or_create(
        account=account,
        address=address,
        network=FIO,
        symbol=FIO,
        identifier=address,
        balance_type='R',
        defaults={
            'balance': balance
        }
    )

    logger.info('synced fio balances for %s, balance = %s in %sms',
                address, balance, (current_time_millis() - start))
