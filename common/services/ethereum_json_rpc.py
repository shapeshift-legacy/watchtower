import requests
import os

# Web3 JSON-RPC Spec:
# https://github.com/ethereum/eth1.0-specs/blob/b4ebe3d6056a2f5edb6f9411da58e042f7a95d2a/json-rpc/spec.json
class EthereumJsonRpc:

    req_body = {
        'id': '1',
        'jsonrpc': '2.0',
        'method': '',
        'params': []
    }

    def __init__(self):
        self.baseurl = os.environ.get('ETH_NODE_URL')
        super().__init__()

    def post(self, data):
        response = requests.post(self.baseurl, json=data)
        response_json = response.json()
        return response_json.get('result', None)

    def get_max_priority_fee_per_gas(self):
        body = self.req_body
        body['method'] = 'eth_maxPriorityFeePerGas'
        body['params'] = []
        return self.post(body)
