from common.services import cointainer_web3 as web3
import logging
from common.utils.ethereum import THOR_ROUTER_ABI
import sha3

logger = logging.getLogger('watchtower.ingester.tasks')

k = sha3.keccak_256()
k.update('TransferOut(address,address,address,uint256,string)'.encode('utf-8'))
incoming_thor_topic = '0x' + k.hexdigest()

k = sha3.keccak_256()
k.update('Deposit(address,address,uint256,string)'.encode('utf-8'))
outgoing_thor_topic = '0x' + k.hexdigest()

thor_deposit_contract = web3.eth.contract(address= web3.toChecksumAddress('0x0000000000000000000000000000000000000000'), abi=THOR_ROUTER_ABI)

def get_incoming_thor_txs(block):
  block_hash = web3.toHex(block.get('hash'))  
  block_height = block.get('number')

  logs = web3.eth.getLogs({
      'fromBlock': block_height,
      'toBlock': block_height,
      'topics': [incoming_thor_topic]
  })

  incoming_thor_txs = dict()
  contract_addresses = dict()

  for tx in block.transactions:
      contract_addresses[tx.get('hash').hex()] = tx['to']

  for log in logs:
    txid = str(log['transactionHash'].hex())
    receipt = web3.eth.getTransactionReceipt(txid)
    transferOut = thor_deposit_contract.events.TransferOut()

    try:
      logsDecoded = transferOut.processReceipt(receipt)
      memo = str(logsDecoded[0]['args']['memo'])
      vault = str(logsDecoded[0]['args']['vault'])
      to = str(logsDecoded[0]['args']['to'])
      amount = str(logsDecoded[0]['args']['amount'])
    except:
      logsDecoded = None

    if logsDecoded is not None:
      contract_address = str(contract_addresses.get(txid))
      incoming_thor_txs[txid]= ({
        'thor_memo': memo,
        'contract_address': contract_address,
        'from_address': vault,
        'to_address': to,
        'block_height': block_height,
        'block_hash': block_hash,
        'amount': amount
      })

  return incoming_thor_txs

def get_outgoing_thor_txs(block):
  block_hash = web3.toHex(block.get('hash'))  
  block_height = block.get('number')

  logs = web3.eth.getLogs({
      'fromBlock': block_height,
      'toBlock': block_height,
      'topics': [outgoing_thor_topic]
  })

  outgoing_thor_txs = dict()
  contract_addresses = dict()
  from_addresses = dict()

  for tx in block.transactions:
      contract_addresses[tx.get('hash').hex()] = tx['to']
      from_addresses[tx.get('hash').hex()] = tx['from']

  for log in logs:
    txid = str(log['transactionHash'].hex())
    receipt = web3.eth.getTransactionReceipt(txid)
    deposit = thor_deposit_contract.events.Deposit()

    try:
      logsDecoded = deposit.processReceipt(receipt)
      memo = str(logsDecoded[0]['args']['memo'])
      amount = str(logsDecoded[0]['args']['amount'])
    except:
      logsDecoded = None

    if logsDecoded is not None:
      to = str(contract_addresses.get(txid))
      from_address = str(from_addresses.get(txid))
      contract_address = str(contract_addresses.get(txid))

      outgoing_thor_txs[txid]= ({
        'thor_memo': memo,
        'contract_address': contract_address,
        'from_address': from_address,
        'to_address': to,
        'block_height': block_height,
        'block_hash': block_hash,
        'amount': amount
      })

  return outgoing_thor_txs

def get_thor_txs(block):
  incoming = get_incoming_thor_txs(block)
  outgoing = get_outgoing_thor_txs(block)
  all = incoming.copy()
  all.update(outgoing)
  return all