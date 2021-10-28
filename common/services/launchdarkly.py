from django.conf import settings

from common.services.redis import redisClient
import ldclient

KEY_PREFIX = 'watchtower:featureflag:'
TTL = 60 # seconds

# Flag Keys
ACCOUNT_BALANCE_TIMINGS = 'accountbalancetiming'
LOCAL_ACCOUNT_BALANCES = 'localaccountbalances'
ALWAYS_HARD_REFRESH = 'alwayshardrefresh'
UNCHAINED_REGISTRY = 'unchainedregistry'
UNCHAINED_ACCOUNT_BALANCES = 'unchainedaccountbalances'
PUBLISH_CONFIRMED_TXS = 'publishconfirmedtxs'
INCLUDE_EIP1559_FEES = 'includeeip1559fees'

# initialize LD
ldclient.set_sdk_key(settings.LAUNCH_DARKLY_SDK_KEY)
ld_client = ldclient.get()
lduser = {'key': 'watchtower-{}'.format(settings.ENV)}

# redis key
def to_key(feature):
    return KEY_PREFIX + feature

# boolean is enabled function, cache for TTL seconds in redis to reduce LD calls
def is_feature_enabled(feature):
    key = to_key(feature)
    enabled = redisClient.get(key)
    if enabled is None:
        enabled = str(ld_client.variation(feature, lduser, False))
        redisClient.setex(key, TTL, enabled)

    return True if enabled == 'True' else False
