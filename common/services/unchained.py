import logging
import os
import urllib3
import ast

from common.utils.requests import http
from common.utils.networks import ETH
from common.services import cointainer_web3 as web3
from common.utils.ethereum import ERC20_ABI


logger = logging.getLogger('watchtower.common.services.unchained')


class UnchainedClient(object):
    def __init__(self, network):
        baseurl = self.get_baseurl(network)

        if baseurl is None:
            raise Exception(
                'UnchainedClient is not supported for network: {}'.format(network)
            )

        self.network = network
        self.baseurl = baseurl

    @staticmethod
    def get_baseurl(network):
        return {
            ETH: os.getenv('UNCHAINED_ETH_URL')
        }.get(network)

    def get_balances(self, address, account_id, supported_tokens=None):
        if not address:
            logger.error("Unable to get %s balances for account: %s. No associated address.", self.network, account_id)
            return dict()

        resp = http.get('{}/api/v2/address/{}?details=tokenBalances'.format(self.baseurl, address)).json_data

        balances = {token.get('contract').lower(): token.get('balance') for token in resp.get('tokens', list())}
        balances[ETH] = resp.get('balance')

        try:
            weth_contract_address = supported_tokens.get('WETH') if supported_tokens and supported_tokens.get('WETH') else None
            if weth_contract_address:
                if balances.get(weth_contract_address) is None:
                    weth_address = web3.toChecksumAddress(weth_contract_address)
                    if weth_address:
                        contract = web3.eth.contract(address=weth_address, abi=ERC20_ABI)
                        balance = contract.functions.balanceOf(address).call()
                        balances[weth_address.lower()] = balance
        except Exception as e:
            logger.error("Failed to fetch WETH: %s balance for address: %s", weth_contract_address, address)
            logger.error(e)

        return balances


def get_client(network):
    return UnchainedClient(network)
