from common.services import bitcoinfeesnode
from common.services.redis import redisClient, BTC_FEES_NODE
from common.utils.networks import BTC
import logging
import json

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('common.utils.bitcoin_node')

MIN_RELAY_FEE = 3000 # sats/kbyte
DEFAULT_FEE = None

"""
Cached Bitcoin Fees - Example:
{
  "fastest": { "maxMinutes": 35, "fee": 246784, "minMinutes": 0 },
  "halfHour": { "maxMinutes": 35, "fee": 246784, "minMinutes": 0 },
  "1hour": { "maxMinutes": 50, "fee": 211968, "minMinutes": 0 },
  "6hour": { "maxMinutes": 300, "fee": 138240, "minMinutes": 35 },
  "24hour": { "maxMinutes": 840, "fee": 1024, "minMinutes": 35 }
}

Fees in satoshis/kB
"""

def cache_bitcoin_fees():
    bitcoin_fees = bitcoinfeesnode.get_fees_list()
    conf_times = { 
        'fastest': {
            'maxMinutes': 36,
            'effort': 5,
            'fee': bitcoin_fees[0]
        },
        'halfHour': {
            'maxMinutes': 36,
            'effort': 4,
            'fee': bitcoin_fees[1]
        },
        '1hour': {
            'maxMinutes': 60,
            'effort': 3,
            'fee': bitcoin_fees[2]
        },
        '6hour': {
            'maxMinutes': 360,
            'effort': 2,
            'fee': bitcoin_fees[3]
        }, 
        '24hour': {
            'maxMinutes': 1440,
            'effort': 1,
            'fee': bitcoin_fees[4]
        }
    }

    return redisClient.set(BTC_FEES_NODE, json.dumps(conf_times))

def get_cached_bitcoin_fees():
    fees = redisClient.get(BTC_FEES_NODE)
    if fees is None:
        return None

    return json.loads(fees)
