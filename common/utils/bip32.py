from pywallet.utils.bip32 import Wallet
from pywallet.utils.ethereum import HDPublicKey
from bitcash.format import public_key_to_address as bch_public_key_to_address
from bitcash.format import point_to_public_key
from cashaddress import convert as convert_bch
import hashlib
from common.utils.networks import SUPPORTED_NETWORKS, BTC, BCH, LTC, DASH, DOGE, DGB, ATOM, BNB, XRP, EOS, FIO, RUNE, \
    KAVA, SCRT, OSMO
from common.services import eos_client
from web3 import Web3
from pycoin.symbols.btc import network as btc_network
from pycoin.symbols.bch import network as bch_network
from pycoin.symbols.dash import network as dash_network
from pycoin.symbols.doge import network as doge_network
from pycoin.symbols.dgb import network as dgb_network
from pycoin.networks.bitcoinish import create_bitcoinish_network
from pycoin.contrib.segwit_addr import bech32_decode

ADDR_KINDS = [
    'eth',
    'p2pkh',
    'p2sh-p2wpkh',
    'p2wpkh'
]

SUPPORTED_ADDR_KIND_CHOICES = [(n, n) for n in ADDR_KINDS]

GAP_LIMIT = 20

CHANGE = 1


def pycoin_network_for_network(network):
    return {
        BTC: btc_network,
        BCH: bch_network,
        LTC: create_bitcoinish_network(
            network_name="Litecoin",
            symbol="LTC",
            subnet_name="mainnet",
            wif_prefix_hex="b0",
            sec_prefix="LTCSEC:",
            address_prefix_hex="30",
            pay_to_script_prefix_hex="32",
            bip32_prv_prefix_hex="019d9cfe",
            bip32_pub_prefix_hex="019da462",
            bech32_hrp="ltc"),
        DASH: dash_network,
        DOGE: doge_network,
        DGB: dgb_network,
    }[network]


def is_valid_bip32_xpub(xpub, network):
    if not xpub or not isinstance(xpub, str):
        return False

    if network == ATOM:
        (hrp, data) = bech32_decode(xpub)
        return hrp in ['cosmos'] and data is not None
    if network == KAVA:
        (hrp, data) = bech32_decode(xpub)
        return hrp in ['kava'] and data is not None
    if network == SCRT:
        (hrp, data) = bech32_decode(xpub)
        return hrp in ['secret'] and data is not None
    if network == OSMO:
        (hrp, data) = bech32_decode(xpub)
        return hrp in ['osmo'] and data is not None
    if network == RUNE:
        (hrp, data) = bech32_decode(xpub)
        return hrp in ['thor', 'tthor'] and data is not None
    if network == BNB:
        (hrp, data) = bech32_decode(xpub)
        return hrp == 'bnb' and data is not None
    if network == XRP:
        if xpub.startswith('r'):
            return True
    if network == FIO:
        return True
    if network == EOS:
        if len(xpub) == 12:
            return True
        elif len(xpub) == 53 and xpub.startswith('EOS'):
            # if we are given an EOS public key, derive the respective accounts
            # note this is definitelty a hack into the current flow that expects a return bool
            try:
                return eos_client.get_accounts_for_key(xpub)
            except:
                # conversion failed, error will bubble up
                pass

    if not xpub.startswith('xpub'):
        return False

    key = btc_network.parse.bip32_pub(xpub)

    if key is None:
        return False

    return key.as_text() == xpub


def derive_addresses(xpub, child_path, count, from_index=0, network=BTC, script_type='p2pkh'):
    assert network in SUPPORTED_NETWORKS

    if network in (ATOM, BNB, XRP, EOS, RUNE, SCRT, KAVA):
        # With account based chains, we only track addresses, not xpubs,
        # so the thing stored here already is the address.
        return [xpub]

    if script_type == 'p2sh-p2wpkh':
        derive_fn = derive_segwit_p2sh_p2wpkh_addresses
    elif script_type == 'p2wpkh':
        derive_fn = derive_segwit_native_addresses
    elif network in [BCH]:
        derive_fn = _derive_addresses_pywallet
    else:
        derive_fn = _derive_addresses_pycoin

    addresses = derive_fn(xpub, child_path, count, from_index=from_index, network=network)
    return addresses


def derive_ethereum_address(xpub):
    xpub_node = HDPublicKey.from_b58check(xpub)
    child_node = HDPublicKey.from_path(xpub_node, '0/0')[-1]
    return Web3.toChecksumAddress(child_node.address())


def derive_segwit_native_addresses(xpub, child_path, count, from_index=0, network=BTC):
    net = pycoin_network_for_network(network)
    account = btc_network.parse.bip32_pub(xpub)
    node = account.subkey_for_path(child_path)
    children = node.children(
        max_level=(count - 1),
        start_index=from_index,
        include_hardened=False
    )

    net = pycoin_network_for_network(network)

    addrs = []
    for c in children:
        script = net.contract.for_p2pkh_wit(c.hash160(is_compressed=True))
        addr = net.address.for_script(script)
        addrs.append(addr)

    return addrs


def derive_segwit_p2sh_p2wpkh_addresses(xpub, child_path, count, from_index=0, network=BTC):
    net = pycoin_network_for_network(network)
    account = btc_network.parse.bip32_pub(xpub)
    node = account.subkey_for_path(child_path)
    children = node.children(
        max_level=(count - 1),
        start_index=from_index,
        include_hardened=False
    )

    addrs = []
    for c in children:
        script = net.contract.for_p2pkh_wit(c.hash160(is_compressed=True))
        script = net.contract.for_p2s(script)
        addr = net.address.for_script(script)
        addrs.append(addr)

    return addrs


def _hash160(data):
    # compute ripemd160 of the sha256 of the provided data
    md = hashlib.new('ripemd160')
    md.update(hashlib.sha256(data).digest())
    return md.digest()


def _derive_addresses_pycoin(xpub, child_path, count, from_index=0, network=BTC):
    net = pycoin_network_for_network(network)
    account = btc_network.parse.bip32_pub(xpub)
    node = account.subkey_for_path(child_path)
    children = node.children(
        max_level=(count - 1),
        start_index=from_index,
        include_hardened=False
    )

    addrs = []
    for c in children:
        script = net.contract.for_p2pkh(c.hash160(is_compressed=True))
        addr = net.address.for_script(script)
        addrs.append(addr)

    return addrs


def _derive_addresses_pywallet(xpub, child_path, count, from_index=0, network=BTC):
    wallet = Wallet.deserialize(xpub, network)
    node = wallet.get_child_for_path('M/' + child_path)

    addresses = []
    for index in range(from_index, from_index + count):
        address = node.get_child(index).to_address()

        if network == BCH:
            pubkey = point_to_public_key(node.get_child(index).public_key)
            address = convert_bch.to_legacy_address(bch_public_key_to_address(pubkey))

        addresses.append(address)

    return addresses
