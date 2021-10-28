"""
Ethereum Fees
"""

import logging
import os
from common.utils.requests import http

logger = logging.getLogger('watchtower.common.services.etherum_fees')

class EthereumFeesClient(object):
    def __init__(self):
        self.baseurl = "https://data-api.defipulse.com/api/v1/egs/api/ethgasAPI.json?api-key="+os.environ.get('ETH_GAS_STATION')
        super().__init__()

    def get_fees_fast(self):
        resp = http.get(self.baseurl)
        if resp.status != 200 or 'fast' not in resp.json_data:
            return None
        else:
            # eth gas station returns fees in units of 10wei.  multiply by 1x10^8 to get gwei
            return (resp.json_data.get('fast') * 100000000)
