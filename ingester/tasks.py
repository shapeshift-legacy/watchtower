from datetime import datetime, timezone
from decimal import Decimal

from celery import task
from celery_once import QueueOnce

from api.rest.v1.data.transactions import fetcher as tx_fetcher

from ingester.eth import eth_block_ingester
from ingester.eth.balance_sync import sync_eth_account_balances
from ingester.tendermint import atom_block_ingester, rune_block_ingester, scrt_block_ingester, kava_block_ingester, osmo_block_ingester
from ingester.tendermint.balance_sync import sync_account_balances
from ingester.bnb import bnb_block_ingester
from ingester.bnb.balance_sync import sync_bnb_account_balances
from ingester.xrp import xrp_block_ingester
from ingester.xrp.balance_sync import sync_xrp_account_balances
from ingester.eos import eos_block_ingester
from ingester.eos.balance_sync import sync_eos_account_balances
from ingester.fio import fio_block_ingester
from ingester.fio.balance_sync import sync_fio_account_balances
from tracker.models import Account, Address, Transaction, BalanceChange, ProcessedBlock, ERC20Token
from common.services import thorchain
from common.services.coinquery import get_client as get_coinquery_client
from common.services.gaia_tendermint import get_client as get_gaia_client
from common.services.redis import redisClient, WATCH_ADDRESS_PREFIX, WATCH_ADDRESS_SET_KEY, WATCH_TX_SET_KEY
from common.services.rabbitmq import RabbitConnection, EXCHANGE_TXS, EXCHANGE_BLOCKS, EXCHANGE_NOTIFICATIONS
from common.utils.bip32 import GAP_LIMIT
from common.utils.ethereum import calculate_balance_change, calculate_dex_balance_change, \
    calculate_ethereum_transaction_fee
from common.utils.ethereum import gen_get_all_ethereum_transactions, gen_get_all_internal_ethereum_transactions, \
    gen_get_all_token_transactions
from common.utils.ethereum import get_balance as get_eth_balance
from common.utils.ethereum import get_token_balance as get_eth_token_balance
from common.utils.ethereum import ETHEREUM_DECIMAL_PRECISION, ETH_MAX_TXS
from common.utils.networks import ATOM, ETH, DOGE, BNB, XRP, EOS, FIO, RUNE, KAVA, SCRT, OSMO
from common.services import binance_client, eos_client, ripple, fio
from common.utils.cosmos import calculate_balance_change as cosmos_calculate_balance_change
from common.utils.fio import calculate_balance_change as fio_calculate_balance_change
from common.services import cointainer_web3 as web3
from common.utils.ethereum import THOR_ROUTER_ABI
from django.db import connection

import logging
import json

logger = logging.getLogger('watchtower.ingester.tasks')

ZX_PROXY_CONTRACT = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'


@task(base=QueueOnce, once={'graceful': True})
def sync_blocks(network, from_hash=None):
    logger.info('sync blocks for %s, from_hash = %s', network, from_hash)
    ProcessedBlock.invalidate_orphans(network)
    coinquery = get_coinquery_client(network)

    if from_hash:
        next_hash = from_hash
    else:
        latest_processed_block = ProcessedBlock.latest(network)
        has_processed_blocks = bool(latest_processed_block)

        if has_processed_blocks:
            next_hash = coinquery.get_next_block_hash(latest_processed_block.block_hash)
        else:
            next_hash = coinquery.get_last_block_hash()

    while next_hash:
        sync_block(network, next_hash)
        info = {"hash": next_hash, "network": network}
        RabbitConnection().publish(
            exchange=EXCHANGE_BLOCKS,
            routing_key='',
            message_type='block',
            body=json.dumps(info)
        )
        next_hash = coinquery.get_next_block_hash(next_hash)

    logger.info('finished syncing blocks for %s, from_hash = %s', network, from_hash)


@task(base=QueueOnce, once={'graceful': True})
def sync_block(network, block_hash):
    logger.info('syncing block for %s with hash %s', network, block_hash)

    coinquery = get_coinquery_client(network)

    try:
        block_txs = coinquery.get_transactions_by_block_hash(block_hash)
        block_txs_by_txid = {tx.get('txid'): tx for tx in block_txs}
        block_txs_by_address = map_txs_by_address(block_txs, txs_by_address={})
        block_tx_addresses = list(block_txs_by_address.keys())
        tracked_addresses = list(Address.objects.filter(
            address__in=block_tx_addresses,
            account__network=network
        ).values_list('address', flat=True))

        # thor trade rewards should happen with this call
        save_results(
            network,
            tracked_addresses,
            block_txs_by_address,
            block_txs_by_txid,
            publish=True,
            thor_trade_reward=True)
        ProcessedBlock.get_or_create(block_hash, network)

        logger.info('finished syncing block for %s with hash %s', network, block_hash)
    except Exception as e:
        logger.error('failed to sync block: %s', str(e))
        raise e


