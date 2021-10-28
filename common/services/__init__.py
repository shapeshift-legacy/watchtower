from common.services.ethereum_json_rpc import EthereumJsonRpc
from django.conf import settings

from .etherscan import EtherscanClient
from .bitcoinfees import BitcoinFeesClient
from .ethereumfees import EthereumFeesClient
from .bitcoinfeesnode import BitcoinFeesClientNode
from .gaia_tendermint import get_client as get_gaia_client
from .binance import BinanceClient
from .ripple import RippleClient
from .eos import EOSClient
from .fio import FioClient
from .cointainerWeb3 import CointainerWeb3Client
from .thorchain import ThorchainClient

etherscan = EtherscanClient(settings.ETHERSCAN_API_KEY)
cointainer_web3 = CointainerWeb3Client(settings.ETH_NODE_URL)
ethereum_json_rpc = EthereumJsonRpc()
ethereumfees = EthereumFeesClient()
bitcoinfees = BitcoinFeesClient()
bitcoinfeesnode = BitcoinFeesClientNode()
binance_client = BinanceClient()
ripple = RippleClient()
eos_client = EOSClient()
fio = FioClient()
thorchain = ThorchainClient(settings.MIDGARD_URL)
