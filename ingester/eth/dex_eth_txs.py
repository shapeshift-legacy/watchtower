from common.services import cointainer_web3 as web3
import logging
import sha3

logger = logging.getLogger('watchtower.ingester.tasks')

WETH_CONTRACT_ADDRESS = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
ZX_PROXY_CONTRACT = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'

k = sha3.keccak_256()
k.update('Withdrawal(address,uint256)'.encode('utf-8'))
weth_withdrawal_topic = '0x' + k.hexdigest()

k = sha3.keccak_256()
k.update('Deposit(address,uint256)'.encode('utf-8'))
weth_deposit_topic = '0x' + k.hexdigest()

def get_dex_eth_deposits(block):
    block_hash = web3.toHex(block.get('hash'))
    block_height = block.get('number')
    logs = web3.eth.getLogs({
        'fromBlock': block_height,
        'toBlock': block_height,
        'topics': [weth_deposit_topic]
    })

    if len(logs) < 1:
        logger.info('No logs of type weth deposit found for block %s %s', block_height, block_hash)

    from_addresses  = dict()
    contract_addresses  = dict()
    weth_deposit_transactions = dict()

    for tx in block.transactions:
        from_addresses[tx.get('hash').hex()] = tx['from']
        contract_addresses[tx.get('hash').hex()] = tx['to']

    for log in logs:
        txid = web3.toHex(log.get('transactionHash'))
        log_contract_address = log.get('address').lower()
        contract_address = contract_addresses.get(txid)

        if contract_address != None:
            contract_address = contract_address.lower()

        if log_contract_address != WETH_CONTRACT_ADDRESS:
            continue

        if contract_address != ZX_PROXY_CONTRACT:
            continue

        weth_deposit_transactions[txid] = ({
            'txid': txid,
            'contract_address': contract_address,
            'from_address': from_addresses.get(txid),
            'to_address': contract_address,
            'block_height': block_height,
            'block_hash': block_hash,
            'amount': int(log.get('data'), 16)
        })

    return weth_deposit_transactions

def get_dex_eth_withdrawals(block):
    block_hash = web3.toHex(block.get('hash'))
    block_height = block.get('number')
    logs = web3.eth.getLogs({
        'fromBlock': block_height,
        'toBlock': block_height,
        'topics': [weth_withdrawal_topic]
    })

    if len(logs) < 1:
        logger.info('No logs of type weth withdrawal found for block %s %s', block_height, block_hash)

    from_addresses  = dict()
    contract_addresses  = dict()
    weth_withdrawal_transactions = dict()

    for tx in block.transactions:
        from_addresses[tx.get('hash').hex()] = tx['from']
        contract_addresses[tx.get('hash').hex()] = tx['to']

    for log in logs:
        txid = web3.toHex(log.get('transactionHash'))
        log_contract_address = log.get('address').lower()
        contract_address = contract_addresses.get(txid)

        if contract_address != None:
            contract_address = contract_address.lower()

        if log_contract_address != WETH_CONTRACT_ADDRESS:
            continue
        if contract_address != ZX_PROXY_CONTRACT:
            continue

        weth_withdrawal_transactions[txid] = ({
            'txid': txid,
            'contract_address': contract_address,
            'from_address': contract_address,
            'to_address': from_addresses.get(txid),
            'block_height': block_height,
            'block_hash': block_hash,
            'amount': int(log.get('data'), 16)
        })

    return weth_withdrawal_transactions

def get_dex_eth_txs(block):
    withdrawals = get_dex_eth_withdrawals(block)
    deposits = get_dex_eth_deposits(block)
    all = withdrawals.copy()
    all.update(deposits)
    return all
