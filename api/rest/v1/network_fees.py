from common.utils.ethereum import get_cached_gas_price, get_cached_eip1559_fees
import logging

from django.http import JsonResponse
from rest_framework.views import APIView
from common.utils.bitcoin_node import get_cached_bitcoin_fees
from common.utils.transactions import COIN_DEFAULTS
from common.utils.networks import BTC, ETH

logger = logging.getLogger('watchtower.network_fees')
class NetworkFeesPage(APIView):

    def get(self, request):

        response = {}
        for network in COIN_DEFAULTS:

            if network == BTC:
                response[network] = {
                    'network': network,
                    'fee': get_cached_bitcoin_fees(),
                    'units': 'sats/kb'
                }
            elif network == ETH:
                gas_price = get_cached_gas_price()
                eip1559_fees = get_cached_eip1559_fees()
                priority_fee_per_gas = eip1559_fees.get('priorityFeePerGas', 'unknown')
                base_fee_per_gas = eip1559_fees.get('baseFeePerGas', 'unknown')

                response[network] = {
                    'network': network,
                    'gasPrice': gas_price,
                    'baseFeePerGas': base_fee_per_gas,
                    'priorityFeePerGas': priority_fee_per_gas,
                    'units': 'wei'
                }
            else:
                response[network] = {
                    'network': network, 
                    'fee': COIN_DEFAULTS[network].get('FEE_PER_KB', 'unkown'),
                    'units': 'sats/kb'
                }

        return JsonResponse({
            'success': True,
            'data': response
        })
