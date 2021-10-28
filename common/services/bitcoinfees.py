"""
Bicoin Fee Service
https://bitcoinfees.earn.com/api

Recommended Transaction Fees
https://bitcoinfees.earn.com/api/v1/fees/recommended
Example response:
{
    "fastestFee": 62,
    "halfHourFee": 60,
    "hourFee": 12
}

Transaction Fees Summary
https://bitcoinfees.earn.com/api/v1/fees/list
Example response:

{ "fees": [ 
  {"minFee":0,"maxFee":0,"dayCount":545,"memCount":87,
  "minDelay":4,"maxDelay":32,"minMinutes":20,"maxMinutes":420},
...
 ] 
}

Returns a list of Fee objects that contain predictions about fees in the given range from minFee to maxFee in satoshis/byte.
The Fee objects have the following properties (aside from the minFee-maxFee range they refer to):

dayCount: Number of confirmed transactions with this fee in the last 24 hours.
memCount: Number of unconfirmed transactions with this fee.
minDelay: Estimated minimum delay (in blocks) until transaction is confirmed (90% confidence interval).
maxDelay: Estimated maximum delay (in blocks) until transaction is confirmed (90% confidence interval).
minMinutes: Estimated minimum time (in minutes) until transaction is confirmed (90% confidence interval).
maxMinutes: Estimated maximum time (in minutes) until transaction is confirmed (90% confidence interval).

Error codes
Status 503: Service unavailable (please wait while predictions are being generated)
Status 429: Too many requests (API rate limit has been reached) 
"""

import logging
import os
from common.utils.requests import requests_util, http

logger = logging.getLogger('watchtower.common.services.bitcoin_fees')

class BitcoinFeesClient(object):
    def __init__(self):
        self.baseurl = "https://bitcoinfees.earn.com/api/v1/fees"
        super().__init__()

    # earn.com returns fees as satoshis per byte.
    def get_fees_list(self):
        resp = http.get(self.baseurl + '/list')
        if resp.status != 200 or 'fees' not in resp.json_data:
            return None
        else:
            return (resp.json_data.get('fees'))
