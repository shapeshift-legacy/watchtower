from .tendermint_block_ingester import TendermintBlockIngester
from common.utils.networks import ATOM, RUNE, SCRT, KAVA, OSMO

atom_block_ingester = TendermintBlockIngester(ATOM)
rune_block_ingester = TendermintBlockIngester(RUNE)
scrt_block_ingester = TendermintBlockIngester(SCRT)
kava_block_ingester = TendermintBlockIngester(KAVA)
osmo_block_ingester = TendermintBlockIngester(OSMO)
