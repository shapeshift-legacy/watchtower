import redis
import os

WATCH_ADDRESS_SET_KEY = 'watchtower:watch:address_set'
WATCH_ADDRESS_PREFIX = 'watchtower:watch:address:'
WATCH_TX_SET_KEY = 'watchtower:watch:tx:'

ETH_BLOCK_HEIGHT = 'watchtower:eth:block_height'
ATOM_BLOCK_HEIGHT = 'watchtower:atom:block_height'
RUNE_BLOCK_HEIGHT = 'watchtower:rune:block_height'
OSMO_BLOCK_HEIGHT = 'watchtower:osmo:block_height'
FIO_BLOCK_HEIGHT = 'watchtower:fio:block_height'
XRP_BLOCK_HEIGHT = 'watchtower:xrp:block_height'

BNB_BLOCK_QUEUE = 'watchtower:bnb:block_queue'
FIO_BLOCK_QUEUE = 'watchtower:fio:block_queue'
EOS_BLOCK_QUEUE = 'watchtower:eos:block_queue'

BNB_BLOCK_QUEUE_HEIGHT = 'watchtower:bnb:block_queue_height'
FIO_BLOCK_QUEUE_HEIGHT = 'watchtower:fio:block_queue_height'
EOS_BLOCK_QUEUE_HEIGHT = 'watchtower:eos:block_queue_height'

ETH_GAS_PRICE = 'watchtower:eth:gas_price'
ETH_EIP1559_FEES = 'watchtower:eth:eip1559_fees'
ETH_ACCOUNT = 'watchtower:eth:account:'
BTC_FEES = 'watchtower:btc:fees'
BTC_FEES_NODE = 'watchtower:btc:fees_node'

redisClient = redis.Redis(host=os.environ.get('REDIS_HOST'), port=os.environ.get('REDIS_PORT'), password='', decode_responses=True)
