import requests
import os
from common.utils.utils import multi_get
import logging
from common.utils.networks import ATOM, RUNE, SCRT, KAVA, OSMO
import json

logger = logging.getLogger('common.services.gaia_tendermint')

# Cosmos API swagger
# https://v1.cosmos.network/rpc/v0.42.6
#
# NOTE: REST endpoints are deprecated in cosmos-sdk 0.42.x / Gaid 5.0.0.  See this guide for migration instructions:
# https://docs.cosmos.network/master/migrations/rest.html

class TendermintGaiaClient:
    API_VERSION = int(os.environ.get('COSMOS_GAIACLI_API_VERSION') or '4')

    def __init__(self, network=ATOM):
        super().__init__()
        self.network = network
        self.baseurl = self.route(network)
        self.native_asset = self.get_native_asset(network)

    @staticmethod
    def route(n):
        return {
            ATOM: os.environ.get('COSMOS_GAIACLI_URL'),
            RUNE: os.environ.get('THORCHAIN_GAIACLI_URL'),
            KAVA: os.environ.get('KAVA_GAIACLI_URL'),
            SCRT: os.environ.get('SECRET_GAIACLI_URL'),
            OSMO: os.environ.get('OSMO_GAIACLI_URL'),
        }[n]

    def get_native_asset(self, a):
        return {
            ATOM: 'uatom',
            RUNE: 'rune',
            SCRT: 'uscrt',
            KAVA: 'ukava',
            OSMO: 'uosmo'
        }[a]

    def get(self, query_string, base_url = None):
        base = base_url
        if base_url == None:
            base = self.baseurl
        url = '{base_url}{query_string}'.format(
            base_url=base,
            query_string=query_string
        )
        response = requests.get(url)
        json_data = None
        try:
            json_data = response.json()
        except:
            logger.error('gaia_tendermint.get() request:{}, response: {}'.format(url, response))
        return json_data

    def post(self, query_string, data):
        url = '{base_url}{query_string}'.format(
            base_url=self.baseurl,
            query_string=query_string
        )

        response = requests.post(url, data=data)
        return response.json()

    # tx is a raw JSON string
    def broadcast(self, tx):
        response = self.post('/txs', tx)
        return response.get('txhash')

    def get_balance(self, address):
        balance = 0
        if self.network == ATOM:
            response = self.get('/cosmos/bank/v1beta1/balances/{}'.format(address))
            balances = response['balances']
        else:
            response = self.get('/bank/balances/{}'.format(address))
            balances = multi_get(response, 'result', default=None)
        for bal in balances:
             if bal['denom'] == self.native_asset:
                 balance = bal['amount']
        return balance

    def get_transactions(self, address):
        txs_sent = self.get_transactions_by_sender(address)
        txs_received = self.get_transactions_by_recipient(address)
        txs_swaps = self.get_transactions_by_actions(address)
        return txs_received + txs_sent + txs_swaps

    def get_latest_block_height(self):
        response = self.get('/blocks/latest')
        height = multi_get(response, 'block', 'header', 'height', default=None)
        return int(height)

    def get_block_at_height(self, height):
        response = self.get('/blocks/{}'.format(height))
        return response.get('block', None)

    def get_block_hash_at_height(self, height):
        response = self.get('/blocks/{}'.format(height))
        if self.API_VERSION == 4:
            return multi_get(response, 'block_id', 'hash', default=None)
        return multi_get(response, 'block_meta', 'block_id', 'hash', default=None)

    # NOTE: REST endpoints are deprecated in cosmos-sdk 0.42.x / Gaid 5.0.0.  See this guide for migration instructions:
    # https://docs.cosmos.network/master/migrations/rest.html
    def get_transactions_at_height(self, height):
        response = self.get_pages('/txs?tx.height={}'.format(height), 'txs')
        return response

    # NOTE: REST endpoints are deprecated in cosmos-sdk 0.42.x / Gaid 5.0.0.  See this guide for migration instructions:
    # https://docs.cosmos.network/master/migrations/rest.html
    def get_transactions_by_sender(self, address):
        txs = None
        if self.network in (RUNE, OSMO):
            txs = self.get_pages('/txs?message.sender={}'.format(address), 'txs')
        elif self.network in (ATOM, SCRT, KAVA):
            txs = self.get_pages('/txs?message.action=send&message.sender={}'.format(address), 'txs')
        else:
            print('Invalid network in get_transactions_by_sender: ', self.network)
        return txs if None else self.format_txs(txs)

    # NOTE: REST endpoints are deprecated in cosmos-sdk 0.42.x / Gaid 5.0.0.  See this guide for migration instructions:
    # https://docs.cosmos.network/master/migrations/rest.html
    def get_transactions_by_recipient(self, address):
        txs = None
        if self.network in (RUNE, OSMO):
            txs = self.get_pages('/txs?transfer.recipient={}'.format(address), 'txs')
        elif self.network in (ATOM, SCRT, KAVA):
            txs = self.get_pages('/txs?message.action=send&transfer.recipient={}'.format(address), 'txs')
        else:
            print('Invalid network in get_transactions_by_recipient: ', self.network)
        return txs if None else self.format_txs(txs)

    def get_transactions_by_actions(self, address):
        if self.network == 'RUNE':
            data = self.get_midgard_actions_by_address(address)
            actions = data.get('actions', [])

            transactions = []
            for action in actions:
                height = action.get('height')
                out = action.get('out', [{}])
                # TEMP FIX FOR FAILED REFUNDS
                if (len(out) is not 0):
                    out_data = self.parse_out_data(out)
                    in_address = action.get('in',[{}])[0].get('address')
                    to_address = out_data['to_address']
                    amount = out_data['amount']

                    response = self.get('/txs?tx.height={}'.format(height))
                    txs = response.get('txs', [])
                    updated_txs = self.add_actions_to_txs(txs, to_address, amount, in_address)
                    transactions = transactions + updated_txs

            return self.format_txs(transactions)
        if self.network == 'ATOM':
            return []
        if self.network == 'OSMO':
            return []

    def add_actions_to_txs(self, txs, to_address, amount, in_address):
        transactions = []
        for tx in txs:
            nested_txs = self.get_nested_transactions(tx)

            for nested_tx in nested_txs:
                from_addr = nested_tx.get('tx',{}).get('from_address', '')
                if from_addr != in_address:
                  continue
                
                id = nested_tx.get('tx', {}).get('id')
                findTxInArray = next((x for x in transactions if x.get('id') == id), None)
                if findTxInArray == None:
                    built_tx = tx
                    built_tx['tx']['value']['memo'] = 'OUT:' + id
                    built_tx['to_address'] = to_address
                    built_tx['amount'] = amount
                    built_tx['id'] = id

                    transactions.append(built_tx)
        return transactions

    def get_nested_transactions(self, tx):
        nested_txs = []
        msgs = tx.get('tx', {}).get('value', {}).get('msg', [{}])
        if (len(msgs) is not 0):
            nested_txs = msgs[0].get('value', {}).get('txs', [])
        return nested_txs

    def parse_out_data(self, out):
        obj = {}
        to_address = out[0].get('address')
        coins = out[0].get('coins', [{}])
        amount = 0
        if (len(coins) is not 0):
            amount = coins[0].get('amount', 0)
        obj['to_address'] = to_address
        obj['amount'] = amount
        return obj

    def get_pages(self, uri_string, key):
        items = []
        current_page = 1
        page_total = 1
        uri_string += '&page={}'
        while current_page <= page_total:  # page_total can be zero in the response...does not make sense to me
            response = self.get(uri_string.format(current_page))
            if 'error' in response:
                logger.error('error getting transactions {}'.format(response.get('error')))
                break
            items += response.get(key, [])
            page_total = int(response.get('page_total'))
            current_page += 1
        return items

    def format_txs(self, txs):
        if self.network == RUNE:
            return self.format_txs_rune(txs)
        elif self.network == ATOM:
            return self.format_txs_cosmos(txs)
        elif self.network == SCRT:
            return self.format_txs_secret(txs)
        elif self.network == KAVA:
            return self.format_txs_kava(txs)
        elif self.network == OSMO:
            return self.format_txs_osmo(txs)
        else:
            print('Invalid network in format_txs: ', self.network)
            return []

    def format_txs_cosmos(self, txs):
        txs_formatted = []
        for tx in txs:
            new_tx = self.format_tx_cosmos(tx)
            txs_formatted.append(new_tx)
        return txs_formatted

    def format_txs_rune(self, txs):
        txs_formatted = []
        for tx in txs:
            new_tx = self.format_tx_rune(tx)
            txs_formatted.append(new_tx)
        return txs_formatted

    def format_txs_secret(self, txs):
        txs_formatted = []
        for tx in txs:
            new_tx = self.format_tx_secret(tx)
            txs_formatted.append(new_tx)
        return txs_formatted

    def format_txs_kava(self, txs):
        txs_formatted = []
        for tx in txs:
            new_tx = self.format_tx_kava(tx)
            txs_formatted.append(new_tx)
        return txs_formatted

    def format_txs_osmo(self, txs):
        txs_formatted = []
        for tx in txs:
            new_tx = self.format_tx_osmo(tx)
            txs_formatted.append(new_tx)
        return txs_formatted

    def format_tx_rune(self, tx):
        # memo in rune MsgDeposit (from rune swap)
        memo = tx.get('tx', {}).get('value', {}).get('msg',[{}])[0].get('value', {}).get('memo')
        if memo is None:
          # memo in ObservedTxIn (to rune swap)
          memo = tx.get('tx', {}).get('value', {}).get('memo')

        new_tx = {
            'txid': tx.get('txhash'),
            'block_height': tx.get('height'),
            'block_hash': '',
            'block_time': tx.get('timestamp'),
            'raw': tx.get('raw_log'),
            'fee': self.get_fee(tx),
            'value': int(tx.get('amount', 0)),
            'thor_memo': memo
        }

        try:
            logs = json.loads(tx.get('raw_log'))
            for log in logs:
                events = log['events']
                for event in events:
                    if event['type'] == 'message' or event['type'] == 'transfer':
                        for attribute in event.get('attributes', []):
                            if attribute.get('key') == 'sender':
                                new_tx['from'] = attribute.get('value')
                            elif attribute.get('key') == 'recipient':
                                new_tx['to'] = attribute.get('value')
                            # there are attributes with keys but no values
                            elif attribute.get('key') == 'amount' and attribute.get('value'):
                                new_tx['value'] = int(attribute.get('value').replace('rune', ''))
                            elif attribute.get('key') == 'action' and attribute.get('value') == 'set_observed_txin':
                                new_tx['to'] = tx.get('to_address')
        except:
            logger.warning('error getting transaction details, txid: {}'.format(tx.get('txhash')))
        return new_tx

    def format_tx_osmo(self, tx):
        new_tx = {
            'txid': tx.get('txhash'),
            'block_height': tx.get('height'),
            'block_hash': '',
            'block_time': tx.get('timestamp'),
            'raw': tx.get('raw_log'),
            'fee': self.get_fee(tx),
            'value': int(tx.get('amount', 0)),
        }

        try:
            logs = json.loads(tx.get('raw_log'))
            for log in logs:
                events = log['events']
                for event in events:
                    if event['type'] == 'message' or event['type'] == 'transfer' or event['type'] == 'delegate' or event['type'] == 'unbond':
                        for attribute in event.get('attributes', []):
                            if attribute.get('key') == 'validator':
                                new_tx['validator'] = attribute.get('value')
                            if attribute.get('key') == 'action':
                                new_tx['type'] = attribute.get('value')
                            if attribute.get('key') == 'sender':
                                new_tx['from'] = attribute.get('value')
                            elif attribute.get('key') == 'recipient':
                                new_tx['to'] = attribute.get('value')
                            # there are attributes with keys but no values
                            elif attribute.get('key') == 'amount' and attribute.get('value'):
                                if "uosmo" in attribute.get('value'):
                                    new_tx['value'] = int(attribute.get('value').replace('uosmo', ''))
                                elif "gamm/pool/1" in attribute.get('value'):
                                    new_tx['type'] = 'pool'
                                    new_tx['value'] = int(attribute.get('value').replace('gamm/pool/1', ''))
                                elif "ibc/" in attribute.get('value'):
                                    new_tx['type'] = 'ibc'
                                    new_tx['value'] = int(attribute.get('value').split("ibc")[0])
                                else:
                                    new_tx['value'] = int(attribute.get('value'))
        except:
            logging.exception('')
            logger.warning('error getting transaction details, txid: {}'.format(tx.get('txhash')))
        return new_tx

    def format_tx_cosmos(self, tx):
        new_tx = {
            'txid': tx.get('txhash'),
            'block_height': tx.get('height'),
            'block_hash': '',
            'block_time': tx.get('timestamp'),
            'raw': tx.get('raw_log'),
            'fee': self.get_fee(tx),
            'value': 0
        }
        if self.API_VERSION == 4:
            new_tx['from'] = ''
            new_tx['to'] = ''
            tx_type = multi_get(tx, 'tx', 'type', default=None)
            if tx_type == 'cosmos-sdk/StdTx':
                msg = multi_get(tx, 'tx', 'value', 'msg', default=None)
                for m in msg:
                    if m['type'] == 'cosmos-sdk/MsgSend':
                        new_tx['from'] = multi_get(m, 'value', 'from_address', default='')
                        new_tx['to'] = multi_get(m, 'value', 'to_address', default='')
                        amount = multi_get(m, 'value', 'amount', default=[])
                        for amt in amount:
                            if amt['denom'] == self.native_asset:
                                new_tx['value'] = int(amt['amount'])
            return new_tx

    def format_tx_secret(self, tx):
        native_asset = self.get_native_asset(SCRT)
        raw_log = tx.get('raw_log')
        new_tx = {
            'txid': tx.get('txhash'),
            'block_height': tx.get('height'),
            'block_hash': '',
            'block_time': tx.get('timestamp'),
            'raw': raw_log,
            'fee': self.get_fee(tx),
            'value': 0
        }
        logs = []
        try:
            # raw_log is not always json
            logs = json.loads(raw_log)
        except:
            logger.info('Secret raw_log is not JSON parseable for txid: ', tx.get('txhash'))
        for log in logs:
            events = log['events']
            for event in events:
                if event['type'] == 'message' or event['type'] == 'transfer':
                    for attribute in event.get('attributes', []):
                        if attribute.get('key') == 'sender':
                            new_tx['from'] = attribute.get('value')
                        elif attribute.get('key') == 'recipient':
                            new_tx['to'] = attribute.get('value')
                        # there are attributes with keys but no values
                        elif attribute.get('key') == 'amount' and attribute.get('value') in native_asset:
                            new_tx['value'] = int(attribute.get('value').replace(native_asset, ''))
        return new_tx

    def format_tx_kava(self, tx):
        native_asset = self.get_native_asset(KAVA)
        raw_log = tx.get('raw_log')
        new_tx = {
            'txid': tx.get('txhash'),
            'block_height': tx.get('height'),
            'block_hash': '',
            'block_time': tx.get('timestamp'),
            'raw': raw_log,
            'fee': self.get_fee(tx),
            'value': 0
        }
        logs = []
        try:
            # raw_log is not always json, example value: "insufficient balance: 0usdx < 3000000000usdx: failed to execute message; message index: 0"
            logs = json.loads(raw_log)
        except:
            logger.info('KAVA raw_log is not JSON parseable for txid: ', tx.get('txhash'))
        for log in logs:
            events = log['events']
            for event in events:
                if event['type'] == 'message' or event['type'] == 'transfer':
                    for attribute in event.get('attributes', []):
                        if attribute.get('key') == 'sender':
                            new_tx['from'] = attribute.get('value')
                        elif attribute.get('key') == 'recipient':
                            new_tx['to'] = attribute.get('value')
                        # there are values that are not the native asset, for example "hard" instead of "ukava"
                        elif attribute.get('key') == 'amount' and attribute.get('value') in native_asset:
                            new_tx['value'] = int(attribute.get('value').replace(native_asset, ''))
        return new_tx

    def get_midgard_actions_by_txid(self, txid):
        response = self.get('/actions?txid={}&limit=1&offset=0'.format(txid), os.environ.get('MIDGARD_URL'))
        if 'error' in response:
            logger.error('error getting action form midgard {}'.format(response.get('error')))
        return response

    def get_midgard_actions_by_address(self, address):
        response = self.get('/actions?address={}&limit=50&offset=0'.format(address), os.environ.get('MIDGARD_URL'))
        if 'error' in response:
            logger.error('error getting action form midgard {}'.format(response.get('error')))
        return response

    @staticmethod
    def get_fee(tx):
        fee = 0
        fee_amounts = tx.get('tx', {}).get('value', {}).get('fee', {}).get('amount', [])
        for amt in fee_amounts:
            fee += int(amt.get('amount', 0))
        return fee


clients = {network: TendermintGaiaClient(network) for network in [ATOM, RUNE, SCRT, KAVA, OSMO]}


def get_client(network):
    if network not in clients:
        raise Exception('Gaia client is not supported for network: {}'.format(network))
    return clients[network]
