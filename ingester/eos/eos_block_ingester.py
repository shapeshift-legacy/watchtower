import json
import time
import itertools
import logging

from tracker.models import Address, Transaction, BalanceChange, ProcessedBlock
from common.utils.networks import EOS
from common.utils.utils import timestamp_to_unix
from common.services import eos_client
from common.services.rabbitmq import RabbitConnection, EXCHANGE_BLOCKS, EXCHANGE_TXS
from ingester.eos.balance_sync import sync_eos_account_balances


logger = logging.getLogger('watchtower.ingester.eos')


class EOSBlockIngester:

    def ingest_txs_over_block_range(self, low_block, high_block):
        '''
        Retrieve txs in last N blocks that relate to our registered accounts, if any
        '''

        # get txs pertaining to accounts we track over a supplied block range
        accounts = Address.objects \
            .select_related('account') \
            .filter(account__network=EOS) \
            .values_list('address', flat=True)
        txs = eos_client.get_block_txs_for_accounts(accounts, low_block, high_block)
        # filter and sort into required { addr: txs } map
        # NOTE - this isnt strictly required given we alredy know these are txs we care about
        # however, im leaving it this way for consistency with the rest of our assets
        txs_by_address = self._filter_txs_by_registered_address(txs)
        # split out fees
        self.enrich(txs_by_address)
        # save txs to db
        self.save_eos_transactions(txs_by_address)

    def _ingest_block(self, block, recurse):
        if block is None:
            logger.warn('EOS skipping ingestion for block: {}'.format(block))
            return
        else:
            logger.debug('EOS ingesting block: {}'.format(block['height']))

        try:
            # save block to db
            b = ProcessedBlock.get_or_none(block['hash'], EOS)
            if not bool(b):
                b = ProcessedBlock()
                b.network = EOS
                b.block_height = block['height']
                b.block_hash = block['hash']
                b.block_time = block['time']
                b.previous_hash = block['previous_hash']
                b.previous_block = ProcessedBlock.get_or_none(block_hash=b.previous_hash, network=EOS)
            else:
                logger.warn('EOS previous orphan %s resurrected', block['hash'])
                b.is_orphaned = False
            b.save()
            # if we have saved - publish block to rabbit
            try:
                info = {
                    'height': block['height'],
                    'hash': block['hash'],
                    'network': EOS
                }
                RabbitConnection().publish(exchange=EXCHANGE_BLOCKS, routing_key='', body=json.dumps(info))
            except Excaption as e:
                logger.error('EOS failed to publish block to rabbit: {}'.format(block['height']))
                logger.error(e)
            logger.info('EOS saved block: {}'.format(block['height']))
        except Exception as e:
            # save failed
            logger.error('EOS failed to save block: {}'.format(block['height']))
            logger.error(e)

        if recurse:
            # keep ingesting - will stop when get_block() returns None
            return self.ingest_blocks(recurse=True)
        return


    def _get_registered_addresses_from_txs(self, txs):
        # all addresses found in tx block
        tx_addresses = list(set(itertools.chain(*[(tx['from'], tx['to']) for tx in txs])))
        registered_addresses = Address.objects \
            .filter(address__in=tx_addresses, account__network=EOS) \
            .values_list('address', flat=True)
        return registered_addresses

    def _filter_txs_by_registered_address(self, txs):
        registered_addresses = self._get_registered_addresses_from_txs(txs)
        txs_by_address = {}
        for tx in txs:
            tx_from = tx['from']
            tx_to = tx['to']
            if tx_from in registered_addresses:
                if tx_from not in txs_by_address:
                    txs_by_address[tx_from] = []
                txs_by_address[tx_from].append(tx)
            if tx_to in registered_addresses:
                if tx_to not in txs_by_address:
                    txs_by_address[tx_to] = []
                if tx_to != tx_from:  # if not a self send
                    txs_by_address[tx_to].append(tx)
        return txs_by_address

    @staticmethod
    def group_transactions_by_address(addresses, transactions):
        by_address = {}
        for t in transactions:
            from_address = t.get('from')
            to_address = t.get('to')
            if from_address in addresses:
                txs = by_address.get(from_address) if isinstance(by_address.get(from_address), list) else list()
                txs.append(t)
                by_address[from_address] = txs

            # only add if not a self send
            if to_address in addresses and to_address != from_address:
                to_tx = t.copy()
                txs = by_address.get(to_address) if isinstance(by_address.get(to_address), list) else list()
                txs.append(to_tx)
                by_address[to_address] = txs
        return by_address

    @staticmethod
    def enrich(by_address):
        for address, txs in by_address.items():
            for tx in txs:
                balance_change = 0.0

                if address == tx.get('from'):
                    balance_change -= tx.get('value')
                elif address == tx.get('to'):
                    balance_change += tx.get('value')

                tx['balance_change'] = balance_change

    @staticmethod
    def save_eos_transactions(tx_by_address):

        # map txs for rabbit notifications
        rabbit_transactions = []
        network = EOS

        for address, txs in tx_by_address.items():
            address_obj = Address.objects.get(address=address)
            account_object = address_obj.account
            sync_eos_account_balances(address)

            for tx in txs:
                logger.debug('persisting transaction and balance change for %s', tx)
                token_obj = None

                tx_obj, tx_created = Transaction.objects.update_or_create(
                    txid=tx.get('txid'),
                    account=account_object,
                    erc20_token=token_obj,
                    is_erc20_token_transfer=False,
                    is_erc20_fee=False,
                    defaults={
                        'block_hash': tx.get('block_hash'),
                        'block_time': tx.get('block_time'),
                        'block_height': tx.get('block_height'),
                        'raw': tx.get('raw')
                    }
                )

                if tx_created:
                    # there is overlap between TX queries to make sure we dont miss any
                    # we should ignore all below if this is a benign duplicate
                    BalanceChange.objects.update_or_create(
                        account=account_object,
                        address=address_obj,
                        transaction=tx_obj,
                        amount=tx.get('balance_change')
                    )
                    msg = {
                        'txid': tx.get('txid'),
                        'network': network,
                        'symbol': network,
                        'xpub': account_object.xpub,
                        'balance_change': tx.get('balance_change'),
                        'balance_units': 'ueos',
                        'blockheight': tx.get('block_height'),
                        'blocktime': timestamp_to_unix(tx.get('block_time').__str__())
                    }
                    if msg["balance_change"] > 0:
                        tx_type = 'receive'
                    else:
                        tx_type = 'send'
                    msg["type"] = tx_type
                    rabbit_transactions.append(msg)
                    logger.info('EOS ingested tx: {}'.format(tx.get('txid')))

        # publish to rabbit
        for msg in rabbit_transactions:
            RabbitConnection().publish(exchange=EXCHANGE_TXS, routing_key='', message_type='event.platform.transaction', body=json.dumps(msg))
