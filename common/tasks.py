from celery import task

from common.utils.ethereum import cache_gas_price, cache_eip1559_fees
from common.utils.bitcoin_node import cache_bitcoin_fees
from common.services import etherscan, ripple, fio, get_gaia_client
from common.services.redis import redisClient, ATOM_BLOCK_HEIGHT, ETH_BLOCK_HEIGHT, XRP_BLOCK_HEIGHT, FIO_BLOCK_HEIGHT, RUNE_BLOCK_HEIGHT, OSMO_BLOCK_HEIGHT

@task()
def update_gas_price_cache():
    return cache_gas_price()

@task()
def update_eth_fees_cache():
    return cache_eip1559_fees()

@task()
def update_bitcoin_fees_cache():
    print("bitcoin_fees_cache")
    return cache_bitcoin_fees()

@task()
def update_eth_block_height():
    latest_block_height = etherscan.get_latest_block_height()
    if isinstance(latest_block_height, int):
        redisClient.set(ETH_BLOCK_HEIGHT, latest_block_height)

@task()
def update_atom_block_height():
    gaia = get_gaia_client('ATOM')
    latest_block_height = gaia.get_latest_block_height()
    if isinstance(latest_block_height, int):
        redisClient.set(ATOM_BLOCK_HEIGHT, latest_block_height)

@task()
def update_rune_block_height():
    gaia = get_gaia_client('RUNE')
    latest_block_height = gaia.get_latest_block_height()
    if isinstance(latest_block_height, int):
        redisClient.set(RUNE_BLOCK_HEIGHT, latest_block_height)

@task()
def update_osmo_block_height():
    gaia = get_gaia_client('OSMO')
    latest_block_height = gaia.get_latest_block_height()
    if isinstance(latest_block_height, int):
        redisClient.set(OSMO_BLOCK_HEIGHT, latest_block_height)


@task()
def update_xrp_block_height():
    latest_block_height = ripple.get_latest_block_height()
    if isinstance(latest_block_height, int):
        redisClient.set(XRP_BLOCK_HEIGHT, latest_block_height)

def update_fio_block_height():
    latest_block_height = fio.get_latest_block_height()
    if isinstance(latest_block_height, int):
        redisClient.set(FIO_BLOCK_HEIGHT, latest_block_height)
