from web3.gas_strategies.rpc import rpc_gas_price_strategy
from common.services.redis import redisClient, ETH_GAS_PRICE, ETH_EIP1559_FEES, ETH_ACCOUNT
from ethtoken.abi import EIP20_ABI

from common.services import etherscan, ethereumfees, ethereum_json_rpc
from common.services import cointainer_web3 as web3


import math
import logging
import json

logger = logging.getLogger('common.utils.ethereum')


ETHEREUM_DECIMAL_PRECISION = 18
ETHEREUM_CHAIN_ID = 1
ETH_TX_PAGE_SIZE = 1000
ETH_MAX_TXS = 10000
ETHEREUM_GAS_PRICE_FLOOR = 10000000000


def get_balance(address):
    return etherscan.get_balance(address)


def get_token_balance(contract_address, address):
    return etherscan.get_token_balance(contract_address, address)


def gen_get_all_ethereum_transactions(address):
    page = 1
    while True and page <= int( math.ceil(ETH_MAX_TXS/ETH_TX_PAGE_SIZE) ):
        response = etherscan.get_ethereum_transactions(address=address, page=page, limit=ETH_TX_PAGE_SIZE)
        page += 1
        if response == []:
            return

        for tx in response:
            yield tx


def gen_get_all_internal_ethereum_transactions(address):
    page = 1
    while True and page <= int( math.ceil(ETH_MAX_TXS/ETH_TX_PAGE_SIZE) ):
        response = etherscan.get_internal_ethereum_transactions(address=address, page=page, limit=ETH_TX_PAGE_SIZE)
        page += 1

        if response == []:
            return

        for tx in response:
            # Add blockHash to each internal tx since they dont have them by
            # default from etherscan
            tx['blockHash'] = 'unknown'
            yield tx


def gen_get_all_token_transactions(address):
    page = 1
    while True and page <= int( math.ceil(ETH_MAX_TXS/ETH_TX_PAGE_SIZE) ):
        response = etherscan.get_token_transfer_events(address=address, page=page, limit=ETH_TX_PAGE_SIZE)
        page += 1

        if response == []:
            return

        for tx in response:
            yield tx


def calculate_balance_change(address, transaction, is_erc20_fee):
    balance_change = 0.0

    address_to = transaction['to']
    address_from = transaction['from']
    transfer_value = float(transaction['value'])

    is_send = address_from.lower() == address.lower()
    is_receive = address_to.lower() == address.lower()
    is_token = 'tokenName' in transaction
    is_error = True if transaction.get('isError', '0') == '1' else False

    if is_erc20_fee:
        return -calculate_ethereum_transaction_fee(transaction)

    if is_receive and not is_error:
        balance_change += transfer_value

    if is_send and not is_error:
        balance_change -= transfer_value

    if is_send and not is_token:
        balance_change -= calculate_ethereum_transaction_fee(transaction)

    return balance_change

def calculate_dex_balance_change(address, transaction, erc_dex_trade, dex_withdraw_trade, dex_deposit_trade, is_erc20_fee, success):
    if success == False or is_erc20_fee:
        return -calculate_ethereum_transaction_fee(transaction)
    if dex_withdraw_trade:
        return float(transaction['value'])
    if dex_deposit_trade:
        return -float(transaction['value'])
    if erc_dex_trade:
        is_erc20_send = transaction['from'].lower() == address.lower()
        is_erc20_receive = transaction['to'].lower() == address.lower()
        if is_erc20_receive:
            return float(transaction['value'])
        if is_erc20_send:
            return -float(transaction['value'])


def calculate_ethereum_transaction_fee(transaction):
    gas_used = float(transaction.get('gasUsed', 0))
    gas_price = float(transaction.get('gasPrice', 0))
    ethereum_fee = gas_used * gas_price
    return ethereum_fee


