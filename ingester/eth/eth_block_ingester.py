
from tracker.models import Address, Transaction, BalanceChange, ProcessedBlock, ERC20Token
from common.utils.blockchain import ETH
from common.utils.utils import timestamp_to_unix
from common.services import cointainer_web3 as web3, etherscan, thorchain
from common.services.launchdarkly import is_feature_enabled, PUBLISH_CONFIRMED_TXS
from common.services.rabbitmq import RabbitConnection, EXCHANGE_TXS, EXCHANGE_BLOCKS
from common.services.redis import redisClient
from common.utils.ethereum import eth_balance_cache_key_format
from datetime import datetime, timezone
from ingester.eth.balance_sync import sync_eth_account_balances, sync_eth_token_balance
from ingester.eth.dex_eth_txs import get_dex_eth_txs
from ingester.eth.thor_eth_txs import get_thor_txs

import json
import sha3
import logging

logger = logging.getLogger('watchtower.ingester.eth')


class EthereumBlockIngester:
    ERC20 = 'ERC20'
    BITGO_MULTISIG = 'BITGO_MULTISIG'
    DEX_ETH_TXS = 'DEX_ETH_TXS'
    THOR_ETH_TXS = 'THOR_ETH_TXS'

    ZX_PROXY_CONTRACT = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'

    k = sha3.keccak_256()
    k.update('Transfer(address,address,uint256)'.encode('utf-8'))
    transfer_topic = '0x' + k.hexdigest()

    # https://github.com/BitGo/eth-multisig-v2/blob/master/contracts/WalletSimple.sol
    k = sha3.keccak_256()
    # Transacted(msg.sender, otherSigner, operationHash, toAddress, value, data)
    k.update('Transacted(address,address,bytes32,address,uint256,bytes)'.encode('utf-8'))
    bitgo_multisig_topic = '0x' + k.hexdigest()
    # 0x59bed9ab5d78073465dd642a9e3e76dfdb7d53bcae9d09df7d0b8f5234d5a806

    def poll_blocks(self):
        latest_known = ProcessedBlock.latest(ETH)
        if latest_known is not None:
            block_by_height = web3.eth.getBlock(str(hex(latest_known.block_height)), False)
            block_by_height_hash = web3.toHex(block_by_height.get('hash'))
            # do we have uncles to deal with?
            if block_by_height is None or block_by_height_hash != latest_known.block_hash:
                logger.info('detected potential ETH uncle at height %s with hash %s',
                            latest_known.block_height, latest_known.block_hash)
                latest_known.is_orphaned = True
                latest_known.save()
                ProcessedBlock.cleanUpOrphans(latest_known.id)
                return self.poll_blocks()
            else:
                self.process_blocks(latest_known.block_height + 1)

        else:
            logger.info('Initializing ETH block tracking')
            block_by_height = web3.eth.getBlock('latest', False)
            self.process_blocks(block_by_height.get('number'))

    def process_blocks(self, start_number):
        logger.debug('sync_eth_blocks: %s', start_number)
        block_by_height = web3.eth.getBlock(start_number, True)
        while block_by_height is not None:
            # store transactions for known addresses
            self.process_block(block_by_height)
            block_hash = web3.toHex(block_by_height.get('hash'))

            # publish block to rabbitmq
            info = {}
            info['height'] = start_number
            info['hash'] = block_hash
            info['network'] = 'ETH'
            RabbitConnection().publish(exchange=EXCHANGE_BLOCKS,
                    routing_key='',
                    body=json.dumps(info))

            # watch out for case where we previously marked a block an orphan but now node has returned it
            # as the valid block at given height again
            b = ProcessedBlock.get_or_none(block_hash, ETH)
            if not bool(b):
                b = ProcessedBlock()
                b.network = ETH
                b.block_height = block_by_height.get('number')
                b.block_hash = block_hash
                b.block_time = datetime.fromtimestamp(block_by_height.get('timestamp'), timezone.utc)
                b.previous_hash = web3.toHex(block_by_height.get('parentHash'))
                b.previous_block = ProcessedBlock.get_or_none(block_hash=b.previous_hash, network=ETH)
            else:
                logger.info('previous orphan %s resurrected', block_hash)
                b.is_orphaned = False

            b.save()
            logger.info('saved new ETH block at height %s with hash %s', b.block_height, b.block_hash)
            start_number += 1
            block_by_height = web3.eth.getBlock(start_number, True)

    def process_block(self, block):
        # extract transactions
        by_address = self.extract_transactions(block)
        # split out fees, add erc20 data
        self.enrich(by_address)
        # save txs
        self.save_eth_transactions(by_address)

    def get_internal_transactions(self, block):
        internal_txs = etherscan.get_internal_txs_by_block_number(int(block.get('number')))

        internal_transactions = dict()
        for txid in internal_txs.keys():
            if internal_transactions.get(txid) is None:
                internal_transactions[txid] = []

            for internal_tx in internal_txs[txid]:
                try:
                    internal_transactions[txid].append({
                        'from_address': web3.toChecksumAddress(internal_tx.get('from')),
                        'to_address': web3.toChecksumAddress(internal_tx.get('to')),
                        'value': internal_tx.get('value')
                    })
                except Exception as e:
                    logger.exception('error adding internal transaction {}'.format(internal_tx), e)

        return internal_transactions

    def get_erc20_transactions(self, block):
        block_hash = web3.toHex(block.get('hash'))
        block_height = block.get('number')
        logs = web3.eth.getLogs({
            'fromBlock': block_height,
            'toBlock': block_height,
            'topics': [self.transfer_topic, None, None]
        })

        if len(logs) < 1:
            logger.info('No logs of type transfer found for block %s %s', block_height, block_hash)

        contract_addresses = dict()
        for tx in block.transactions:
            contract_addresses[tx.get('hash').hex()] = tx['to']

        erc20_transactions = dict()
        for log in logs:
            txid = web3.toHex(log.get('transactionHash'))
            contract_address = log.get('address').lower()
            original_contract_address = contract_addresses.get(txid)
            if original_contract_address != None:
                original_contract_address = original_contract_address.lower()

            topics = log.get('topics')
            if len(topics) != 3:
                # not an ERC20 transfer event (could be ERC721 or something else)
                logger.debug('invalid number of topics (%s) for tx %s in block %s', len(topics), txid, block_hash)
                continue

            if erc20_transactions.get(txid) is None:
                erc20_transactions[txid] = []

            erc20_transactions[txid].append({
                'txid': txid,
                'contract_address': contract_address,
                'original_contract_address': original_contract_address,
                'from_address': web3.toChecksumAddress(web3.toHex(topics[1])[26:]),
                'to_address': web3.toChecksumAddress(web3.toHex(topics[2])[26:]),
                'block_height': block_height,
                'block_hash': block_hash,
                'amount': int(log.get('data'), 16)
            })

        return erc20_transactions

    def get_bitgo_multisig_transactions(self, block):
        block_hash = web3.toHex(block.get('hash'))
        block_height = block.get('number')
        logs = web3.eth.getLogs({
            'fromBlock': block_height,
            'toBlock': block_height,
            'topics': [self.bitgo_multisig_topic]
        })

        logger.debug('Found %s multisig logs in block %s', len(logs), block_height)

        multisig_txs = dict()
        for log in logs:
            logger.debug('Processing multisig log: %s', log)
            txid = web3.toHex(log.get('transactionHash'))
            topics = log.get('topics')
            if len(topics) != 1:
                logger.info('invalid number of topics (%s) for multisig tx %s in block %s', len(topics), txid, block_hash)
                continue

            # topics not indexed, need to pull from data...
            # example:
            # #0x000000000000000000000000e01ed9e684de649bfec799cd79f6c27335c23cb9000000000000000000000000f42347648799ff04f422a033089e342cfadd6ea445cf3f16095be914ad49c158a2e19b220f429de1e49ca5166553b915154b649200000000000000000000000026e1b6b5f5b60c07b058d0617a9d14a73e2f6dbc000000000000000000000000000000000000000000000000035a8c7d586bc00000000000000000000000000000000000000000000000000000000000000000c00000000000000000000000000000000000000000000000000000000000000000
            data = log.get('data')
            from_address = data[26:66]
            to_address = data[218:258]
            amount = int(data[258:322], 16)
            multisig_txs[txid] = {
                'txid': txid,
                'from_address': from_address,
                'to_address': to_address,
                'block_height': block_height,
                'block_hash': block_hash,
                'amount': amount
            }

            logger.debug('Added multisig tx %s from = %s, to = %s, amount = %s', txid, from_address, to_address, amount)
        return multisig_txs

    def extract_transactions(self, block):
        block_height = block.get('number')
        block_hash = web3.toHex(block.get('hash'))
        block_time = datetime.fromtimestamp(block.get('timestamp'), timezone.utc)

        logger.debug('extract_transactions for block: %s', block_hash)

        internal_transactions = self.get_internal_transactions(block)
        erc20_transactions = self.get_erc20_transactions(block)
        thor_txs = get_thor_txs(block)
        dex_eth_txs = get_dex_eth_txs(block)
        multisig_transactions = self.get_bitgo_multisig_transactions(block)

        transactions = []
        addresses = set()

        def add_transaction(base_transaction, type_transaction):
            transaction = dict()
            transaction.update(base_transaction)
            transaction.update(type_transaction)
            transactions.append(transaction)
            transaction.get('from_address') and addresses.add(transaction.get('from_address'))
            transaction.get('to_address') and addresses.add(transaction.get('to_address'))
            logger.debug('added transaction %s', transaction)

        for tx in block.transactions:
            txid = web3.toHex(tx.get('hash'))

            base_transaction = {
                'txid': txid,
                'from_address': web3.toChecksumAddress(tx.get('from')),
                'gas_price': tx.get('gasPrice'),
                'to_address': None,
                'contract_address': None,
                'block_height': block_height,
                'block_hash': block_hash,
                'block_time': block_time,
                'is_dex_trade': False,
                'raw': '',
            }

            internal_txs = internal_transactions.get(txid)
            erc20_txs = erc20_transactions.get(txid)
            thor_tx = thor_txs.get(txid)
            dex_eth_tx = dex_eth_txs.get(txid)
            multisig_tx = multisig_transactions.get(txid)

            # standard eth transfer not including dex, thor, and multisig
            if not dex_eth_tx and not thor_tx and not multisig_tx:
                # do not include 0 value eth transfers related to an erc20 token transfer
                if not (int(tx.get('value')) == 0 and erc20_txs):
                    standard_transaction = {
                        'type': ETH,
                        'to_address': web3.toChecksumAddress(tx.get('to')) if bool(tx.get('to')) else None,
                        'value': tx.get('value')
                    }

                    add_transaction(base_transaction, standard_transaction)

            # internal eth transfers not including dex, thor, and multisig
            if internal_txs and not dex_eth_tx and not thor_tx and not multisig_tx:
                for internal_tx in internal_txs:
                    internal_transaction = {
                        'type': ETH,
                        'from_address': internal_tx.get('from_address'),
                        'to_address': internal_tx.get('to_address'),
                        'value': internal_tx.get('value')
                    }

                    add_transaction(base_transaction, internal_transaction)

            # erc20 token transfers
            if erc20_txs:
                for erc20_tx in list(erc20_txs):
                    original_contract_address = erc20_tx.get('original_contract_address')
                    if original_contract_address:
                        original_contract_address = original_contract_address.lower()

                    memo = None
                    if thor_tx:
                        memo = thor_tx.get('thor_memo')

                    erc20_transaction = {
                        'type': self.ERC20,
                        'from_address': web3.toChecksumAddress(erc20_tx.get('from_address')),
                        'to_address': web3.toChecksumAddress(erc20_tx.get('to_address')),
                        'value': erc20_tx.get('amount'),
                        'contract_address': erc20_tx.get('contract_address').lower(),
                        'original_contract_address': original_contract_address,
                        'is_dex_trade': original_contract_address == self.ZX_PROXY_CONTRACT,
                        'thor_memo': memo
                    }

                    add_transaction(base_transaction, erc20_transaction)

            # Non-erc20 thor trades
            if thor_tx and not erc20_txs:
                thor_transaction = {
                    'type': self.THOR_ETH_TXS,
                    'from_address': web3.toChecksumAddress(thor_tx.get('from_address')),
                    'to_address': web3.toChecksumAddress(thor_tx.get('to_address')),
                    'value': thor_tx.get('amount'),
                    'contract_address': thor_tx.get('contract_address').lower(),
                    'thor_memo': thor_tx.get('thor_memo')
                }

                add_transaction(base_transaction, thor_transaction)

            # 0x trades into and out of eth
            if dex_eth_tx:
                dex_eth_transaction = {
                    'type': self.DEX_ETH_TXS,
                    'from_address': web3.toChecksumAddress(dex_eth_tx.get('from_address')),
                    'to_address': web3.toChecksumAddress(dex_eth_tx.get('to_address')),
                    'value': dex_eth_tx.get('amount'),
                    'contract_address': dex_eth_tx.get('contract_address').lower(),
                    'is_dex_trade': True
                }

                add_transaction(base_transaction, dex_eth_transaction)

            if multisig_tx:
                multisig_transaction = {
                    'type': self.BITGO_MULTISIG,
                    'from_address': web3.toChecksumAddress(multisig_tx.get('from_address')),
                    'to_address': web3.toChecksumAddress(multisig_tx.get('to_address')),
                    'value': multisig_tx.get('amount')
                }

                add_transaction(base_transaction, multisig_transaction)

        # find intersection of addresses in block and addresses we know about
        known_addresses = Address.objects.filter(
            address__in=list(addresses),
            account__network=ETH
        ).values_list('address', flat=True)

        # filter list of transactions down to those we care about
        transactions = list(filter(lambda t: t.get('from_address') in known_addresses
                            or t.get('to_address') in known_addresses, transactions))
        logger.debug('after filter transactions have %s txs', len(transactions))

        # group transactions by address in a dictionary
        by_address = self.group_transactions_by_address(known_addresses, transactions)

        return by_address

    @staticmethod
    def group_transactions_by_address(addresses, transactions):
        by_address = dict()

        def add_tx(address, tx):
            txid = tx.get('txid')

            if by_address.get(address) is None:
                by_address[address] = dict()

            if by_address[address].get(txid) is None:
                by_address[address][txid] = list()

            by_address[address][txid].append(tx)

        for t in transactions:
            from_address = t.get('from_address')
            if from_address in addresses:
                add_tx(from_address, t)

            # only add if not a self send
            to_address = t.get('to_address')
            if to_address in addresses and to_address != from_address:
                add_tx(to_address, t)

        return by_address

    # determine gas used for sends, calculate balance change, split out fee tx for ERC20s, add token symbol
    # and token id to ERC20s
    def enrich(self, by_address):
        erc20_fees = dict()
        for address, tx_obj in by_address.items():
            for txid, txs in tx_obj.items():
                receipt = web3.eth.getTransactionReceipt(txid)
                eth_send = any(address == tx.get('from_address') and tx.get('type') == ETH and int(tx.get('value')) > 0 for tx in txs)
                eth_dex_send = any(address == tx.get('from_address') and tx.get('type') == self.DEX_ETH_TXS and int(tx.get('value')) > 0 for tx in txs)

                for tx in txs:
                    balance_change = 0.0

                    tx['success'] = str(receipt.status) == '1'
                    tx['origin_address'] = receipt['from']

                    # sanitize address values
                    origin_address = tx.get('origin_address', '') or ''
                    from_address = tx.get('from_address', '') or ''
                    to_address = tx.get('to_address', '') or ''

                    # warn if we are missing any addresses to further diagnose use case
                    if origin_address == '' or from_address == '' or to_address == '':
                        logger.warn('invalid tx (missing to_address): {}'.format(tx))

                    # user (address) created the transaction
                    # track any associated token transfer events as a result of the transaction
                    # track any associated eth value transfers as a result of the transaction
                    if address.lower() == origin_address.lower():
                        tx['gas_used'] = receipt.get('gasUsed')
                        tx['fee'] = tx.get('gas_used') * tx.get('gas_price')

                        if tx.get('type') == self.ERC20:
                            # normal erc20 self send should be the fee only
                            if address.lower() == from_address.lower() and address.lower() == to_address.lower():
                                balance_change = 0
                            # normal outgoing erc20
                            elif address.lower() == from_address.lower():
                                balance_change = -tx.get('value')
                            # incoming erc20 due to contract interaction by user (ex. fox claim)
                            elif address.lower() == to_address.lower():
                                balance_change = tx.get('value')

                            # if there is no eth being sent in the same transaction,
                            # track the fee separately for any erc20 token transfers
                            if not eth_send and not eth_dex_send:
                                fee_tx = tx.copy()
                                fee_tx['from_address'] = address
                                fee_tx['type'] = ETH
                                fee_tx['erc20_fee'] = True
                                fee_tx['thor_memo'] = None  # do not include thor_memo on the erc20 fee tx
                                fee_tx['balance_change'] = -tx.get('fee')

                                if erc20_fees.get(txid) is None:
                                    erc20_fees[txid] = list()

                                erc20_fees[txid].append(fee_tx)
                        elif tx.get('type') == ETH or tx.get('type') == self.BITGO_MULTISIG:
                            # eth self send should be the fee only
                            # NOTE: this appears as a sent value on the platform versus a gas fee
                            if address.lower() == from_address.lower() and address.lower() == to_address.lower():
                                balance_change = -tx.get('fee')
                            # normal outgoing eth should track fee as part of total outgoing value
                            elif address.lower() == from_address.lower():
                                balance_change = -(tx.get('fee') + tx.get('value'))
                            # incoming eth due to contract interaction by user (ex. lp withdrawal)
                            elif address.lower() == to_address.lower():
                                balance_change = tx.get('value')
                        elif tx.get('type') == self.DEX_ETH_TXS:
                            if address.lower() == from_address.lower():
                                balance_change = -(tx.get('fee') + tx.get('value'))
                            if address.lower() == to_address.lower():
                                balance_change = tx.get('value')
                        elif tx.get('type') == self.THOR_ETH_TXS:
                            balance_change = -(int(tx.get('fee')) + int(tx.get('value')))
                        else:
                            logger.warning('unsupported transaction type %s', tx.get('type'))
                    # value was sent directly to the user (address)
                    else:
                        if address.lower() == to_address.lower():
                            balance_change = tx.get('value')

                    tx['balance_change'] = balance_change

                    if tx.get('type') == self.ERC20:
                        contract_address = tx.get('contract_address').lower()
                        # get contract details
                        tx['erc20_transfer'] = True

                        try:
                            token = ERC20Token.get_or_create(contract_address)
                            tx['token_symbol'] = token.symbol
                            tx['erc20_token_id'] = token.id
                        except Exception as e:
                            logger.exception('error obtaining details for erc20 contract {}'.format(contract_address), e)

        # add any fee tx we encountered
        for txid, fees in erc20_fees.items():
            for fee in fees:
                by_address[fee['from_address']][txid].append(fee)

    @staticmethod
    def save_eth_transactions(tx_by_address):
        # map txs for rabbit notifications
        rabbit_transactions = []
        network = 'ETH'

        for address, tx_obj in tx_by_address.items():
            address_obj = Address.objects.get(address=address)
            account_object = address_obj.account

            for txid, txs in tx_obj.items():
                for tx in txs:
                    logger.info('persisting transaction and balance change for %s', tx)
                    token_obj = None
                    if tx.get('erc20_token_id') is not None:
                        token_obj = ERC20Token.objects.get(id=tx.get('erc20_token_id'))

                    fee = None
                    numberFee = tx.get('fee', None)
                    if numberFee is not None:
                        fee = '{:e}'.format(numberFee)

                    tx_obj, tx_created = Transaction.objects.update_or_create(
                        txid=txid,
                        account=account_object,
                        erc20_token=token_obj,
                        is_erc20_token_transfer=tx.get('erc20_transfer', False),
                        is_erc20_fee=tx.get('erc20_fee', False),
                        is_dex_trade=tx.get('is_dex_trade', False),
                        success=tx.get('success', False),
                        thor_memo=tx.get('thor_memo', None),
                        defaults={
                            'block_hash': tx.get('block_hash'),
                            'block_time': tx.get('block_time'),
                            'block_height': tx.get('block_height'),
                            'raw': tx.get('raw')
                        },
                        fee=fee
                    )

                    BalanceChange.objects.update_or_create(
                        account=account_object,
                        address=address_obj,
                        transaction=tx_obj,
                        amount=tx.get('balance_change')
                    )

                    msg = {}
                    msg["txid"] = txid
                    msg["network"] = network
                    msg["symbol"] = network
                    msg["xpub"] = account_object.xpub
                    msg["fee_asset"] = 'ETH'
                    msg["network_fee"] = int(tx.get('fee', 0))
                    msg["balance_change"] = int(tx.get('balance_change'))
                    msg["balance_units"] = 'wei'
                    msg["blockheight"] = tx.get('block_height')
                    msg["blocktime"] = timestamp_to_unix(tx.get('block_time').__str__())
                    msg["is_dex_trade"] = tx.get('is_dex_trade')
                    msg["success"] = tx.get('success')
                    msg["thor_memo"] = tx.get('thor_memo', None)

                    if token_obj is not None:
                        msg["symbol"] = token_obj.symbol
                        msg["token_contract_address"] = token_obj.contract_address
                        msg["token_name"] = token_obj.name
                        msg["token_decimals"] = token_obj.precision
                        key = eth_balance_cache_key_format(address, token_obj.contract_address)
                    else:
                        key = eth_balance_cache_key_format(address)

                    redisClient.delete(key)

                    if tx.get('erc20_fee', False):
                        tx_type = 'fee'
                    elif msg["balance_change"] > 0:
                        tx_type = 'receive'
                    else:
                        tx_type = 'send'

                    msg["type"] = tx_type

                    rabbit_transactions.append(msg)

                    sync_eth_account_balances.s(address, False).apply_async()
                    if token_obj is not None:
                        sync_eth_token_balance.s(
                            address_obj.account.id,
                            address,
                            token_obj.symbol,
                            token_obj.contract_address
                        ).apply_async()

        # Create new list where we merge 2 dex messages per dex trade into 1 message per dex trade with buy and sell asset.
        rabbit_messages = []
        memo_prefix_out = 'OUT:'
        for msg in rabbit_transactions:
            thor_memo = msg.get('thor_memo')
            if msg.get('is_dex_trade') is False and thor_memo is None:
                rabbit_messages.append(msg)
            elif thor_memo is not None and memo_prefix_out in thor_memo:
                sell_txid = thor_memo[len(memo_prefix_out):]
                thor_tx = thorchain.get_valid_transaction(txid=sell_txid)
                if thor_tx:
                    msg = {**msg, **thor_tx}
                    rabbit_messages.append(msg)
            else:
                msg_matches = list(filter(lambda m: m.get('txid') == msg.get('txid'), rabbit_transactions))
                # Only use receive message to append to messages list. Ensures only 1 message per dex trade is published to rabbit.
                if msg.get('type') == 'receive':
                    for match in msg_matches:
                        if match.get('type') == 'receive':
                            msg["buy_asset"] = match.get('symbol')
                            msg['buy_asset_amount'] = match.get('balance_change')
                        elif match.get('type') == 'send':
                            msg["sell_asset"] = match.get('symbol')
                            msg['sell_asset_amount'] = -match.get('balance_change')
                    rabbit_messages.append(msg)

        # publish to rabbit
        publish_confirmed_txs = is_feature_enabled(PUBLISH_CONFIRMED_TXS)
        if publish_confirmed_txs:
            logger.info("Rabbit messages: %s", rabbit_messages)
            for msg in rabbit_messages:
                RabbitConnection().publish(exchange=EXCHANGE_TXS, routing_key='', message_type='event.platform.transaction', body=json.dumps(msg))
