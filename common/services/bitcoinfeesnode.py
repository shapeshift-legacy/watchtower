"""
Bicoin Fee Service from node

Query the fees from Shapeshift bitcoin node.

"""

import logging
import os
from common.utils.requests import requests_util, http
from .authproxy import AuthServiceProxy
from django.conf import settings

logger = logging.getLogger('watchtower.common.services.bitcoin_fees_node')

#ESTIMATE_MODE = "ECONOMICAL"
ESTIMATE_MODE = "CONSERVATIVE"

class BitcoinFeesClientNode(object):
    def __init__(self):
        self.url = settings.BTC_NODE_URL
        self.bitcoin_node = AuthServiceProxy(self.url)
        self.mode = ESTIMATE_MODE
        super().__init__()

    def corefees_bin(self, samples, bitcoin, mode, blocktime):
        if samples < 10:
            raise Exception("Need a minimum of 10 samples!")

        try:
            feesamples = []
            numfeesamples = []
            rawsamples = []
            for i in range(samples):
                result = bitcoin.estimatesmartfee(int(blocktime), mode)["feerate"]
                rate = int(result*100000000)
                rawsamples.append(rate)
                if rate in feesamples:
                    numfeesamples[feesamples.index(rate)] += 1
                else:
                    feesamples.append(rate)
                    numfeesamples.append(1)

        except Exception as e:
            print("Couldn't estimate. {}".format(str(e)))
    
        return round(max(feesamples))

    def get_fees_list(self):
        feeschedule = []
        feeschedule.append(self.corefees_bin(10, self.bitcoin_node, self.mode, 1))
        feeschedule.append(self.corefees_bin(10, self.bitcoin_node, self.mode, 3))
        feeschedule.append(self.corefees_bin(10, self.bitcoin_node, self.mode, 6))
        feeschedule.append(self.corefees_bin(10, self.bitcoin_node, self.mode, 36))
        feeschedule.append(self.corefees_bin(10, self.bitcoin_node, self.mode, 144))
        if sorted(feeschedule, reverse=True) != feeschedule:
            feeindx = 0;
            while feeindx < len(feeschedule)-1:
                if feeschedule[feeindx] < feeschedule[feeindx+1]:
                    feeschedule[feeindx] = feeschedule[feeindx+1]
                    feeindx = 0
                else:
                    feeindx += 1

        return feeschedule