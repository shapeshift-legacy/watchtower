from web3 import Web3


class CointainerWeb3Client(Web3):
    """
    Docs: https://web3py.readthedocs.io/en/stable/
    """
    def __init__(self, node_url):
        assert(node_url), "os.environ.get('ETH_NODE_URL') is {}".format(node_url)
        request_kwargs = {
            'timeout': 60
        }
        web3_provider = Web3.HTTPProvider(node_url, request_kwargs=request_kwargs)
        super().__init__(web3_provider)