@task(base=QueueOnce, once={'graceful': True})
def fix_pending_txs(network):
    txids = []
    dbTxMap = {}
    unconfirmed = tx_fetcher.fetch_unconfirmed_transactions(network).get('data')
    for tx in unconfirmed:
        # map txids to that txs id in the database
        txid = tx.get('txid')
        id = tx.get('id')
        dbTxMap[txid] = id
        txids.append(txid)

    # ask coinquery for updates on pending transactions
    coinquery = get_coinquery_client(network)
    txmap = coinquery.get_transactions_for_txids(txids)

    # for any transactions that are now confirmed but we missed for some reason, mark it as confirmed
    for txid, tx in txmap.items():

        # doge deviates from the insight api and does not have block_height information
        # when requesting transaction details
        if network == DOGE:
            block = coinquery.get_block_by_hash(tx.get('blockhash'))
            block_height = block.get('height')
        else:
            block_height = tx.get('blockheight')

        if block_height is not None and block_height > 0:
            logger.error(
                'confirmed transaction is still marked as unconfirmed, fixing... How did this happen: {} {}'
                    .format(network, txid)
            )

            # mark the transaction as confirmed
            block_hash = tx.get('blockhash')
            block_time = datetime.fromtimestamp(tx.get('blocktime'), timezone.utc)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                        update tracker_transaction
                        set block_height = {}, block_hash = '{}', block_time = '{}'
                        where tracker_transaction.id = {}
                        """.format(block_height, block_hash, block_time, dbTxMap.get(txid))
                )


@task(base=QueueOnce, once={'graceful': True})
def refresh_chainheights():
    with connection.cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY tracker_chainheight")


def _coallate(list_a, list_b):
    """ Given: _coallate([ '1', '2', '3', '4'], ['a', 'b', 'c', 'd'])
        Return: ['1', 'a', '2', 'b', '3', 'c', '4', 'd']
    """
    return [i for sub in zip(list_a, list_b) for i in sub]


# wrapper around sync_xpub that tracks the status of the sync process
@task(base=QueueOnce, once={'graceful': True})
def initial_sync_xpub(xpub, network, script_type, hard_refresh, publish):
    account_object, created = Account.objects.get_or_create(xpub=xpub, network=network, script_type=script_type)
    time_since_last_update = (datetime.now(timezone.utc) - account_object.updated_at).total_seconds()

    # skip if already syncing, unless it has been more than 15min since the acount was updated
    if account_object.sync_status in ['SYNCING'] and time_since_last_update < 900 and created is False:
        return
    account_object.update_sync_status('SYNCING')

    # Remove addresses, transactions, and associated data from db on hard refresh
    if hard_refresh:
        Address.objects.filter(account=account_object).delete()
        Transaction.objects.filter(account=account_object).delete()

    msg = {
        'type': 'sync_xpub',
        'data': {
            'xpub': xpub,
            'network': network,
            'script_type': script_type,
            'sync_status': 'syncing'
        }
    }

    RabbitConnection().publish(exchange=EXCHANGE_NOTIFICATIONS, routing_key='', body=json.dumps(msg))

    try:
        sync_xpub(xpub, network, script_type, publish)
    except Exception as e:
        # mark the sync as failed and rethrow the exception
        account_object = Account.objects.get(xpub=xpub, network=network, script_type=script_type)
        account_object.update_sync_status('FAILED')

        msg['data']['sync_status'] = 'failed'

        RabbitConnection().publish(exchange=EXCHANGE_NOTIFICATIONS, routing_key='', body=json.dumps(msg))

        logger.error("Syncing failed for xpub with id: {} with error: {}".format(account_object.id, str(e)))
        raise e

    account_object = Account.objects.get(xpub=xpub, network=network, script_type=script_type)
    account_object.update_sync_status('COMPLETE')

    msg['data']['sync_status'] = 'complete'

    RabbitConnection().publish(exchange=EXCHANGE_NOTIFICATIONS, routing_key='', body=json.dumps(msg))


@task(base=QueueOnce, once={'graceful': True})
def sync_xpub(xpub, network, script_type, publish, start_index=0):
    logger.info('syncing xpub for network %s', network)

    account_object = Account.objects.get(xpub=xpub, network=network, script_type=script_type)

    if network == ETH:
        return sync_ethereum_account(account_object)
    if network == ATOM or network == KAVA or network == RUNE or network == OSMO or network == SCRT:
        return sync_tendermint_account(network, account_object)
    if network == BNB:
        return sync_binance_account(account_object)
    if network == XRP:
        return sync_ripple_account(account_object)
    if network == EOS:
        return sync_eos_account(account_object)
    if network == FIO:
        return sync_fio_account(account_object)

    coinquery = get_coinquery_client(network)

    from_index = start_index
    to_index = from_index + GAP_LIMIT
    max_idx = start_index
    addr_chunk_size = 10

    while True:
        addresses_to_track = {}
        raw_txs = {}
        txs_by_address = {}  # {'<address>': {'<txid>': <int/satoshis:balance_change>}}

        count = to_index - from_index
        external_addresses = account_object.derive_external_addresses(count, from_index=from_index)  # noqa
        internal_addresses = account_object.derive_internal_addresses(count, from_index=from_index)  # noqa

        addr_change = _coallate(
            [(addr, chunk_idx + from_index, True) for (chunk_idx, addr) in enumerate(internal_addresses)],
            [(addr, chunk_idx + from_index, False) for (chunk_idx, addr) in enumerate(external_addresses)])

        # Pull out the first element of all the tuples into their own list:
        addresses = [ac[0] for ac in addr_change]

        for x in range(0, len(addresses), addr_chunk_size):
            addrs = addresses[x:x + addr_chunk_size]
            transactions = coinquery.get_transactions(addrs, page_size=20)

            for addr in addrs:
                txs_by_address[addr] = {}

            for tx in transactions:
                raw_txs[tx.get('txid')] = tx

            txs_by_address = map_txs_by_address(
                transactions,
                txs_by_address=txs_by_address,
                filter_addresses=addrs,
            )

        for (address, idx, is_change) in addr_change:
            address_info = {
                'index': idx,
                'relpath': '{}/{}'.format(1 if is_change else 0, idx),
                'type': Address.CHANGE if is_change else Address.RECEIVE
            }

            address_obj, address_created = Address.objects.update_or_create(
                address=address,
                account=account_object,
                defaults=address_info
            )

            address_info['is_change'] = is_change
            addresses_to_track[address] = address_info

            # Here we conservatively deviate from the standard, and reset the
            # gap limit upon seeing tx's on either the change chain or the
            # external chain. Standards-following wallets are allowed to scan
            # only the external chain, since wallets are expected to never send
            # change to an address with an index higher than the gap-20 on the
            # external chain.  We do a smidge extra scanning here in order to
            # detect those change outputs coming from wallets that got it wrong
            # (like ourselves, before this commit).
            #
            # It is conservative for us to do this, since it will only result
            # in us scanning a little more of the blockchain in the worst case,
            # but does not change the way a standards-following wallet would see
            # us behaving.
            has_transactions = bool(txs_by_address[address])
            if has_transactions:
                max_idx = max(max_idx, idx)

        # thor trade rewards should not happen with this call
        save_results(network, addresses_to_track, txs_by_address, raw_txs, publish=publish)

        # explicitly clear so gc knows it can garbage collect
        addresses_to_track.clear()
        raw_txs.clear()
        txs_by_address.clear()

        # we didn't find any new active addresses
        if max_idx < from_index:
            break

        # scan GAP_LIMIT past the last idx we found
        from_index = to_index
        to_index = max_idx + GAP_LIMIT


@task(base=QueueOnce, once={'graceful': True})
def watch_addresses():
    # todo refactor to batch calls to cq (1 call per network we are watching at least 1 address for)
    addresses = redisClient.smembers(WATCH_ADDRESS_SET_KEY)
    for address in addresses:

        key = WATCH_ADDRESS_PREFIX + address
        s = redisClient.get(key)
        watched = json.loads(s) if isinstance(s, str) else None

        if watched is None:
            redisClient.srem(WATCH_ADDRESS_SET_KEY, address)
            continue

        coinquery = get_coinquery_client(watched["network"])
        transactions = coinquery.get_transactions([address])

        if len(transactions) > watched["current"]:
            logger.info('found %s transactions for %s with watched count %s', len(transactions), address,
                        watched["current"])
            txs_by_address = {}
            txs_by_address[address] = {}
            addresses_to_track = {}
            raw_txs = {}
            for tx in transactions:
                raw_txs[tx.get('txid')] = tx

            txs_by_address = map_txs_by_address(
                transactions,
                txs_by_address=txs_by_address,
                filter_addresses=[address]
            )

            addresses_to_track[address] = {
                'is_change': watched["type"] == "change",
                'index': watched["index"],
                'relpath': watched["relpath"],
                'type': watched["type"]
            }

            # thor trade rewards should not happen with this call
            save_results(watched["network"], addresses_to_track, txs_by_address, raw_txs)

            redisClient.delete(key)
            redisClient.srem(WATCH_ADDRESS_SET_KEY, address)
            logger.debug('saved tx %s for %s', tx.get('id'), address)


@task(base=QueueOnce, once={'graceful': True})
def watch_tx_task():
    watch_tx('BTC')
    watch_tx('LTC')
    watch_tx('DOGE')
    watch_tx('DASH')
    watch_tx('BCH')
    watch_tx('DGB')


def watch_tx(network):
    transactions = redisClient.smembers(WATCH_TX_SET_KEY + network)
    if len(transactions) > 0:
        logger.debug('checking on %s %s transactions', len(transactions), network)
        coinquery = get_coinquery_client(network)
        txs_by_txid = coinquery.get_transactions_for_txids(transactions)

        txs_list = list(txs_by_txid.values())
        txs_by_address = map_txs_by_address(txs_list, txs_by_address={})
        tx_addresses = list(txs_by_address.keys())
        tracked_addresses = list(Address.objects.filter(
            address__in=tx_addresses,
            account__network=network
        ).values_list('address', flat=True))

        # thor trade rewards should not happen with this call
        save_results(network, tracked_addresses, txs_by_address, txs_by_txid)

        txids_to_remove = list(txs_by_txid.keys())
        logger.debug('txids_to_remove = %s', txids_to_remove)

        redisClient.srem(WATCH_TX_SET_KEY + network, *txids_to_remove)


# Assumptions:
# no transactions occurred after sync started and before it finished
def sync_tendermint_account(network, account_object):
    gaia = get_gaia_client(network)

    def save_tx(tx):
        tx_obj, tx_created = Transaction.objects.update_or_create(
            txid=tx['txid'],
            account=account_object,
            erc20_token=None,
            is_erc20_token_transfer=False,
            is_erc20_fee=False,
            thor_memo=tx.get('thor_memo'),
            fee=tx.get('fee', 0),
            defaults={
                'block_hash': tx['block_hash'],
                'block_time': tx['block_time'],
                'block_height': tx['block_height'],
                'raw': ''
            }
        )

        balance_change_amount = 0
        if network == 'RUNE':
            if address == tx.get('from'):
                balance_change_amount -= tx.get('value')
            elif address == tx.get('to'):
                balance_change_amount += tx.get('value')
        if network == 'OSMO':
            if address == tx.get('from'):
                balance_change_amount -= tx.get('value')
            elif address == tx.get('to'):
                balance_change_amount += tx.get('value')
        else:
            balance_change_amount = cosmos_calculate_balance_change(address, tx)

        BalanceChange.objects.update_or_create(
            account=account_object,
            address=address_obj,
            transaction=tx_obj,
            amount=balance_change_amount
        )
        return

    address_obj = account_object.get_account_address()
    address = address_obj.address
    sync_account_balances(network, address)

    # todo: check for empty list
    for tx in gaia.get_transactions(address):
        save_tx(tx)


# Assumptions:
# no transactions occurred after sync started and before it finished
def sync_binance_account(account_object):
    def save_tx(tx):
        tx_obj, tx_created = Transaction.objects.update_or_create(
            txid=tx['txid'],
            account=account_object,
            erc20_token=None,
            is_erc20_token_transfer=False,
            is_erc20_fee=False,
            defaults={
                'block_hash': tx['block_hash'],
                'block_time': tx['block_time'],
                'block_height': tx['block_height'],
                'raw': ''
            }
        )

        balance_change_amount = cosmos_calculate_balance_change(address, tx)  # this function also works for bnb
        balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
            account=account_object,
            address=address_obj,
            transaction=tx_obj,
            amount=balance_change_amount
        )
        return

    address_obj = account_object.get_account_address()
    address = address_obj.address
    sync_bnb_account_balances(address)

    for tx in binance_client.get_txs_for_address(address):
        save_tx(tx)


# Assumptions:
# no transactions occurred after sync started and before it finished
def sync_ripple_account(account_object):
    def save_tx(tx):
        tx_obj, tx_created = Transaction.objects.update_or_create(
            txid=tx['txid'],
            account=account_object,
            defaults={
                'block_hash': tx['block_hash'],
                'block_time': tx['block_time'],
                'block_height': tx['block_height'],
                'raw': ''
            }
        )

        balance_change_amount = cosmos_calculate_balance_change(address, tx)  # this function also works for xrp
        balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
            account=account_object,
            address=address_obj,
            transaction=tx_obj,
            amount=balance_change_amount
        )
        return

    address_obj = account_object.get_account_address()
    address = address_obj.address
    sync_xrp_account_balances(address)

    for tx in ripple.get_transactions_by_account(address):
        save_tx(tx)


# Assumptions:
# no transactions occurred after sync started and before it finished
def sync_fio_account(account_object):
    def save_tx(tx):
        tx_obj, tx_created = Transaction.objects.update_or_create(
            txid=tx['txid'],
            account=account_object,
            defaults={
                'block_hash': tx['block_hash'],
                'block_time': tx['block_time'],
                'block_height': tx['block_height'],
                'raw': ''
            }
        )

        balance_change_amount = fio_calculate_balance_change(address, tx)  # this function also works for eos
        balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
            account=account_object,
            address=address_obj,
            transaction=tx_obj,
            amount=balance_change_amount
        )
        return

    address_obj = account_object.get_account_address()
    address = address_obj.address
    sync_fio_account_balances(address)

    for tx in fio.get_transactions_by_pubkey(address):
        save_tx(tx)


# Assumptions:
# no transactions occurred after sync started and before it finished
def sync_eos_account(account_object):
    def save_tx(tx):
        tx_obj, tx_created = Transaction.objects.update_or_create(
            txid=tx['txid'],
            account=account_object,
            defaults={
                'block_hash': tx['block_hash'],
                'block_time': tx['block_time'],
                'block_height': tx['block_height'],
                'raw': ''
            }
        )

        balance_change_amount = cosmos_calculate_balance_change(address, tx)  # this function also works for eos
        balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
            account=account_object,
            address=address_obj,
            transaction=tx_obj,
            amount=balance_change_amount
        )
        return

    address_obj = account_object.get_account_address()
    address = address_obj.address
    sync_eos_account_balances(address)

    for tx in eos_client.get_account_tx(address):
        save_tx(tx)


# Assumptions:
# no transactions occurred after sync started and before it finished
def sync_ethereum_account(account_object):
    ethereum_address_obj = account_object.get_account_address()
    ethereum_address = ethereum_address_obj.address
    tokens = {}

    def save_tx(transaction, contract_address):
        txid = transaction['hash']
        block_hash = transaction['blockHash']
        block_time = int(transaction['timeStamp'])
        block_time = datetime.fromtimestamp(block_time, timezone.utc)
        block_height = int(transaction['blockNumber'])
        is_erc20_token_transfer = 'tokenName' in transaction
        is_erc20_fee = transaction.get('is_erc20_fee', False)
        tx_successful = False if transaction.get('isError', '0') == '1' else True
        thor_memo = transaction.get('thor_memo', None)

        if is_erc20_token_transfer:
            token_name = transaction['tokenName']
            token_symbol = transaction['tokenSymbol']
            precision = int(transaction.get('tokenDecimal') or ETHEREUM_DECIMAL_PRECISION)

            # etherscan returns switched symbol and name for FTX Token
            if contract_address == '0x50d1c9771902476076ecfc8b2a83ad6b9355a4c9':
                token_name = transaction['tokenSymbol']
                token_symbol = transaction['tokenName']

            # override RUNE token symbol to allow for native RUNE to use it (symbols must be unique in axiom/wt for now)
            if contract_address == '0x3155ba85d5f96b2d030a4966af206230e46849cb':
                token_symbol = 'ETH.RUNE'

            token_obj, token_created = ERC20Token.objects.update_or_create(
                contract_address=contract_address,
                defaults={"contract_address": contract_address, "name": token_name, "symbol": token_symbol,
                          "precision": precision}
            )

        else:
            token_obj = None

        # erc20 transfer as part of an 0x trade
        erc_dex_trade = is_erc20_token_transfer == True and transaction['original_to_address'] == ZX_PROXY_CONTRACT
        # internal tx from 0x to us
        dex_withdraw_trade = is_erc20_token_transfer != True and transaction['from'] == ZX_PROXY_CONTRACT and \
                             transaction['to'] == ethereum_address.lower()
        # normal tx from us to 0x
        dex_deposit_trade = is_erc20_token_transfer != True and transaction['from'] == ethereum_address.lower() and \
                            transaction['original_to_address'] == ZX_PROXY_CONTRACT and len(
            transaction.get('input', '0x')) > 32

        is_dex_trade = erc_dex_trade or dex_withdraw_trade or dex_deposit_trade

        numberFee = calculate_ethereum_transaction_fee(transaction)

        fee = None
        if numberFee is not None:
            fee = '{:e}'.format(numberFee)

        tx_obj, tx_created = Transaction.objects.update_or_create(
            txid=txid,
            account=account_object,
            erc20_token=token_obj,
            is_erc20_token_transfer=is_erc20_token_transfer,
            is_erc20_fee=is_erc20_fee,
            is_dex_trade=is_dex_trade,
            success=tx_successful,
            defaults={
                'block_hash': block_hash,
                'block_time': block_time,
                'block_height': block_height,
                'raw': ''
            },
            thor_memo=thor_memo,
            fee=str(fee)
        )

        if is_dex_trade == False:
            balance_change_amount = calculate_balance_change(ethereum_address, transaction, is_erc20_fee)
        else:
            balance_change_amount = calculate_dex_balance_change(ethereum_address, transaction, erc_dex_trade,
                                                                 dex_withdraw_trade, dex_deposit_trade, is_erc20_fee,
                                                                 tx_successful)

        balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
            account=account_object,
            address=ethereum_address_obj,
            transaction=tx_obj,
            amount=balance_change_amount
        )
        tokens[contract_address] = 1
        return block_height

    # get eth and token balances
    sync_eth_account_balances(ethereum_address)

    # get transactions from block explorer service
    token_transaction_ids = []

    tx_types = {
        'normal': {'count': 0, 'min_block_height': 0},
        'internal': {'count': 0, 'min_block_height': 0},
        'token': {'count': 0, 'min_block_height': 0}
    }

    all_eth_transactions1 = gen_get_all_ethereum_transactions(ethereum_address)
    all_eth_transactions2 = gen_get_all_ethereum_transactions(ethereum_address)

    original_to_addresses = dict()

    thor_deposit_contract = web3.eth.contract(
        address=web3.toChecksumAddress('0x0000000000000000000000000000000000000000'), abi=THOR_ROUTER_ABI)

    for tx in all_eth_transactions1:
        original_to_addresses[tx.get('hash')] = tx['to']

    for tx in gen_get_all_token_transactions(ethereum_address):

        # check to see if this token tx includes a thor memo and extract it
        receipt = web3.eth.getTransactionReceipt(tx['hash'])
        transferOut = thor_deposit_contract.events.TransferOut()
        deposit = thor_deposit_contract.events.Deposit()
        try:
            logsDecoded = transferOut.processReceipt(receipt)
            tx['thor_memo'] = str(logsDecoded[0]['args']['memo'])
        except:
            pass
        try:
            logsDecoded = deposit.processReceipt(receipt)
            tx['thor_memo'] = str(logsDecoded[0]['args']['memo'])
        except:
            pass

        tx['original_to_address'] = original_to_addresses.get(tx.get('hash'))
        token_transaction_ids.append(tx['hash'])
        tx_types['token']['min_block_height'] = save_tx(tx, tx['contractAddress'])
        tx_types['token']['count'] += 1

    # all non-token transactions.  Includes token fee txs
    for tx in all_eth_transactions2:

        # save fee txs, every token tx has a fee
        tx['original_to_address'] = original_to_addresses.get(tx.get('hash'))
        if tx['hash'] in token_transaction_ids:
            tx['is_erc20_fee'] = True

        # dont put thor_memo on token fee txs
        if tx.get('is_erc20_fee', None) is not True:
            # check to see if this was a call to the thor deposit contract
            # extract the memo if it was
            try:
                decoded_input = thor_deposit_contract.decode_function_input(tx['input'])
            except:
                decoded_input = None

            if decoded_input is not None:
                tx['thor_memo'] = str(decoded_input[1]['memo'])

        tx_types['normal']['min_block_height'] = save_tx(tx, ETH)
        tx_types['normal']['count'] += 1

        # save another tx if eth was sent
        if float(tx['value']) > 0:
            tx['original_to_address'] = original_to_addresses.get(tx.get('hash'))
            if tx.get('is_erc20_fee', None) is True: #zero out the fee if already included above
                tx['is_erc20_fee'] = False
                tx['gasUsed'] = 0 
                tx['gasPrice'] = 0
            tx_types['normal']['min_block_height'] = save_tx(tx, ETH)
            tx_types['normal']['count'] += 1

    for tx in gen_get_all_internal_ethereum_transactions(ethereum_address):
        # check to see if this was an internal thor eth transaction (incoming eth tx)
        # extract the memo if it was
        receipt = web3.eth.getTransactionReceipt(tx['hash'])
        transferOut = thor_deposit_contract.events.TransferOut()
        try:
            logsDecoded = transferOut.processReceipt(receipt)
            tx['thor_memo'] = str(logsDecoded[0]['args']['memo'])
        except:
            pass

        tx['original_to_address'] = original_to_addresses.get(tx.get('hash'))
        tx['blockHash'] = receipt['blockHash'].hex()
        tx_types['internal']['min_block_height'] = save_tx(tx, ETH)
        tx_types['internal']['count'] += 1

    init_block_height = 0
    for item in tx_types.values():
        if item['count'] >= ETH_MAX_TXS:
            init_block_height = item['min_block_height']

    if init_block_height > 0:
        logger.warning('xpub has more than max transactions: %s, inserting initial balance at block %s', ETH_MAX_TXS,
                       init_block_height)
        init_block_time = Transaction.objects.filter(block_height=init_block_height, account=account_object)[
            0].block_time

        # remove older transactions & balance transfers
        Transaction.objects.filter(block_height__lt=init_block_height, account=account_object).delete()

        # insert initial balance adjustment
        for contract_address in tokens:
            if contract_address == ETH:
                current_balance = int(get_eth_balance(ethereum_address))
                initial_balance = current_balance - int(Address.objects.get(address=ethereum_address).get_balance())
                erc20_token = None
                is_erc20_token_transfer = False
            else:
                current_balance = int(get_eth_token_balance(contract_address, ethereum_address))
                initial_balance = current_balance - int(
                    Address.objects.get(address=ethereum_address).get_erc20_contract_balance(contract_address))
                erc20_token = ERC20Token.objects.get(contract_address=contract_address)
                is_erc20_token_transfer = True

            if initial_balance != 0:
                tx_obj, tx_created = Transaction.objects.update_or_create(
                    txid='initial_balance_adjustment',
                    account=account_object,
                    erc20_token=erc20_token,
                    is_erc20_token_transfer=is_erc20_token_transfer,
                    is_erc20_fee=False,
                    defaults={
                        'block_hash': 'initial_balance_adjustment',
                        'block_time': init_block_time,
                        'block_height': init_block_height,
                        'raw': ''
                    }
                )
                balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
                    account=account_object,
                    address=ethereum_address_obj,
                    transaction=tx_obj,
                    amount=initial_balance
                )


def get_fee(tx):
    vin = tx.get('vin')
    vout = tx.get('vout')
    total_in = 0
    total_out = 0

    if vin is not None:
        for tx_in in vin:
            satoshis = tx_in.get('valueSat', 0)
            total_in += satoshis
    if vout is not None:
        for tx_out in vout:
            satoshis = int(Decimal(tx_out.get('value', 0)).quantize(Decimal(10) ** -8) * (10 ** 8))
            total_out += satoshis
    return total_in - total_out


def map_txs_by_address(txs, txs_by_address={}, filter_addresses=[]):
    for tx in txs:
        txid = tx.get('txid')
        vin = tx.get('vin')
        vout = tx.get('vout')

        for tx_in in vin:
            address = tx_in.get('addr')
            satoshis = tx_in.get('valueSat', 0)

            if not address:  # skip coinbase inputs
                continue

            should_include_address = (not filter_addresses) or address in filter_addresses
            if address not in txs_by_address and should_include_address:
                txs_by_address[address] = {}

            if (filter_addresses and address in filter_addresses) or (
                    not filter_addresses and address in txs_by_address):  # noqa
                txs_by_address[address][txid] = txs_by_address[address].setdefault(txid, 0) - satoshis  # noqa

        for tx_out in vout:
            for address in tx_out['scriptPubKey'].get('addresses', []):
                if (not filter_addresses) or address in filter_addresses:
                    if address not in txs_by_address:
                        txs_by_address[address] = {}

                    satoshis = int(Decimal(tx_out.get('value')).quantize(Decimal(10) ** -8) * (10 ** 8))  # noqa
                    txs_by_address[address][txid] = txs_by_address[address].setdefault(txid, 0) + satoshis  # noqa

    return txs_by_address


def save_results(network, addresses, txs_by_address, raw_txs, publish=True, thor_trade_reward=False):
    # map txs for rabbit notifications
    rabbitTransactions = {}

    for address in addresses:
        address_obj = Address.objects.get(address=address, account__network=network)
        account = address_obj.account

        for txid, balance_change in txs_by_address[address].items():

            raw_tx = raw_txs[txid]
            # if we have a block_hash but not the blockheight (coinquery doge does not return blockheight)
            # then we need to look up the height
            if raw_tx.get('blockhash') and not raw_tx.get('blockheight'):
                try:
                    coinquery = get_coinquery_client(network)
                    block = coinquery.get_block_by_hash(raw_tx.get('blockhash'))
                    raw_tx['blockheight'] = block.get('height')
                except Exception as e:
                    logger.error("Unable to fetch blockheight for block: %s", str(raw_tx.get('blockhash')), extra=e)

            # Extract thor memo from bitcoin op_return output if it exists on the transaction
            thor_memo = None
            try:
                if raw_tx['vout'] is not None:
                    for i in raw_tx['vout']:
                        if 'OP_RETURN' in i['scriptPubKey']['asm']:
                            hex_data = i['scriptPubKey']['asm'].split()[1]
                            thor_memo = str(bytearray.fromhex(hex_data).decode())
            except Exception as e:
                logger.error("Exception decoding thor memo: %s", e)

            fee = get_fee(raw_tx)

            try:
                if thor_memo is None or thor_memo.startswith('omni'):
                    thor_memo= ''
            except Exception as e:
                logger.error("Exception omni thor memo: %s", e)
                thor_memo= ''

            tx_obj, tx_created = Transaction.objects.update_or_create(
                txid=txid,
                account=account,
                defaults={
                    'block_hash': raw_tx.get('blockhash'),
                    'block_time': datetime.fromtimestamp(raw_tx.get('blocktime'), timezone.utc) if raw_tx.get(
                        'blocktime') else None,
                    'block_height': raw_tx.get('blockheight', 0),
                    'thor_memo': thor_memo,
                    'fee': str(fee)
                }
            )

            balance_change_obj, bc_created = BalanceChange.objects.update_or_create(
                account=account,
                address=address_obj,
                transaction=tx_obj,
                amount=balance_change
            )

            if publish:
                # keep track of what messages we need to push to rabbit
                # need combined dict key in case of multiple tx's in same block with same xpub
                key = account.xpub + txid
                if rabbitTransactions.get(key, None) is None:
                    msg = {}
                    msg["txid"] = txid
                    msg["network"] = network
                    msg["symbol"] = network
                    msg["xpub"] = account.xpub
                    msg["balance_change"] = balance_change
                    msg["blockheight"] = raw_txs[txid].get('blockheight', 0)
                    msg["blocktime"] = raw_txs[txid].get('blocktime')
                    msg["confirmations"] = raw_txs[txid].get('confirmations', 0)
                    # add thor trade details if reward is enabled
                    if thor_trade_reward:
                        memo_prefix_out = 'OUT:'
                        if thor_memo and memo_prefix_out in thor_memo:
                            sell_txid = thor_memo[len(memo_prefix_out):]
                            thor_tx = thorchain.get_valid_transaction(txid=sell_txid)
                            if thor_tx:
                                msg = {**msg, **thor_tx}
                    rabbitTransactions[key] = msg
                else:
                    # merge the balance_changes so that we don't double notify for change addresses
                    rabbitTransactions[key]["balance_change"] += balance_change

    if publish:
        # publish to rabbit
        logger.info("Rabbit messages: %s", list(rabbitTransactions.values()))
        for k, v in rabbitTransactions.items():
            msg = v
            txType = "receive" if msg["balance_change"] > 0 else "send"
            msg['type'] = txType
            RabbitConnection().publish(
                exchange=EXCHANGE_TXS,
                routing_key='',
                message_type='event.platform.transaction',
                body=json.dumps(msg)
            )

@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_eth():
    eth_block_ingester.poll_blocks()


@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_atom():
    atom_block_ingester.poll_blocks()


@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_rune():
    rune_block_ingester.poll_blocks()


@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_kava():
    kava_block_ingester.poll_blocks()

@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_osmo():
    osmo_block_ingester.poll_blocks()

@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_secret():
    scrt_block_ingester.poll_blocks()


@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_xrp():
    xrp_block_ingester.poll_blocks()


@task(base=QueueOnce, once={'graceful': True})
def sync_blocks_fio():
    fio_block_ingester.poll_blocks()


# @task(base=QueueOnce, once={'graceful': True})
# def queue_blocks_bnb():
#     try:
#         bnb_block_ingester.queue_blocks_ws()
#     except SoftTimeLimitExceeded:
#         # celery does not like long running tasks
#         # soft_time_limit should be less than beat schedule
#         logger.info('BNB SoftTimeLimitExceeded: allowing socket to restart')
#     except Exception as e:
#         logger.error('BNB {}'.format(e))
#     return

@task(base=QueueOnce, once={'graceful': True})
def ingest_blocks_bnb_alpha():
    bnb_block_ingester.ingest_blocks()


@task(base=QueueOnce, once={'graceful': True})
def ingest_blocks_bnb_bravo():
    bnb_block_ingester.ingest_blocks()


@task(base=QueueOnce, once={'graceful': True})
def ingest_blocks_bnb_charlie():
    bnb_block_ingester.ingest_blocks()


@task(base=QueueOnce, once={'graceful': True})
def ingest_blocks_eos():
    # ingest txs in last 20 blocks that relate to our registered accounts, if any
    eos_block_ingester.ingest_txs_over_block_range(-21, -1)
