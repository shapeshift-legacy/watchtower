from web3 import Web3


class InfuraWeb3Client(Web3):
    """
    Docs: https://web3py.readthedocs.io/en/stable/
    """
    def __init__(self, api_key, timeout=60, network='mainnet', version=3):
        api_url = 'https://{network}.infura.io/v{version}/{api_key}'.format(
            network=network,
            version=version,
            api_key=api_key
        )
        request_kwargs = {
            'timeout': 60
        }
        web3_provider = Web3.HTTPProvider(api_url, request_kwargs=request_kwargs)
        super().__init__(web3_provider)
