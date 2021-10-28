PRODUCTION = 'production'

BTC = 'BTC'
BCH = 'BCH'
LTC = 'LTC'
DOGE = 'DOGE'
DASH = 'DASH'
ETH = 'ETH'
DGB = 'DGB'
ATOM = 'ATOM'
BNB = 'BNB'
EOS = 'EOS'
XRP = 'XRP'
FIO = 'FIO'
RUNE = 'RUNE'
# TERRA = 'TERRA'
KAVA = 'KAVA'
SCRT = 'SCRT'
OSMO = 'OSMO'

NETWORK_CONFIGS = {
    BTC: {
        'slip44': 2147483648,
        'precision': 8,
        'symbol': 'BTC',
        'display_name': 'Bitcoin',
        'script_types': [
            'p2pkh',
            'p2sh-p2wpkh',
            'p2wpkh'
        ],
        'script_type_default': 'p2sh-p2wpkh',
        'p2pkh_prefix': 0,
        'p2sh_prefix': 5
    },
    BCH: {
        'slip44': 2147483793,
        'precision': 8,
        'symbol': 'BCH',
        'display_name': 'Bitcoin Cash',
        'script_types': [
            'p2pkh'
        ],
        'script_type_default': 'p2pkh',
        'p2pkh_prefix': 0,
        'p2sh_prefix': 5
    },
    LTC: {
        'slip44': 2147483650,
        'precision': 8,
        'symbol': 'LTC',
        'display_name': 'Litecoin',
        'script_types': [
            'p2sh-p2wpkh',
            'p2wpkh',
            'p2pkh'
        ],
        'script_type_default': 'p2pkh',
        'p2pkh_prefix': 48,
        'p2sh_prefix': 50,
    },
    DOGE: {
        'slip44': 2147483651,
        'precision': 8,
        'symbol': 'DOGE',
        'display_name': 'Dogecoin',
        'script_types': [
            'p2pkh'
        ],
        'script_type_default': 'p2pkh',
        'p2pkh_prefix': 30,
        'p2sh_prefix': 22,
    },
    DASH: {
        'slip44': 2147483653,
        'precision': 8,
        'symbol': 'DASH',
        'display_name': 'Dash',
        'script_types': [
            'p2pkh'
        ],
        'script_type_default': 'p2pkh',
        'p2pkh_prefix': 76,
        'p2sh_prefix': 16,
    },
    DGB: {
        'slip44': 2147483668,
        'precision': 8,
        'symbol': 'DGB',
        'display_name': 'Digibyte',
        'script_types': [
            'p2pkh',
            'p2sh-p2wpkh',
            'p2wpkh'
        ],
        'script_type_default': 'p2pkh',
        'p2pkh_prefix': 30,
        'p2sh_prefix': 32,
    },
    ETH: {
        'slip44': 2147483708,
        'precision': 18,
        'symbol': 'ETH',
        'display_name': 'Ethereum',
        'script_types': [
            'eth' #TODO  this is a lie, stop telling lies
        ],
        'script_type_default': 'eth'
    },
    ATOM: {
        'slip44': 0x80000000 + 118,
        'precision': 6,
        'symbol': 'ATOM',
        'display_name': 'Cosmos',
        'script_types': [
            'cosmos' #TODO  this is a lie, stop telling lies
        ],
        'script_type_default': 'cosmos'
    },
    BNB: {
        'slip44': 0x80000000 + 714,
        'precision': 8,
        'symbol': 'BNB',
        'display_name': 'Binance',
        'script_types': [
            'binance' #TODO  this is a lie, stop telling lies
        ],
        'script_type_default': 'binance'
    },
    EOS: {
        'slip44': 0x80000000 + 194,
        'precision': 4,
        'symbol': 'EOS',
        'display_name': 'EOS',
        'script_types': [
            'eos' #TODO  this is a lie, stop telling lies
        ],
        'script_type_default': 'eos'
    },
    FIO: {
        'slip44': 0x80000000 + 235,
        'precision': 9,
        'symbol': 'FIO',
        'display_name': 'fio',
        'script_types': [
            'fio' #TODO  this is a lie, stop telling lies
        ],
        'script_type_default': 'fio'
    },
    RUNE: {
        'slip44': 0x80000000 + 931,
        'precision': 8,
        'symbol': 'RUNE',
        'display_name': 'Thorchain',
        'script_types': [
            'thorchain', #TODO  this is a lie, stop telling lies
            'bech32'
        ],
        'script_type_default': 'thorchain'
    },
    XRP: {
        'slip44': 0x80000000 + 144,
        'precision': 6,
        'symbol': 'XRP',
        'display_name': 'Ripple',
        'script_types': [
            'ripple'
        ],
        'script_type_default': 'ripple'
    },
    # TERRA: {
    #     'slip44': 0x80000000 + 330,
    #     'precision': 6,
    #     'symbol': 'LUNA',  # TODO Terra is the network name, LUNA is just a token on the network
    #     'display_name': 'Luna',
    #     'script_types': [
    #         'terra',
    #         'bech32'
    #     ],
    #     'script_type_default': 'terra'
    # },
    SCRT: {
        'slip44': 0x80000000 + 529,
        'precision': 6,
        'symbol': 'SCRT',
        'display_name': 'Secret',
        'script_types': [
            'secret',
            'bech32'
        ],
        'script_type_default': 'secret'
    },
    KAVA: {
        'slip44': 0x80000000 + 459,
        'precision': 6,
        'symbol': 'KAVA',
        'display_name': 'Kava',
        'script_types': [
            'kava',
            'bech32'
        ],
        'script_type_default': 'kava'
    },
    OSMO: {
        'slip44': 0x80000000 + 459,
        'precision': 6,
        'symbol': 'OSMO',
        'display_name': 'Osmo',
        'script_types': [
            'osmo',
            'osmosis',
            'bech32'
        ],
        'script_type_default': 'osmo'
    },
}

SUPPORTED_NETWORKS = list(NETWORK_CONFIGS.keys())
SUPPORTED_NETWORK_CHOICES = [(n, n) for n in SUPPORTED_NETWORKS]
