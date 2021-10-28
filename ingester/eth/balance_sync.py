from django.conf import settings
from celery import task
from celery_once import QueueOnce

from tracker.models import AccountBalance, Address, ERC20Token

from common.utils.networks import ETH
from common.utils.requests import http
from common.utils.utils import current_time_millis

import logging
import os

logger = logging.getLogger('watchtower.ingester.tasks')

@task(base=QueueOnce, once={'graceful': True})
def sync_eth_account_balances(address, include_tokens=True):
    logger.info('sync_eth_account_balances: %s, include_tokens = %s', address, include_tokens)
    start = current_time_millis()
    params = {
        'action': 'balance',
        'address': address,
        'apikey': 'watchtower-' + settings.ENV,
    }

    address_obj = Address.objects.get(address=address, account__network=ETH)
    account = address_obj.account
    try:
        res = http.get(os.getenv('COINQUERY_ETH_URL'), params)
        data = res.json_data
        balance = data.get('result')

        account_balance_obj, ab_created = AccountBalance.objects.update_or_create(
            account=account,
            address=address,
            network=ETH,
            symbol=ETH,
            identifier=address,
            balance_type='R',
            defaults={
                'balance': balance
            }
        )

        logger.debug('created (ETH) = %s, account_balance = %s', ab_created, balance)
    except Exception as e:
        logger.error('failed to GET ETH balance from %s: %s', os.getenv('COINQUERY_ETH_URL'), str(e))

    if include_tokens:
        try:
            supported_tokens = list(ERC20Token.objects.filter(supported=True))
            for token in supported_tokens:
                # run the token syncs in their own tasks, otherwise we're over 30 seconds in sync time per account
                sync_eth_token_balance.s(account.id, address, token.symbol, token.contract_address).apply_async()
                logger.debug('queued token %s for account %s', token.symbol, address)
        except Exception as e:
            logger.error('failed to GET ETH token balances from %s: %s', os.getenv('COINQUERY_ETH_URL'), str(e))

    logger.info('Performed balance sync for eth account %s in %sms', address, (current_time_millis()) - start)

@task(base=QueueOnce, once={'graceful': True})
def sync_eth_token_balance(account_id, address, symbol, contract_address):
    logger.info('sync_eth_token_balance: %s, symbol = %s, contract = %s', address, symbol, contract_address)
    params = {
        'action': 'tokenbalance',
        'contractaddress': contract_address,
        'address': address,
        'apikey': 'watchtower-' + settings.ENV,
    }
    res = http.get(os.getenv('COINQUERY_ETH_URL'), params)
    data = res.json_data

    balance = data.get('result')

    if balance != '0':
        account_balance_obj, ab_created = AccountBalance.objects.update_or_create(
            account_id=account_id,
            address=address,
            network=ETH,
            symbol=symbol,
            identifier=contract_address,
            balance_type='R',
            defaults={
                'balance': balance
            }
        )
        logger.debug('created (%s) = %s, account_balance = %s', symbol, ab_created, balance)
    else:
        # need to do plain update here to set any existing balance for this token to 0
        update_count = AccountBalance.objects.filter(
            account_id=account_id,
            address=address,
            network=ETH,
            symbol=symbol,
            identifier=contract_address,
            balance_type='R'
        ).update(balance=0)
        logger.debug('%s: update count = %s, account_balance = %s', address, update_count, balance)
