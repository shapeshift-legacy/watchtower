from common.utils.ethereum import format_address as to_checksum_address
from tracker.models import Address, Transaction, BalanceChange, ProcessedBlock
from common.utils.utils import timestamp_to_unix
from common.services.gaia_tendermint import get_client as get_gaia_client
from common.services.rabbitmq import RabbitConnection, EXCHANGE_BLOCKS, EXCHANGE_TXS
from ingester.tendermint.balance_sync import sync_account_balances
from common.utils.networks import ATOM, RUNE, SCRT, KAVA, OSMO
from cashaddress import convert as convert_bch
import json
import logging

logger = logging.getLogger('watchtower.ingester.tendermint')


class TendermintBlockIngester:
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.gaia = get_gaia_client(network)
        self.native_asset = self.gaia.get_native_asset(network)

    def poll_blocks(self):
        latest_known = ProcessedBlock.latest(self.network)
        if latest_known is not None:
            block_by_height = self.gaia.get_block_at_height(str(latest_known.block_height))
            block_by_height_hash = self.gaia.get_block_hash_at_height(str(latest_known.block_height))
            # do we have uncles to deal with?
            if block_by_height is None or block_by_height_hash != latest_known.block_hash:
                logger.info('detected potential %s uncle at height %s with hash %s',
                            self.network, latest_known.block_height, latest_known.block_hash)
                latest_known.is_orphaned = True
                latest_known.save()
                ProcessedBlock.cleanUpOrphans(latest_known.id)
                return self.poll_blocks()
            else:
                self.process_blocks(latest_known.block_height + 1)
        else:
            logger.info('Initializing {} block tracking'.format(self.network))
            block_by_height = self.gaia.get_latest_block_height()
            if block_by_height is None:
                logger.info('Error: requested block not found')
                return None
            self.process_blocks(block_by_height)

    def process_blocks(self, start_number):
        logger.debug('sync_blocks: %s', start_number)
        block_by_height = self.gaia.get_block_at_height(start_number)
        block_hash = self.gaia.get_block_hash_at_height(start_number)
        while block_by_height is not None:
            # store transactions for known addresses
            self.process_block(block_by_height, block_hash)
            block_header = block_by_height['header']

            # publish block to rabbitmq
            info = {
                'height': start_number,
                'hash': block_hash,
                'network': self.network
            }
            RabbitConnection().publish(exchange=EXCHANGE_BLOCKS,
                                       routing_key='',
                                       body=json.dumps(info))

            # watch out for case where we previously marked a block an orphan but now gaia has returned it
            # as the valid block at given height again
            b = ProcessedBlock.get_or_none(block_hash, self.network)
            if not bool(b):
                b = ProcessedBlock()
                b.network = self.network
                b.block_height = block_header['height']
                b.block_hash = block_hash
                b.block_time = block_header['time']
                b.previous_hash = block_header['last_block_id']['hash']
                b.previous_block = ProcessedBlock.get_or_none(block_hash=b.previous_hash, network=self.network)
            else:
                logger.info('previous orphan %s resurrected', block_hash)
                b.is_orphaned = False

            b.save()
            logger.info('saved new %s block at height %s with hash %s', self.network, b.block_height, b.block_hash)
            start_number += 1
            block_by_height = self.gaia.get_block_at_height(start_number)
            block_hash = self.gaia.get_block_hash_at_height(start_number)

    def process_block(self, block, block_hash):
        # get transactions at block height
        height = block.get('header', {}).get('height')
        txs = self.gaia.get_transactions_at_height(height)
        if txs is None:
            logger.info('Error getting transactions from block')
            return

        # group by address
        by_address = self.format_txs(txs, height)
        # split out fees
        self.enrich(by_address)
        # save txs
        self.save_transactions(by_address, block_hash)

    def format_txs(self, txs, height):
        if self.network != RUNE:
            return self.parse_transactions(txs)
        addresses = set()
        for tx in txs:
            nested_txs = self.gaia.get_nested_transactions(tx)
            for nested_tx in nested_txs:
                from_address = nested_tx.get('tx', {}).get('from_address', '')
                # ETH addresses in db are checksum,
                # BCH addresses in db are legacy format
                if nested_tx.get('tx', {}).get('chain') == 'ETH':
                  from_address = to_checksum_address(from_address)
                elif nested_tx.get('tx', {}).get('chain') == 'BCH':
                  from_address = convert_bch.to_legacy_address('bitcoincash:{}'.format(from_address))

                addresses.add(from_address)
        # intentionally filter on address only; can be mixed bag of chains
        known_addresses = Address.objects.filter(
            address__in=list(addresses)
        ).values_list('address', flat=True)

        transactions = []
        for tx in txs:
            msgType = tx.get('tx', {}).get('value', {}).get('msg', [{}])[0].get('type')
            if msgType != 'thorchain/ObservedTxIn':
              transactions.append(tx)
              continue

            nested_txs = self.gaia.get_nested_transactions(tx)

            for nested_tx in nested_txs:
                from_address = nested_tx.get('tx', {}).get('from_address', '')
                if nested_tx.get('tx', {}).get('chain') == 'ETH':
                  from_address = to_checksum_address(from_address)
                elif nested_tx.get('tx', {}).get('chain') == 'BCH':
                  from_address = convert_bch.to_legacy_address('bitcoincash:{}'.format(from_address))

                id = nested_tx.get('tx', {}).get('id')
                findTxInArray = next((x for x in transactions if x.get('id') == id), None)

                if findTxInArray == None and from_address in known_addresses:
                    data = self.gaia.get_midgard_actions_by_txid(id)
                    actions = data.get('actions', [{}])
                    # action observations sometimes span blocks (one validator observes in block N, another block N+1, N+2 and so on)
                    # only record the tx in the block the swap/action occurred in
                    actions = list(
                      filter(
                        lambda action: height == action.get('height', ''),
                        actions
                      )
                    )

                    # TEMP FIX FOR SWITCH MEMO TYPES
                    if (len(actions) is not 0):
                        out = actions[0].get('out', [{}])
                        # TEMP FIX FOR FAILED REFUNDS
                        if (len(out) is not 0):
                            out_data = self.gaia.parse_out_data(out)
                            built_tx = tx
                            built_tx['tx']['value']['memo'] = 'OUT:' + id
                            built_tx['to_address'] = out_data['to_address']
                            built_tx['amount'] = out_data['amount']
                            built_tx['id'] = id

                            transactions.append(built_tx)

        return self.parse_transactions(transactions)

    def parse_transactions(self, txs):
        transactions = []
        addresses = set()
        for tx in txs:
            if self.network == RUNE:
                parsed_tx = self.gaia.format_tx_rune(tx)
            elif self.network == ATOM:
                parsed_tx = self.gaia.format_tx_cosmos(tx)
            elif self.network == KAVA:
                parsed_tx = self.gaia.format_tx_kava(tx)
            elif self.network == SCRT:
                parsed_tx = self.gaia.format_tx_secret(tx)
            elif self.network == OSMO:
                parsed_tx = self.gaia.format_tx_osmo(tx)
            transactions.append(parsed_tx)
            addresses.add(parsed_tx.get('from'))
            if parsed_tx.get('to') is not None:
                addresses.add(parsed_tx.get('to'))

        # find intersection of addresses in block and addresses we know about
        known_addresses = Address.objects.filter(
            address__in=list(addresses)
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

    def save_transactions(self, tx_by_address, block_hash):

        # map txs for rabbit notifications
        rabbit_transactions = []

        for address, txs in tx_by_address.items():
            address_obj = Address.objects.get(address=address)
            account_object = address_obj.account
            # ignore txs from other chains (thorchain USDT->ETH for example)
            if account_object.network != self.network:
              continue
            sync_account_balances(self.network, address)

            for tx in txs:
                logger.debug('persisting transaction and balance change for %s', tx)
                token_obj = None

                tx_obj, tx_created = Transaction.objects.update_or_create(
                    txid=tx.get('txid'),
                    account=account_object,
                    erc20_token=token_obj,
                    is_erc20_token_transfer=False,
                    is_erc20_fee=False,
                    thor_memo=tx.get('thor_memo', None),
                    fee=tx.get('fee', 0),
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
                    'network': self.network,
                    'symbol': self.network,
                    'xpub': account_object.xpub,
                    'balance_change': int(tx.get('balance_change')),
                    'balance_units': self.native_asset,
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
            RabbitConnection().publish(exchange=EXCHANGE_TXS, routing_key='', message_type='event.platform.transaction',
                                       body=json.dumps(msg))
