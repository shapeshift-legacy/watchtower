from tracker.models import Address, Transaction, BalanceChange, ProcessedBlock
from common.utils.blockchain import FIO
from common.utils.utils import timestamp_to_unix
from common.services import fio
from common.services.rabbitmq import RabbitConnection, EXCHANGE_BLOCKS, EXCHANGE_TXS
from ingester.fio.balance_sync import sync_fio_account_balances
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger('watchtower.ingester.fio')

class FioBlockIngester:
    def poll_blocks(self):
        latest_known = ProcessedBlock.latest(FIO)
        if latest_known is not None:
            self.process_blocks(latest_known.block_height + 1)
        else:
            logger.info('Initializing Fio block tracking')
            block_by_height = fio.get_latest_block_height()
            self.process_blocks(block_by_height)

    def process_blocks(self, start_number):
        logger.debug('sync_fio_blocks: %s', start_number)
        block_by_height = fio.get_block_at_height(start_number)
        while block_by_height is not None:
            # store transactions for known addresses
            self.process_block(block_by_height)
            block_hash = block_by_height['id']

            # publish block to rabbitmq
            info = {
                'height': start_number,
                'hash': block_hash,
                'network': 'FIO'
            }
            RabbitConnection().publish(exchange=EXCHANGE_BLOCKS,
                                       routing_key='',
                                       body=json.dumps(info))

            # watch out for case where we previously marked a block an orphan but now gaia has returned it
            # as the valid block at given height again
            b = ProcessedBlock.get_or_none(block_hash, FIO)
            if not bool(b):
                b = ProcessedBlock()
                b.network = FIO
                b.block_height = block_by_height.get('block_num')
                b.block_hash = block_by_height.get('id')
                timeOfBlock = block_by_height.get('timestamp')
                timeOfBlock = timeOfBlock[:-4]
                timeOfBlock = datetime.strptime(timeOfBlock, '%Y-%m-%dT%H:%M:%S')
                timeOfBlock = timeOfBlock.astimezone()
                b.block_time = timeOfBlock
                b.previous_hash = block_by_height.get('previous')
                b.previous_block = ProcessedBlock.get_or_none(block_hash=b.previous_hash, network=FIO)
            else:
                logger.info('previous orphan %s resurrected', block_hash)
                b.is_orphaned = False

            b.save()
            logger.info('saved new FIO block at height %s with hash %s', b.block_height, b.block_hash)
            start_number += 1
            block_by_height = fio.get_block_at_height(start_number)

    def process_block(self, block):
        # get transactions at block height
        txs = fio.parse_block_txs(block)
        # group by address
        by_address = self.parse_transactions(txs)
        # split out fees
        self.enrich(by_address)
        # save txs
        self.save_fio_transactions(by_address, block['id'])

    def parse_transactions(self, txs):
        transactions = []
        addresses = set()
        for tx in txs:
            #parsed_tx = fio.format_tx(tx)
            transactions.append(tx)
            addresses.add(tx.get('from'))
            if tx.get('to') is not None:
                addresses.add(tx.get('to'))
            logger.debug('added transaction %s', tx)

        # find intersection of addresses in block and addresses we know about
        known_addresses = Address.objects.filter(
            address__in=list(addresses),
            account__network=FIO
        ).values_list('address', flat=True)

        # filter list of transactions down to those we care about
        transactions = list(filter(lambda t: t.get('from') in known_addresses
                                             or t.get('to') in known_addresses, transactions))
        logger.debug('after filter transactions have %s txs', len(transactions))

        # group transactions by address in a dictionary
        by_address = self.group_transactions_by_address(known_addresses, transactions)
        return by_address

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
    def save_fio_transactions(tx_by_address, block_hash):
        # map txs for rabbit notifications
        rabbit_transactions = []
        network = 'FIO'

        for address, txs in tx_by_address.items():
            address_obj = Address.objects.get(address=address)
            account_object = address_obj.account
            sync_fio_account_balances(address)

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
                        'block_hash': block_hash,
                        'block_time': tx.get('block_time'),
                        'block_height': tx.get('block_height'),
                        'raw': tx.get('raw') or "raw"
                    }
                )

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
                    'balance_change': int(tx.get('balance_change')),
                    'balance_units': 'ufio',
                    'blockheight': tx.get('block_height'),
                    'blocktime': timestamp_to_unix(tx.get('block_time').__str__())
                }

                if msg["balance_change"] > 0:
                    tx_type = 'receive'
                else:
                    tx_type = 'send'

                msg["type"] = tx_type

                rabbit_transactions.append(msg)

        # publish to rabbit
        for msg in rabbit_transactions:
            RabbitConnection().publish(exchange=EXCHANGE_TXS, routing_key='', message_type='event.platform.transaction', body=json.dumps(msg))
