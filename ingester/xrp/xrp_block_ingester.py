from tracker.models import Address, Transaction, BalanceChange, ProcessedBlock
from common.utils.blockchain import XRP
from common.utils.utils import timestamp_to_unix
from common.services import ripple
from common.services.rabbitmq import RabbitConnection, EXCHANGE_BLOCKS, EXCHANGE_TXS
from ingester.xrp.balance_sync import sync_xrp_account_balances
import json
import logging
from datetime import datetime, timezone


logger = logging.getLogger('watchtower.ingester.xrp')


class RippleBlockIngester:
    def poll_blocks(self):
        latest_known = ProcessedBlock.latest(XRP)
        if latest_known is not None:
            block_by_height = ripple.get_block_at_height(latest_known.block_height)
            # xrp doesnt have orphans
            if block_by_height is None or block_by_height.get('ledger_hash') != latest_known.block_hash:
                #keep working
                return self.poll_blocks()
            else:
                self.process_blocks(latest_known.block_height + 1)
        else:
            logger.info('Initializing XRP block tracking')
            block_by_height = ripple.get_latest_block_height()
            self.process_blocks(block_by_height)

    def process_blocks(self, start_number):
        logger.debug('sync_ripple_blocks: %s', start_number)
        block_by_height = ripple.get_block_at_height(start_number)

        while block_by_height is not None:
            # store transactions for known addresses
            self.process_block(block_by_height)
            block_hash = block_by_height['ledger_hash']

            # publish block to rabbitmq
            info = {
                'height': start_number,
                'hash': block_hash,
                'network': 'XRP'
            }
            RabbitConnection().publish(exchange=EXCHANGE_BLOCKS,
                                       routing_key='',
                                       body=json.dumps(info))

            b = ProcessedBlock.get_or_none(block_hash, XRP)
            if not bool(b):
                b = ProcessedBlock()
                b.network = XRP
                b.block_height = block_by_height['ledger_index']
                b.block_hash = block_by_height['ledger_hash']
                b.block_time = datetime.fromtimestamp(ripple.ripple_to_unix_epoch(block_by_height['ledger']['close_time']), timezone.utc)
                b.previous_hash = block_by_height['ledger']['parent_hash']
                #b.previous_block = ProcessedBlock.get_or_none(block_hash=b.previous_hash, network=XRP)
            else:
                logger.info('previous orphan %s resurrected', block_hash)
                b.is_orphaned = False

            b.save()
            logger.info('saved new XRP block at height %s with hash %s', b.block_height, b.block_hash)
            start_number += 1
            block_by_height = ripple.get_block_at_height(start_number)

    def process_block(self, block):
        height = block['ledger_index']
        txs = ripple.get_transactions_at_height(height)
        txs_by_address = self.parse_transactions(txs)
        self.enrich(txs_by_address)
        self.save_xrp_transactions(txs_by_address, block['ledger_hash'])

    def parse_transactions(self, transactions):
        # transactions = []
        addresses = set()
        for tx in transactions:
            addresses.add(tx.get('from'))
            if tx.get('to') is not None:
                addresses.add(tx.get('to'))

        # find intersection of addresses in block and addresses we know about
        known_addresses = Address.objects.filter(
            address__in=list(addresses),
            account__network=XRP
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
                    balance_change -= float(tx.get('value'))
                elif address == tx.get('to'):
                    balance_change += float(tx.get('value'))

                tx['balance_change'] = balance_change


    @staticmethod
    def save_xrp_transactions(tx_by_address, block_hash):

        # map txs for rabbit notifications
        rabbit_transactions = []
        network = 'XRP'

        for address, txs in tx_by_address.items():
            address_obj = Address.objects.get(address=address)
            account_object = address_obj.account
            sync_xrp_account_balances(address)

            for tx in txs:
                logger.debug('persisting transaction and balance change for %s', tx)

                blocktime = datetime.strptime(tx.get('block_time'), '%Y-%m-%d %H:%M:%S')
                datestring = blocktime.strftime('%Y-%m-%dT%H:%M:%S%z')

                tx_obj, tx_created = Transaction.objects.update_or_create(
                    txid=tx.get('txid'),
                    account=account_object,
                    defaults={
                        'block_hash': block_hash,
                        'block_time': blocktime,
                        'block_height': tx.get('block_height'),
                        'raw': ''
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
                    'balance_units': 'xrp',
                    'blockheight': tx.get('block_height'),
                    'blocktime': timestamp_to_unix(datestring)
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
