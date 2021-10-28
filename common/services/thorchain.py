import requests
import logging
import time
from decimal import Decimal
from common.utils.networks import ETH, NETWORK_CONFIGS


logger = logging.getLogger('watchtower.common.services.thorchain')


THORCHAIN_PRECISION = 8

MAX_RETRIES = 10

class ThorchainClient:
    def __init__(self, api_url):
        super().__init__()
        self.API_URL = api_url

    @staticmethod
    def _int_to_decimal(value):
        if not value:
            return 0
        return value * pow(10, -THORCHAIN_PRECISION)

    @staticmethod
    def _decimal_to_int(value, precision):
        if not value:
            return 0
        return value * pow(10, precision)

    @staticmethod
    def _get_asset_precision(network, asset, contract_address):
        precision = THORCHAIN_PRECISION
        if network == ETH and asset != ETH:
            precision = NETWORK_CONFIGS[ETH]['precision']
            if contract_address is not None:
                from tracker.models import ERC20Token # circular import/defer loading 
                erc20 = ERC20Token.get_or_none(contract_address)
                if erc20:
                    precision = erc20.precision
        elif network in NETWORK_CONFIGS:
            precision = NETWORK_CONFIGS[network]['precision']
        return precision

    def get(self, endpoint, params):
        query_string = '&'.join(['{}={}'.format(k, v) for k, v in params.items()])
        url = '{api_url}{endpoint}?{query_string}'.format(
            api_url=self.API_URL,
            endpoint=endpoint,
            query_string=query_string
        )
        response = requests.get(url)
        try:
            return response.status_code, response.json()
        except Exception as e:
            logger.error('failed GET from %s: %s', self.API_URL, str(e))
            return response.status_code, response.text

    def get_transaction(self, txid):
        query_params = {
            'txid': txid,
            'type': 'swap',
            'limit': 1,
            'offset': 0
        }
        status, transaction = self.get('/actions', query_params)
        if status == 200 and int(transaction.get('count', 0)) > 0:
            return transaction
        else:
            logger.error('get transaction %s', status, transaction)
            return None

    def parse_transaction(self, tx):
        logger.info('parse transaction input %s', tx)
        try:
            sell_asset_network, sell_asset_symbol = tx['actions'][0]['in'][0]['coins'][0]['asset'].split('.')
            # Handle ERC20s
            sell_contract_address = None
            if sell_asset_network == ETH and sell_asset_symbol != ETH:
                sell_asset_symbol, sell_contract_address = sell_asset_symbol.split('-')
        except Exception as e:
            logger.error('error getting sell_asset_network and sell_asset_symbol %s', e)
            sell_asset_network = None
            sell_asset_symbol = None

        try:
            coins = tx['actions'][0]['in'][0]['coins']
            sell_asset_amount = sum(int(coin['amount']) for coin in coins) # sum all sends
            precision = self._get_asset_precision(sell_asset_network, sell_asset_symbol, sell_contract_address)
            decimal_amount = self._int_to_decimal(sell_asset_amount)
            sell_asset_amount = self._decimal_to_int(decimal_amount, precision)
        except Exception as e:
            logger.error('error getting sell_asset_amount %s', e)
            sell_asset_amount = None

        try:
            buy_asset_network, buy_asset_symbol = tx['actions'][0]['out'][0]['coins'][0]['asset'].split('.')
            # Handle ERC20s
            buy_contract_address = None
            if buy_asset_network == ETH and buy_asset_symbol != ETH:
                buy_asset_symbol, buy_contract_address = buy_asset_symbol.split('-')
        except Exception as e:
            logger.error('error getting buy_asset_network and buy_asset_symbol %s', e)
            buy_asset_network = None
            buy_asset_symbol = None

        try:
            coins = tx['actions'][0]['out'][0]['coins']
            buy_asset_amount = sum(int(coin['amount']) for coin in coins) # sum all sends
            precision = self._get_asset_precision(buy_asset_network, buy_asset_symbol, buy_contract_address)
            decimal_amount = self._int_to_decimal(buy_asset_amount)
            buy_asset_amount = self._decimal_to_int(decimal_amount, precision)
        except Exception as e:
            logger.error('error getting buy_asset_amount %s', e)
            buy_asset_amount = None

        try:
            liquidity_fee = int(tx['actions'][0]['metadata']['swap']['liquidityFee'])
            network_fee = int(tx['actions'][0]['metadata']['swap']['networkFees'][0]['amount'])
            fee_network, fee_asset = tx['actions'][0]['metadata']['swap']['networkFees'][0]['asset'].split('.')
            # Handle ERC20s
            fee_contract_address = None
            if fee_network == ETH and fee_asset != ETH:
                fee_asset, fee_contract_address = fee_asset.split('-')
            precision = self._get_asset_precision(fee_network, fee_asset, fee_contract_address)
            decimal_amount = self._int_to_decimal(network_fee)
            network_fee = self._decimal_to_int(decimal_amount, precision)
        except Exception as e:
            logger.error('error getting liquidity_fee and network_fee %s', e)
            liquidity_fee = None
            network_fee = None
            fee_network = None
            fee_asset = None

        thor_tx = {}
        thor_tx['sell_asset_amount'] = sell_asset_amount
        thor_tx['sell_asset_network'] = sell_asset_network
        thor_tx['sell_asset'] = sell_asset_symbol
        thor_tx['buy_asset_amount'] = buy_asset_amount
        thor_tx['buy_asset_network'] = buy_asset_network
        thor_tx['buy_asset'] = buy_asset_symbol
        thor_tx['buy_asset_network'] = buy_asset_network
        thor_tx['fee_asset'] = fee_asset
        thor_tx['fee_network'] = fee_network
        thor_tx['network_fee'] = network_fee
        thor_tx['liquidity_fee'] = liquidity_fee
        thor_tx['is_thor_trade'] = True
        thor_tx['success'] = True # required for rewards
        return thor_tx

    def validate_transaction (self, tx, retries = 0):
        logger.info('validate_transaction tx %s', tx)
        try:
            status = tx['actions'][0]['status'] # valid statuses are pending and success
            if status == 'success':
                return self.parse_transaction(tx=tx)
            if retries < MAX_RETRIES:
                time.sleep(10) # Sleep for 10 seconds to handle Midgard latency
                txid = tx['actions'][0]['in'][0]['txID']
                tx = self.get_transaction(txid=txid)
                retries += 1
                return self.validate_transaction(tx=tx, retries=retries)
            else:
                raise Exception('max retries exceeded')
        except Exception as e:
            logger.error('error getting successful transaction %s', e)

    def get_valid_transaction(self, txid):
        tx = self.get_transaction(txid=txid)
        if tx:
            return self.validate_transaction(tx=tx)
        else:
            return None
