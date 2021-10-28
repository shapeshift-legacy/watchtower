import asyncio
import json
import time
import logging
import websockets
import itertools

from time import sleep
from dateutil import parser

from tracker.models import Address, Transaction, BalanceChange, ProcessedBlock
from common.utils.networks import BNB
from common.utils.utils import timestamp_to_unix
from common.services import binance_client
from common.services.rabbitmq import RabbitConnection, EXCHANGE_BLOCKS, EXCHANGE_TXS
from ingester.bnb.balance_sync import sync_bnb_account_balances
import ingester.tasks


logger = logging.getLogger('watchtower.ingester.bnb')


class BinanceBlockIngester:

    def queue_blocks_ws(self):
        WSS_URI = binance_client.BASE_URL_RPC.replace('https', 'wss') + '/websocket'

        def _transform_block(_this, _next):
            try:
                this_block = _this.get('result', {}).get('data', {}).get('value', {}).get('block', {})
                next_block = _next.get('result', {}).get('data', {}).get('value', {}).get('block', {})
                return {
                    'hash': next_block['header']['last_block_id']['hash'],
                    'height': this_block['header']['height'],
                    'num_txs': this_block['header']['num_txs'],
                    'previous_hash': this_block['header']['last_block_id']['hash'],
                    'time': this_block['header']['time'],
                    'txs': this_block['data']['txs'],
                }
            except Exception as e:
                logger.error('BNB _transform_block: {}'.format(e))
                return None

        def _handle_msg(msg, prev_msg):
            prev_block = json.loads(prev_msg)
            this_block = json.loads(msg)
            block = _transform_block(prev_block, this_block)
            if block is not None:
                queue_length = binance_client.queue_block(block)
                logger.info('BNB queued: {} queue_length: {}'.format(block['height'], queue_length))

        async def _get_stream(rpc_json):
            async with websockets.connect(WSS_URI, ssl=True) as websocket:
                prev_msg = None
                await websocket.send(rpc_json)
                async for msg in websocket:
                    # `prev_msg` required to determine `msg` block hash
                    if prev_msg is None:
                        prev_msg = msg
                        continue
                    # perform ETL
                    _handle_msg(msg, prev_msg)
                    # update pointers
                    prev_msg = msg

        # subscribe to socket method
        asyncio.run(_get_stream(
            '{"jsonrpc":"2.0","method":"subscribe","id":0,"params":{"query":"tm.event=\'NewBlock\'"}}'
        ))

    def queue_blocks(self, height=None, queued=None):
        '''
        Queue blocks in redis for consumption by tx ingester
        '''
        MAX_QUEUE_LENGTH = 600
        BATCH_SIZE = 10
        RETRY = True

        # start from supplied, last saved or bnb chain height
        # requesting block at height None returns latest on chain
        if height is None:
            try:
                height = int(binance_client.get_queue_block_height()) + 1
            except:
                pass

        if queued is None:
            queued = []

        logger.debug('BNB queue_blocks from height: {}'.format(height))
        block = binance_client.get_block(height)
        if block is not None:
            queue_length = binance_client.queue_block(block)
            if queue_length >= MAX_QUEUE_LENGTH:
                logger.warn('BNB queue_length: {} >= limit of: {}'.format(queue_length, MAX_QUEUE_LENGTH))
                return queued
            queued.append(block['height'])
            # base case
            if len(queued) == BATCH_SIZE:
                logger.info('BNB queued {} blocks: [{} ... {}]'.format(len(queued), queued[0], queued[-1]))
                queue_height = binance_client.set_queue_block_height(block)
                logger.info('BNB queue_length: {} queue_height: {}'.format(queue_length, block['height']))
                return queued
            # recurse - queue next block
            return self.queue_blocks(
                height=block['height'] + 1, queued=queued
            )
        elif RETRY:
            sleep(1)  # prevent recursion error / DOS
            logger.warn('BNB retrying get_block for height: {}'.format(height))
            return self.queue_blocks(height=height, queued=queued)
        return queued

    def ingest_blocks(self, recurse=False):
        '''
        Dequeue blocks from redis and ingest txs

        `recurse` is useful for development and debugging in python shell
        it should not be used with celery.
        '''
        return self._ingest_block(binance_client.dequeue_block(), recurse)

    def _ingest_block(self, block, recurse):
        if block is None:
            logger.warn('BNB skipping ingestion for block: {}'.format(block))
            return
        else:
            logger.debug('BNB ingesting block: {}'.format(block['height']))
        txs_block = binance_client.get_block_txs(block)
        txs_block_by_address = self._filter_txs_by_registered_address(txs_block)

        # split out fees
        self.enrich(txs_block_by_address)
        # save txs to db
        self.save_bnb_transactions(txs_block_by_address, block['hash'])

        try:
            # save block to db
            b = ProcessedBlock.get_or_none(block['hash'], BNB)
            if not bool(b):
                b = ProcessedBlock()
                b.network = BNB
                b.block_height = block['height']
                b.block_hash = block['hash']
                b.block_time = block['time']
                b.previous_hash = block['previous_hash']
                b.previous_block = ProcessedBlock.get_or_none(block_hash=b.previous_hash, network=BNB)
            else:
                logger.warn('BNB previous orphan %s resurrected', block['hash'])
                b.is_orphaned = False
            b.save()
            # if we have saved - publish block to rabbit
            try:
                info = {
                    'height': block['height'],
                    'hash': block['hash'],
                    'network': BNB
                }
                RabbitConnection().publish(exchange=EXCHANGE_BLOCKS, routing_key='', body=json.dumps(info))
            except Exception as e:
                logger.error('BNB failed to publish block to rabbit: {}'.format(block['height']))
                logger.error(e)
            logger.info('BNB saved block: {}'.format(block['height']))
        except Exception as e:
            # save failed
            logger.error('BNB failed to save block: {}'.format(block['height']))
            logger.error(e)

        if recurse:
            # keep ingesting - will stop when get_block() returns None
            return self.ingest_blocks(recurse=True)
        return


    def _get_registered_addresses_from_txs(self, txs):
        # all addresses found in tx block
        tx_addresses = list(set(itertools.chain(*[(tx['from'], tx['to']) for tx in txs])))
        registered_addresses = Address.objects \
            .select_related('account') \
            .filter(address__in=tx_addresses, account__network=BNB) \
            .values_list('address', flat=True)
        return registered_addresses

    def _filter_txs_by_registered_address(self, txs):
        registered_addresses = self._get_registered_addresses_from_txs(txs)
        txs_by_address = {}
        for tx in txs:
            tx_from = tx['from']
            tx_to = tx['to']
            tx_asset = tx.get('asset')
            if tx_asset == 'BNB':
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
    def save_bnb_transactions(tx_by_address, block_hash):
        # map txs for rabbit notifications
        rabbit_transactions = []
        network = BNB

        for address, txs in tx_by_address.items():
            address_obj = Address.objects.get(address=address)
            account_object = address_obj.account
            sync_bnb_account_balances(address)

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
                        'raw': tx.get('raw')
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
                    'balance_change': tx.get('balance_change'),
                    'balance_units': 'ubnb',
                    'blockheight': tx.get('block_height'),
                    'blocktime': timestamp_to_unix(tx.get('block_time'))
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
