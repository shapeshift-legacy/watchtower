import json
import requests
import os

from datetime import datetime, timezone


class RippleClient:
    XRP_BASE_URL_REMOTE = 'https://s1.ripple.com:51234'
    XRP_BASE_URL = os.environ.get('RIPPLED_URL')

    # fail fast
    assert(XRP_BASE_URL), "os.environ.get('RIPPLED_URL') is {}".format(XRP_BASE_URL)

    def __init__(self):
        super().__init__()

    def _date_to_standard_format(self, date_seconds):
        if not date_seconds:
            return None
        date = datetime.fromtimestamp(self.ripple_to_unix_epoch(date_seconds), timezone.utc)
        STANDARD_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
        try:
            return datetime.strftime(date, STANDARD_DATE_FORMAT)
        except Exception as e:
            return None

    def ripple_to_unix_epoch(self, seconds):
        # https://xrpl.org/basic-data-types.html#specifying-time
        # ripple epoch is 946684800 seconds after the unix epoch
        return seconds + 946684800

    def _post(self, query_string, data, base_url=XRP_BASE_URL):
        url = '{base_url}{query_string}'.format(
            base_url=base_url,
            query_string=query_string
        )
        response = requests.post(url, data=json.dumps(data))
        try:
            return response.json()
        except:
            return response.text

    def get_latest_block_height(self):
        # https://xrpl.org/ledger_closed.html
        data = {
            'method': 'ledger_closed',
            'params': [],
        }
        return self._post('/', data).get('result', {}).get('ledger_index', {})

    def get_block_at_height(self, height, transactions=False, expand=False, is_retry=False):
        '''
        https://xrpl.org/ledger.html

        Returns dict
        {
            'ledger': {
                'accepted': True,
                'account_hash': '2D2762FDA138B0EB21821CA2FBFB91CB810C769202723F21CDD52E47C3F2D191',
                'close_flags': 0,
                'close_time': 639528330,
                'close_time_human': '2020-Apr-06 22:45:30.000000000',
                'close_time_resolution': 10,
                'closed': True,
                'hash': '2AC53B7CFAE7990E673F4F5085FF3032BA952631BB04FEE22B20F4B921B899B3',
                'ledger_hash': '2AC53B7CFAE7990E673F4F5085FF3032BA952631BB04FEE22B20F4B921B899B3',
                'ledger_index': '54618111',
                'parent_close_time': 639528322,
                'parent_hash': 'E0C27F500F39939BED6420C05079C593C9C7369FB6BDD777E1EF80B295201C80',
                'seqNum': '54618111',
                'totalCoins': '99991015566071335',
                'total_coins': '99991015566071335',
                'transaction_hash': 'EA02370856F8B942378902DED7E167C2C47997CD9B8D491AB0EA0EC0098816CB'
            },
            'ledger_hash': '2AC53B7CFAE7990E673F4F5085FF3032BA952631BB04FEE22B20F4B921B899B3',
            'ledger_index': 54618111,
            'status': 'success',
            'validated': True
        }
        or, if not yet validated
        {
            'ledger': {
                'closed': False,
                'ledger_index': '54618539',
                'parent_hash': '48FD7F12B49299116263B877A8D96F058A283811AC079AAF7F4D41929F13A7E8',
                'seqNum': '54618539'
            },
            'ledger_current_index': 54618539,
            'status': 'success',
            'validated': False
        }
        '''
        data = {
            'method': 'ledger',
            'params': [
                {
                    'ledger_index': int(height),
                    'binary': False,
                    'transactions': transactions,
                    'expand': expand,
                }
            ]
        }

        ledger = self._post('/', data=data).get('result')
        # if we have no
        if not ledger.get('status') == 'error' and ledger.get('validated'):
            return ledger

        if ledger.get('error') == 'lgrNotFound':
            # retry using remote node
            # this is fugly
            ledger = self._post('/', data=data, base_url=self.XRP_BASE_URL_REMOTE).get('result')
            if not ledger.get('status') == 'error' and ledger.get('validated'):
                return ledger

        return None

    def get_balance(self, address):
        # https://xrpl.org/account_info.html
        data = {
            'method': 'account_info',
            'params': [
                {
                    'account': address,
                    'ledger_index': 'current',
                    'queue': True,
                    'strict': True,
                }
            ]
        }
        return self._post('/', data=data).get('result', {}).get('account_data', {}).get('Balance')

    def get_raw_transaction(self, tx):
        # https://xrpl.org/tx.html
        data = {
            'method': 'tx',
            'params': [
                {
                    'transaction': tx,
                    'binary': False
                }
            ]
        }
        return self._post('/', data).get('result', {})

    def get_transactions_at_height(self, height):
        # requesting a block optionally includes txs - we leverage that here
        block = self.get_block_at_height(height, transactions=True, expand=True)
        if not block:
            return []
        return self._format_txs(block.get('ledger', {}).get('transactions', []), block)

    def get_transactions_by_account(self, account):
        # https://xrpl.org/account_tx.html
        data = {
            'method': 'account_tx',
            'params': [
                {
                    'account': account,
                    'binary': False,
                    'forward': False,
                    'ledger_index_max': -1,
                    'ledger_index_min': -1
                }
            ]
        }
        # TODO:
        # fix cointainer node - no txs being returned, i assume a tx indexing config is off
        response = self._post('/', data, base_url=self.XRP_BASE_URL_REMOTE)
        txs = response.get('result', {}).get('transactions', [])
        # standardize (flatten) txs to match those from a block
        txs = [tx.get('tx') for tx in txs]
        return self._format_txs(txs)

    def broadcast(self, tx):
        data = {
            'method': 'submit',
            'params': [
                {
                    'tx_blob': tx
                }
            ]
        }
        return self._post('/', data).get('result', {}).get('tx_json', {}).get('hash')

    def _filter_txs(self, txs):
        # https://xrpl.org/transaction-types.html
        # we only care about XRP to XRP txs
        # these are of type `Payment`, and will NOT have a `Paths` key
        tx_types = ('Payment',)
        return [tx for tx in txs if tx.get('TransactionType') in tx_types and not tx.get('Paths')]

    def _format_txs(self, txs, block=None):
        # rippled does not return all block information with the tx
        # if we supply the block, all txs are linked to that block (saves lookups)
        txs = self._filter_txs(txs)
        if not txs:
            return []
        formatted = []
        for tx in txs:
            # this is fugly
            _block = block or self.get_block_at_height(tx['ledger_index'])
            # if not _block:
            #     continue
            formatted.append(self._format_tx(tx, _block))
        return formatted

    def _format_tx(self, tx, block):
        if block is None:
            # make .get calls below safe
            block = {}
        new_tx = {
            'txid': tx.get('hash'),
            'block_height': block.get('ledger_index'),
            'block_hash': block.get('ledger_hash'),
            'block_time': self._date_to_standard_format(block['ledger']['close_time']),
            'raw': '',
            'fee': tx.get('Fee'),
            # if Amount is a dict then the asset is not XRP and we don't track it.
            # https://xrpl.org/issued-currencies.html
            'value': "0" if isinstance(tx.get('Amount'), dict) else tx.get('Amount'),
            'from': tx.get('Account'),
            'to': tx.get('Destination')
        }
        return new_tx
