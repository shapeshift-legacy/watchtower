from common.services import bitcoinfees
from common.services.redis import redisClient, BTC_FEES
from common.utils.networks import BTC
import logging
import json

logger = logging.getLogger('common.utils.bitcoin')

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
    bitcoin_fees = bitcoinfees.get_fees_list()
    conf_times = { 
        'fastest': {
            'maxMinutes': 36,
            'effort': 5,
            'fee': DEFAULT_FEE
        },
        'halfHour': {
            'maxMinutes': 36,
            'effort': 4,
            'fee': DEFAULT_FEE
        },
        '1hour': {
            'maxMinutes': 60,
            'effort': 3,
            'fee': DEFAULT_FEE
        },
        '6hour': {
            'maxMinutes': 360,
            'effort': 2,
            'fee': DEFAULT_FEE
        }, 
        '24hour': {
            'maxMinutes': 1440,
            'effort': 1,
            'fee': DEFAULT_FEE
        }
    }

    for time in conf_times:
        for fee in bitcoin_fees:
            if int(fee['maxMinutes']) < conf_times[time]['maxMinutes']:
                conf_times[time]['fee'] = max((fee['minFee'] * 1024), MIN_RELAY_FEE)
                conf_times[time]['minMinutes'] = fee['minMinutes']
                conf_times[time]['maxMinutes'] = fee['maxMinutes']
                break
        # sometimes there is not a fee for the desired confirmation time, in this case use the highest
        if conf_times[time]['fee'] is None:
            conf_times[time]['fee'] = max((bitcoin_fees[-1]['minFee'] * 1024), MIN_RELAY_FEE)

    return redisClient.set(BTC_FEES, json.dumps(conf_times))

def get_cached_bitcoin_fees():
    fees = redisClient.get(BTC_FEES)
    if fees is None:
        return None

    return json.loads(fees)