def format_balance(value, decimals):
    balance_string_format = '{{0:.{}f}}'.format(8)
    formatted = balance_string_format.format(value / (10 ** decimals))
    formatted = formatted.rstrip('0').rstrip('.')
    return float(formatted)


def format_address(address):
    return web3.toChecksumAddress(address)

# get recommended gas price using web3 calls to our node
def cache_gas_price():
    #get node recommended
    web3.eth.setGasPriceStrategy(rpc_gas_price_strategy)
    gas_price_node = web3.eth.generateGasPrice()

    #get remote
    gas_price_remote = ethereumfees.get_fees_fast()

    # cache best fee
    gas_price_options = [gas_price_node,gas_price_remote,ETHEREUM_GAS_PRICE_FLOOR]
    gas_price = max(gas_price_options)
    return redisClient.set(ETH_GAS_PRICE, str(gas_price))

def get_cached_gas_price():
    return redisClient.get(ETH_GAS_PRICE)


# gets maxPriorityFeePerGas from the geth node.
# Todo - when ethgasstation.info api adds eip1559 support, compare to the node fee and use the highest
def cache_eip1559_fees():
    fees = {}
    try:
        block_by_height = web3.eth.getBlock('latest', False)
        base_fee_per_gas = int(block_by_height.get('baseFeePerGas', None), 16)
        max_priority_fee_per_gas = int(ethereum_json_rpc.get_max_priority_fee_per_gas(), 16)

        fees = {
            'baseFeePerGas': base_fee_per_gas,
            'priorityFeePerGas': max_priority_fee_per_gas
        }
    except Exception as e:
        print('Error getting Ethereum fees from the node: {}'.format(str(e)))

    return redisClient.set(ETH_EIP1559_FEES, json.dumps(fees))

def get_cached_eip1559_fees():
    fees = redisClient.get(ETH_EIP1559_FEES)
    if fees is None:
        return None
    return json.loads(fees)

def estimate_ethereum_gas_used(transaction_params):
    gas_used = web3.eth.estimateGas(transaction_params)
    return gas_used


def estimate_ethereum_gas_limit(transaction_params):
    safety_margin = 0.1  # add 10%
    gas_used = estimate_ethereum_gas_used(transaction_params)
    gas_limit = round(gas_used * (1.0 + safety_margin))
    return gas_limit

def estimate_token_gas_used(contract_address, from_address, to_address, value):
    contract = web3.eth.contract(address=contract_address, abi=EIP20_ABI)
    transfer = contract.functions.transfer(to_address, value)
    gas_used = transfer.estimateGas({'from': from_address})

    return gas_used


def estimate_token_gas_limit(contract_address, from_address, to_address, value):
    safety_margin = 0.1  # add 10%
    gas_used = estimate_token_gas_used(contract_address, from_address, to_address, value)
    gas_limit = round(gas_used * (1.0 + safety_margin))
    return gas_limit


def get_token_transfer_data(contract_address, from_address, to_address, value, gas, gas_price, nonce):
    contract = web3.eth.contract(address=contract_address, abi=EIP20_ABI)
    transfer = contract.functions.transfer(to_address, value)
    transaction = transfer.buildTransaction({
        'chainId': ETHEREUM_CHAIN_ID,
        'gas': gas,
        'gasPrice': gas_price,
        'nonce': nonce
    })
    return transaction['data']


def get_transaction_count(address):
    return web3.eth.getTransactionCount(format_address(address))


def eth_balance_cache_key_format(eth_addr, contract_addr=""):
    if contract_addr:
        return "{}{}_{}:balance".format(ETH_ACCOUNT, contract_addr.lower(), eth_addr.lower())

    return "{}{}:balance".format(ETH_ACCOUNT, eth_addr.lower())

