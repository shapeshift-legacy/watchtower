"""
CoinQuery Python Client

Based on Insight API (https://github.com/bitpay/insight-api)
"""
import logging
import os
import urllib3

from common.utils.requests import requests_util, http
from common.utils.networks import SUPPORTED_NETWORKS, BTC, BCH, DASH, DGB, ETH, LTC, DOGE, ATOM, BNB, EOS, XRP, FIO, RUNE, SCRT, KAVA, OSMO


logger = logging.getLogger('watchtower.common.services.coinquery')
apikey = 'watchtower-' + os.environ.get('ENV')


class CoinQueryClient(object):
    def __init__(self, network=BTC):
        self.network = network
        self.baseurl = self.route(network)

    # switch on network
    @staticmethod
    def route(n):
        return {
            'BTC': "{}/{}".format(os.environ.get('COINQUERY_URL'), BTC.lower()),
            'BCH': "{}/{}".format(os.environ.get('COINQUERY_URL'), BCH.lower()),
            'DGB': "{}/{}".format(os.environ.get('COINQUERY_URL'), DGB.lower()),
            'LTC': "{}/{}".format(os.environ.get('COINQUERY_URL'), LTC.lower()),
            'DOGE': "{}/{}".format(os.environ.get('COINQUERY_URL'), DOGE.lower()),
            'DASH': "{}/{}".format(os.environ.get('COINQUERY_URL'), DASH.lower()),
            # so that our pseudo-switch statement doesn't fail
            'ETH': ETH,
            'FIO': FIO,
            'ATOM': ATOM,
            'BNB': BNB,
            'EOS': EOS,
            'XRP': XRP,
            'RUNE': RUNE,
            'SCRT': SCRT,
            'KAVA': KAVA,
            'OSMO': OSMO,
        }[n]

    def get_transactions(self, addresses, page_size=50):
        if not addresses:
            return []

        address_str = ','.join(addresses)

        def get_url(page):
            _from = page * page_size
            _to = _from + page_size
            url = '{}/addrs/{}/txs?from={}&to={}&apikey={}'.format(self.baseurl, address_str, _from, _to, apikey)
            return url

        resp = http.get(get_url(0)).json_data
        total_transactions = resp.get('totalItems')
        total_pages = (total_transactions // page_size) + 1

        if total_pages <= 1:
            return resp.get('items')
        else:
            urls = [get_url(page) for page in range(total_pages)]
            txs = []
            for url in urls:
                resp = http.get(url, retries=2)
                txs += resp.json_data.get('items', [])

            return txs

    def get_transactions_by_block_hash(self, block_hash, page=None):
        def get_url(page_x):
            url = '{}/txs?block={}&pageNum={}&apikey={}'.format(self.baseurl, block_hash, page_x if page_x is not None else 0, apikey)

            return url

        resp = http.get(get_url(page), retries=urllib3.Retry(3, backoff_factor=1.0))

        if page is not None:
            return resp.json_data.get('txs')
        else:
            total_pages = resp.json_data.get('pagesTotal', 0)
            urls = [get_url(i) for i in range(total_pages)]
            txs = []
            for resp in requests_util.get_multiple(urls):
                txs += resp.json_data.get('txs', [])

            return txs

    def get_transactions_for_txids(self, txids, precise=False):
        baseurl = self.baseurl
        query_params = "?apikey={}".format(apikey)

        # CQ doesn't have Dash extraPayload/extraPayloadSize yet, so as a
        # crutch, grab this from dash.org instead:
        if precise and self.network == DASH:
            baseurl = "https://insight.dash.org/insight-api"
            query_params = ""

        urls = ['{}/tx/{}{}'.format(baseurl, txid, query_params) for txid in set(txids)]
        tx_map = {}
        for resp in requests_util.get_multiple(urls):
            tx = resp.json_data
            tx_map[tx['txid']] = tx
        return tx_map

    def get_raw_transactions_for_txids(self, txids):
        baseurl = self.baseurl
        txid_dict = {}
        for txid in set(txids):
            txid_dict[txid] = {}
            txid_dict[txid]['url'] = '{}/rawtx/{}'.format(baseurl, txid)

        raw_tx_map = {}
        for txid, value in requests_util.get_multiple_from_dictionary(txid_dict).items():
            tx = value['response'].json_data
            raw_tx_map[txid] = tx['rawtx']

        return raw_tx_map

    def get_block_by_hash(self, block_hash):
        url = '{}/block/{}?apikey={}'.format(self.baseurl, block_hash, apikey)
        resp = http.get(url)
        return resp.json_data

    def get_last_block_hash(self):
        url = '{}/status?q=getLastBlockHash&apikey={}'.format(self.baseurl, apikey)
        resp = http.get(url)
        return resp.json_data.get('lastblockhash')

    def get_next_block_hash(self, block_hash):
        block = self.get_block_by_hash(block_hash)
        return block.get('nextblockhash')

    def get_utxos_for_addresses(self, addresses):
        def make_url(addresses):
            address_str = ','.join(addresses)
            return '{}/addrs/{}/utxo?apikey={}'.format(self.baseurl, address_str, apikey)

        addresses_per_request = 50
        address_groups = [addresses[i: i + addresses_per_request] for i in range(0, len(addresses), addresses_per_request)]  # noqa
        urls = [make_url(address_group) for address_group in address_groups]

        utxos = []
        for resp in requests_util.get_multiple(urls):
            for utxo in list(resp.json_data):
                # fill in missing values
                has_amount = 'amount' in utxo
                has_satoshis = 'satoshis' in utxo
                if has_amount and not has_satoshis:
                    utxo['satoshis'] = int(utxo['amount'] * (10 ** 8))
                utxos.append(utxo)

        return utxos

    def send(self, rawtx):
        url = '{}/tx/send?apikey={}'.format(self.baseurl, apikey)
        body = {'rawtx': rawtx}
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

        # Retry the broadcast up to 3 times (workaround for 104 Connection Reset By Peer)
        # Enable retry explicitly for POST via method_whitelist
        retry = urllib3.Retry(total=3,
                              method_whitelist=['POST'])
        resp = http.post(url, body=body, headers=headers, retries=retry)

        return resp.json_data.get('txid')

clients = {network: CoinQueryClient(network) for network in SUPPORTED_NETWORKS}

def get_client(network):
    if network not in clients:
        raise Exception('CoinQuery client is not supported for network: {}'.format(network))
    return clients[network]
