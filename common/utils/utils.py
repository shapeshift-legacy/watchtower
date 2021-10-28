from datetime import datetime
import time
import logging

logger = logging.getLogger('common.utils.utils')


# convert a timestamp of the form '2019-12-19T17:50:20Z' or '2019-05-23 10:56:38-06:00' to unix seconds
# returns unix time if successful or the original timestamp if it was unable to be converted
def timestamp_to_unix(stamp):

    if len(stamp) < 4:
        return stamp

    # python 3.6 can't interpret colons in timezone offsets but 3.7 can
    # so we need to strip the colon from the timezone offset
    if stamp[-3] == ':':
        stripped = stamp[:-3] + stamp[-2:]
    # python interprets Z zone as a local
    elif stamp[-1] == 'Z':
        stripped = stamp[:-1] + '+0000'
    else:
        stripped = stamp

    try:
        if 'T' in stamp:
            return int(datetime.strptime(stripped, '%Y-%m-%dT%H:%M:%S%z').timestamp())
        else:
            return int(datetime.strptime(stripped, '%Y-%m-%d %H:%M:%S%z').timestamp())
    except Exception as e:
        logger.error('unable to parse timestamp: %s, with error: %s', stripped, e)
        return stamp

def current_time_millis():
    return int(round(time.time() * 1000))

def multi_get(dict_obj, *attrs, default=None):
    if dict_obj is None:
        return None
    result = dict_obj
    for attr in attrs:
        if result is None or attr not in result:
            return default
        result = result[attr]
    return result