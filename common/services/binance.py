import base64
import datetime
import json
import hashlib
import logging
import requests
import subprocess
import os
from decimal import Decimal
from dateutil import parser

from ..utils.networks import BNB, NETWORK_CONFIGS
from common.services.redis import redisClient as redis_client, BNB_BLOCK_QUEUE, BNB_BLOCK_QUEUE_HEIGHT


logger = logging.getLogger('watchtower.common.services.binance')


class BinanceClient(object):

    BASE_URL_API = os.environ.get('BINANCE_BNBCLI_URL')
    BASE_URL_RPC = os.environ.get('BINANCE_BNBNODE_URL')
    # fail fast
    assert(BASE_URL_API), "os.environ.get('BINANCE_BNBCLI_URL') is {}".format(BASE_URL_API)
    assert(BASE_URL_RPC), "os.environ.get('BINANCE_BNBNODE_URL') is {}".format(BASE_URL_RPC)

    # TODO:
    # we leverage a remote node for transactions by address (for initial sync)
    # this does not seem to be available on the node nor cli
    BASE_URL_DEX = 'https://dex-european.binance.org'

    def __init__(self):
        super().__init__()

    @staticmethod
    def _decimal_to_int(value):
        # left shift the decimal place according to precision (varies per coin)
        # i.e. 2.69709498 -> 269709498
        if not value:
            return 0
        return int(Decimal(value) * Decimal(10**NETWORK_CONFIGS[BNB]['precision']))

    @staticmethod
    def _date_to_standard_format(date_string):
        if not date_string:
            return None
        STANDARD_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S%z'
        try:
            return datetime.datetime.strftime(parser.parse(date_string), STANDARD_DATE_FORMAT)
        except Exception as e:
            logger.warn('Unable to convert DATETIME - {}'.format(e))
            return date_string

    def _get(self, query_string, base_url=BASE_URL_API):
        """
        Returns tuple -> (status_code, data)
        """
        url = '{base_url}{query_string}'.format(base_url=base_url, query_string=query_string)
        response = requests.get(url)
        try:
            return response.status_code, response.json()
        except:
            return response.status_code, response.text

    def _post(self, query_string, data, base_url=BASE_URL_API):
        """
        Returns tuple -> (status_code, data)
        """
        url = '{base_url}{query_string}'.format(base_url=base_url, query_string=query_string)
        response = requests.post(url, json=data)
        try:
            return response.status_code, response.json()
        except:
            return response.status_code, response.text

    def _get_rpc(self, query_string):
        return self._get(query_string, base_url=self.BASE_URL_RPC)

    def _get_dex(self, query_string):
        return self._get(query_string, base_url=self.BASE_URL_DEX)

    def dequeue_block(self):
        try:
            block = json.loads(redis_client.lpop(BNB_BLOCK_QUEUE))  # FIFO
            logger.debug('BNB dequeue block: {}'.format(block.get('height')))
            return block
        except:
            return None

    def queue_block(self, block):
        try:
            length = redis_client.rpush(BNB_BLOCK_QUEUE, json.dumps(block))  # FIFO
            logger.debug('BNB queue block: {} queue length: {}'.format(block.get('height'), length))
            return length
        except:
            return False

    def get_queue_block_height(self):
        try:
            return redis_client.get(BNB_BLOCK_QUEUE_HEIGHT)
        except Exception as e:
            logger.error('BNB get_queue_block_height: {}'.format(e))
            return None

    def set_queue_block_height(self, block):
        try:
            return redis_client.set(BNB_BLOCK_QUEUE_HEIGHT, block['height'])
        except Exception as e:
            logger.error('BNB set_queue_block_height: {}'.format(e))
            return False

    def get_account(self, address):
        status, response = self._get('/api/v1/account/{}'.format(address))
        if status == 200:
            return response
        return response

    def get_balance(self, address, asset=BNB):
        account = self.get_account(address)
        try:
            for coin in account['balances']:
                if coin['symbol'] == asset:
                    return self._decimal_to_int(coin['free'])
        except:
            return 0
        else:
            return 0

    def get_height(self):
        status, response = self._get_rpc('/status')
        if status == 200:
            return int(response['result']['sync_info']['latest_block_height'])
        return response

    def get_block(self, height=None):
        status, response = self._get_rpc('/block?height={}'.format(height) if height else '/block')
        if status == 200:
            block = response.get('result')
            if block is not None:
                if block.get('block_meta') is not None \
                    and block.get('block') is not None:
                        return self._format_block(block)
                logger.warn('Block beyond node history requested - {}'.format(height))
            else:
                logger.warn('Block response unexpected - {}'.format(response))
        return None

    def get_block_txs(self, block=None):
        if block is None:
            block = self.get_block()
        try:
            decoded_txs = self._decode_txs(block['txs'])
            return self._format_txs(decoded_txs, block)
        except TypeError as e:
            # no txs in block
            logger.info('BNB No txs in block - {}'.format(block['height']))
            return []
        except Exception as e:
            # this is a known issue on pioneer side, hence warning
            logger.warn('BNB {} Failed to decode txs for block - {}'.format(e, block['height']))
            return []

    def get_txs_for_height(self, height):
        status, response = self._get_rpc('/tx_search?query=\"tx.height={}\"'.format(height))
        if status == 200:
            block_txs = [base64.b64decode(tx['tx']).hex() for tx in response['result']['txs']]
            return self._format_txs(self._decode_txs(block_txs), self.get_block(height))
        return response

    def get_txs_for_address(self, address):
        NINETY_DAYS_AGO_IN_MS = int((datetime.datetime.now() - datetime.timedelta(days=90)).timestamp() * 1000)
        status, response = self._get_dex(
            '/api/v1/transactions?address={}&startTime={}&txAsset={}'.format(address, NINETY_DAYS_AGO_IN_MS, 'BNB')
        )
        if status == 200:
            return self._format_txs(response['tx'])
        return response

    def broadcast(self, tx):
        # https://docs.binance.org/api-reference/node-rpc.html#623-broadcasttxsync
        # tx is an amino encoded hex string i.e. "0xdb01f0625dee0a6...d2e518202f"
        status, response = self._get_rpc('/broadcast_tx_sync?tx={}'.format(tx))
        if status == 200:
            return response.get('result', {}).get('hash')
        return response

    def _get_tx_hash(self, b64_tx):
        return hashlib.sha256(base64.b64decode(b64_tx)).digest().hex().upper()

    def _decode_txs(self, txs):
        # support for decoding in python is basically non-existant
        # below leverages go-sdk via a built binary
        cmd = '/watchtower/common/utils/amino/amino-decoder {}'.format(' '.join(txs))
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()
        if not error:
            return list(zip(txs, json.loads(output)))
        return []

    def _format_block(self, block):
        try:
            return {
                'hash': block['block_meta']['block_id']['hash'],
                'height': int(block['block_meta']['header']['height']),
                'num_txs': block['block_meta']['header']['num_txs'],
                'previous_hash': block['block_meta']['header']['last_block_id']['hash'],
                'time': block['block_meta']['header']['time'],
                'txs': block['block']['data']['txs'],
            }
        except Exception as e:
            logger.error('_format_block: {}'.format(e))
            return None

    def _format_txs(self, decoded_txs, block=None):
        def _is_allowed_tx(tx):
            try:
                encoded, decoded = tx
                decoded['msg'][0]['inputs'][0]['address'] is not None
                decoded['msg'][0]['outputs'][0]['address'] is not None
                decoded['msg'][0]['inputs'][0]['coins'][0]['denom'] == 'BNB'
                decoded['msg'][0]['inputs'][0]['coins'][0]['amount'] is not None
                return True
            except Exception as e:
                return False
        try:
            if block is not None:
                return [self._format_tx(tx, block) for tx in decoded_txs if _is_allowed_tx(tx)]
        except:
            pass
        try:
            ALLOWED_TYPES = ('TRANSFER',)
            return [self._format_dex_tx(tx) for tx in decoded_txs if tx['txType'] in ALLOWED_TYPES]
        except:
            pass
        return []

    def _format_tx(self, tx, block):
        '''
        [
            {
                'msg': [
                    {
                        'inputs': [
                            {
                                'address': 'bnb1l6dxh9kz055vs0qkdn3n43y6tez38csj4q7x5d',
                                'coins': [{'denom': 'BNB', 'amount': 35012840862}]
                            }
                        ],
                        'outputs': [
                            {
                                'address': 'bnb1lc5c3paqzh55d7n7zd6dgvhaqq5905wzr849tj',
                                'coins': [{'denom': 'BNB', 'amount': 35012840862}]
                            }
                        ]
                    }
                ],
                'signatures': [
                    {
                        'pub_key': [
                            3, ..., 75
                        ],
                        'signature': 'P66nAeKx/671oBzc37WRnxxXCOxmIJOdCCZEEeSxiv1ualjMoI7sKDiZoTHzS6e1mpjqIa2MHYEM/Tq99+BfCQ==',
                        'account_number': 27586,
                        'sequence': 77
                    }
                ],
                'memo': '',
                'source': 0,
                'data': None
            }
        ]
        '''
        FEE_CONST = 37500  # binance uses a const fee structure of 0.000375 BNB for transfers
        encoded, decoded = tx
        return {
            'txid': self._get_tx_hash(encoded),
            'block_height': block['height'],
            'block_hash': block['hash'],
            'block_time': self._date_to_standard_format(block['time']),
            'raw': '',
            'from': decoded['msg'][0]['inputs'][0]['address'],
            'to': decoded['msg'][0]['outputs'][0]['address'],
            'asset': decoded['msg'][0]['inputs'][0]['coins'][0]['denom'],
            'value':  decoded['msg'][0]['inputs'][0]['coins'][0]['amount'],
            'fee': FEE_CONST,
        }

    def _format_dex_tx(self, tx):
        return {
            'txid': tx.get('txHash', '').upper(),
            'block_height': tx.get('blockHeight'),
            'block_hash': '',
            'block_time': self._date_to_standard_format(tx.get('timeStamp')),
            'raw': '',
            'from': tx.get('fromAddr'),
            'to': tx.get('toAddr'),
            'asset': tx.get('txAsset'),
            'value': self._decimal_to_int(tx.get('value')),
            'fee': self._decimal_to_int(tx.get('txFee')),
        }
