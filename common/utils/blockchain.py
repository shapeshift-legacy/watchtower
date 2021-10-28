from django.core.cache import cache

from common.services.coinquery import get_client as get_coinquery_client
from common.services import etherscan, binance_client, ripple, get_gaia_client
from common.utils.networks import ATOM, BNB, ETH, XRP, FIO, RUNE


LAST_BLOCK_CACHE_FORMAT = 'latest-block-height-{network}'
LAST_BLOCK_CACHE_TTL = 10  # seconds


def get_latest_block_height(network, ignore_cache=False):
    def is_valid(height):
        return isinstance(height, int)

    cache_key = LAST_BLOCK_CACHE_FORMAT.format(network=network)
    cached_value = cache.get(cache_key)

    if not ignore_cache and is_valid(cached_value):
        return cached_value

    if network == ETH:
        last_block_height = etherscan.get_latest_block_height()
    elif network == BNB:
        last_block_height = binance_client.get_latest_block_height()
    elif network == XRP:
        last_block_height = ripple.get_latest_block_height()
    elif network in [ATOM, RUNE]:
        gaia = get_gaia_client(newtork)
        last_block_height = gaia.get_latest_block_height()
    else:
        coinquery = get_coinquery_client(network)
        last_block_hash = coinquery.get_last_block_hash()
        last_block_height = coinquery.get_block_by_hash(last_block_hash).get('height')

    if not is_valid(last_block_height):
        raise Exception('Received invalid block height: {}'.format(last_block_height))

    cache.set(cache_key, last_block_height, LAST_BLOCK_CACHE_TTL)
    return last_block_height
