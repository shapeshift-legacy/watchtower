from celery import task
from celery_once import QueueOnce

from tracker.models import AccountBalance, Address
from common.services import eos_client
from common.utils.networks import EOS
from common.utils.utils import current_time_millis

import logging

logger = logging.getLogger('watchtower.ingester.eos.common')

@task(base=QueueOnce, once={'graceful': True})
def sync_eos_account_balances(address):
    logger.info('syncing eos account balances for %s', address)
    start = current_time_millis()
    address_obj = Address.objects.get(address=address, account__network=EOS)
    account = address_obj.account

    balance = eos_client.get_account_balance(address)

    AccountBalance.objects.update_or_create(
        account=account,
        address=address,
        network=EOS,
        symbol=EOS,
        identifier=address,
        balance_type='R',
        defaults={
            'balance': balance
        }
    )

    logger.info('synced eos balances for %s, balance = %s in %sms',
                address, balance, (current_time_millis() - start))