ERC20_ABI = """
[
    {
        "constant": true,
        "inputs": [],
        "name": "name",
        "outputs": [
            {
                "name": "",
                "type": "string"
            }
        ],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {
                "name": "_spender",
                "type": "address"
            },
            {
                "name": "_value",
                "type": "uint256"
            }
        ],
        "name": "approve",
        "outputs": [
            {
                "name": "",
                "type": "bool"
            }
        ],
        "payable": false,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [
            {
                "name": "",
                "type": "uint256"
            }
        ],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {
                "name": "_from",
                "type": "address"
            },
            {
                "name": "_to",
                "type": "address"
            },
            {
                "name": "_value",
                "type": "uint256"
            }
        ],
        "name": "transferFrom",
        "outputs": [
            {
                "name": "",
                "type": "bool"
            }
        ],
        "payable": false,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [
            {
                "name": "",
                "type": "uint8"
            }
        ],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [
            {
                "name": "_owner",
                "type": "address"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "name": "balance",
                "type": "uint256"
            }
        ],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "symbol",
        "outputs": [
            {
                "name": "",
                "type": "string"
            }
        ],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {
                "name": "_to",
                "type": "address"
            },
            {
                "name": "_value",
                "type": "uint256"
            }
        ],
        "name": "transfer",
        "outputs": [
            {
                "name": "",
                "type": "bool"
            }
        ],
        "payable": false,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [
            {
                "name": "_owner",
                "type": "address"
            },
            {
                "name": "_spender",
                "type": "address"
            }
        ],
        "name": "allowance",
        "outputs": [
            {
                "name": "",
                "type": "uint256"
            }
        ],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "payable": true,
        "stateMutability": "payable",
        "type": "fallback"
    },
    {
        "anonymous": false,
        "inputs": [
            {
                "indexed": true,
                "name": "owner",
                "type": "address"
            },
            {
                "indexed": true,
                "name": "spender",
                "type": "address"
            },
            {
                "indexed": false,
                "name": "value",
                "type": "uint256"
            }
        ],
        "name": "Approval",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {
                "indexed": true,
                "name": "from",
                "type": "address"
            },
            {
                "indexed": true,
                "name": "to",
                "type": "address"
            },
            {
                "indexed": false,
                "name": "value",
                "type": "uint256"
            }
        ],
        "name": "Transfer",
        "type": "event"
    }
]
"""

THOR_ROUTER_ABI = """
[{"inputs":[],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":true,"internalType":"address","name":"asset","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":false,"internalType":"string","name":"memo","type":"string"}],"name":"Deposit","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"oldVault","type":"address"},{"indexed":true,"internalType":"address","name":"newVault","type":"address"},{"indexed":false,"internalType":"address","name":"asset","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":false,"internalType":"string","name":"memo","type":"string"}],"name":"TransferAllowance","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"vault","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"address","name":"asset","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":false,"internalType":"string","name":"memo","type":"string"}],"name":"TransferOut","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"oldVault","type":"address"},{"indexed":true,"internalType":"address","name":"newVault","type":"address"},{"components":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"indexed":false,"internalType":"struct Router.Coin[]","name":"coins","type":"tuple[]"},{"indexed":false,"internalType":"string","name":"memo","type":"string"}],"name":"VaultTransfer","type":"event"},{"inputs":[],"name":"RUNE","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address[]","name":"recipients","type":"address[]"},{"components":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"internalType":"struct Router.Coin[]","name":"coins","type":"tuple[]"},{"internalType":"string[]","name":"memos","type":"string[]"}],"name":"batchTransferOut","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address payable","name":"vault","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"string","name":"memo","type":"string"}],"name":"deposit","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"router","type":"address"},{"internalType":"address payable","name":"asgard","type":"address"},{"components":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"internalType":"struct Router.Coin[]","name":"coins","type":"tuple[]"},{"internalType":"string","name":"memo","type":"string"}],"name":"returnVaultAssets","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"router","type":"address"},{"internalType":"address","name":"newVault","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"string","name":"memo","type":"string"}],"name":"transferAllowance","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address payable","name":"to","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"string","name":"memo","type":"string"}],"name":"transferOut","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"}],"name":"vaultAllowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
"""
