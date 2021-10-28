from django.test import TestCase
from unittest import mock

from .utils.bip32 import is_valid_bip32_xpub, derive_addresses, derive_ethereum_address, derive_segwit_p2sh_p2wpkh_addresses
from .utils.networks import SUPPORTED_NETWORKS, BTC, BCH, BNB, LTC, DASH, DOGE, DGB, ATOM, XRP, EOS, RUNE, SCRT, KAVA, OSMO
from .utils.transactions import create_unsigned_utxo_transaction
from .utils.utils import timestamp_to_unix


class Bip32UtilTest(TestCase):
    def test_is_valid_bip32_xpub_util(self):
        valid_xpubs = [
            ('xpub6BfKpqjTwvH21wJGWEfxLppb8sU7C6FJge2kWb9315oP4ZVqCXG29cdUtkyu7YQhHyfA5nt63nzcNZHYmqXYHDxYo8mm1Xq1dAC7YtodwUR', 'BTC'),  # noqa
            ('xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz', 'BTC'),  # noqa
            (u'xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz', 'BTC'),  # noqa
            ('cosmos15cenya0tr7nm3tz2wn3h3zwkht2rxrq7q7h3dj', 'ATOM'),
            ('bnb1vz5jq54d60dj7zt9p9fc6ykrsqvqjff3jj8u07', 'BNB'),
            ('xpub69MaKuopr1KuXRMuERt28hXsGK225boTGM1FDYU7H8caYwy38fugQhk4dwyFT9dbYc45DwUh7kJn3xU4422uuYWqMqFXUKyoWXjxdcnQ7WK', 'XRP'),
            ('2wsgjqwb2hrp', 'EOS')
        ]
        invalid_xpubs = [
            (None, 'BTC'),
            ('1Mz7153HMuxXTuR2R1t78mGSdzaAtNbBWX', 'BTC'),
            ('17v9bcxrrKF4V2uyRtZR9QHRRcMFvG7pdq', 'BTC'),
            ('invalid_address', 'BTC'),
            (u'asdf', 'BTC'),
            ('', 'BTC'),
            (1234, 'BTC'),
            ('xpub', 'BTC'),
            (b'invalid_type', 'BTC'),
            ('cosmos15cenya0tr7nm3tz2wn3h3zwkht2rxrq7q7fake', 'ATOM'),
            ('bnb1vz5jq54d60dj7zt9p9fc6ykrsqvqjff3jjfake', 'BNB'),
            ('superlegitxpub', 'XRP'),
            ('superlegitxpub', 'EOS')
        ]

        for valid_xpub, network in valid_xpubs:
            self.assertTrue(is_valid_bip32_xpub(valid_xpub, network), "'%s' should be valid" % (valid_xpub,))

        for invalid_xpub, network in invalid_xpubs:
            self.assertFalse(is_valid_bip32_xpub(invalid_xpub, network), "'%s' should be INVALID" % (invalid_xpub,))

    @mock.patch('common.utils.bip32._derive_addresses_pywallet')
    @mock.patch('common.utils.bip32._derive_addresses_pycoin')
    def test_which_address_derivation_library(self, mock_derive_addresses_pycoin, mock_derive_addresses_pywallet):
        pycoin_networks = [BTC, LTC, DASH, DOGE]
        pywallet_networks = [BCH]
        valid_btc_xpub = 'xpub_valid_mock_response'
        valid_child_path = '0'
        valid_count = 1
        valid_from_index = 0

        # Test derive_addresses to ensure the correct derivation library is used for each asset
        for pycoin_network in pycoin_networks:
            derive_addresses(
                valid_btc_xpub,
                valid_child_path,
                valid_count,
                valid_from_index,
                pycoin_network
            )
            # Confirm that the appropriate address derivation library is used for each asset
            mock_derive_addresses_pycoin.assert_called_with(
                valid_btc_xpub,
                valid_child_path,
                valid_count,
                from_index=valid_from_index,
                network=pycoin_network
            )

        for pywallet_network in pywallet_networks:
            derive_addresses(
                valid_btc_xpub,
                valid_child_path,
                valid_count,
                valid_from_index,
                pywallet_network
            )
            # Confirm that the appropriate address derivation library is used for each asset
            mock_derive_addresses_pywallet.assert_called_with(
                valid_btc_xpub,
                valid_child_path,
                valid_count,
                from_index=valid_from_index,
                network=pywallet_network
            )


    def test_derive_segwit_p2sh_p2wpkh_addresses(self):
        test_payloads = [
            #{
            #    'xpub': 'xpub6CkG15Jdw866GKs84e7ysjxAhBQUJBdLZTVbQERCjwh2z6wZSSdjfmaXaMvf6Vm5sbWemK43d7HJMicz41G3vEHA9Sa5N2J9j9vgwyiHdMj',  # noqa
            #    'network': TESTNET,
            #    'from_index': 0,
            #    'derivation_path': '0',
            #    'expected_addresses': [
            #        '2Mww8dCYPUpKHofjgcXcBCEGmniw9CoaiD2',
            #        '2N55m54k8vr95ggehfUcNkdbUuQvaqG2GxK',
            #        '2N9LKph9TKtv1WLDfaUJp4D8EKwsyASYnGX'
            #    ]
            #},
            {
                'xpub': 'xpub6CkG15Jdw866GKs84e7ysjxAhBQUJBdLZTVbQERCjwh2z6wZSSdjfmaXaMvf6Vm5sbWemK43d7HJMicz41G3vEHA9Sa5N2J9j9vgwyiHdMj',  # noqa
                'network': BTC,
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    '36NvZTcMsMowbt78wPzJaHHWaNiyR73Y4g',
                    '3DXZ1Kp7KPdjUu29zLzW8gcDh4iQz6JV2S',
                    '3Hn7kxDRiSQfJYb7uLgwSG8y7bfoJbBHL4'
                ]
            },
            {
                'xpub': 'xpub6CkG15Jdw866GKs84e7ysjxAhBQUJBdLZTVbQERCjwh2z6wZSSdjfmaXaMvf6Vm5sbWemK43d7HJMicz41G3vEHA9Sa5N2J9j9vgwyiHdMj',  # noqa
                'network': BTC,
                'from_index': 1,
                'derivation_path': '1',
                'expected_addresses': [
                    '3ML5DVDS86MCagt7tnVHKCmdXfSs5ZA8tK',
                    '3JNH93bjyTwqaAoC8G7vfcAZwZX4W1iYdu',
                    '3E3WYqywEi5jjumRMrAjJ9aHghB5H5KHqh',
                    '39rKfSjs5HbVg5g2eSyNiMfPgAPB6NkQGz'
                ]
            }
        ]

        # Derive addresses for each supported asset and confirm they are equal to the expected value
        for data in test_payloads:
            derived_addresses = derive_segwit_p2sh_p2wpkh_addresses(
                data['xpub'],
                data['derivation_path'],
                len(data['expected_addresses']),
                data['from_index'],
                data['network']
            )
            self.assertEqual(data['expected_addresses'], derived_addresses)


    def test_derive_addresses_with_supported_assets(self):
        test_payloads = [
            {
                'xpub': 'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # noqa
                'network': BTC,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    '18HuzJJdwaqszWDYPqyhcbu8Kfqz7yQKYT',
                    '12ZAnvchXSEvhydoHZxBQ8nRZfobP5QJpK',
                    '1FCz11GNbajayiSL7jkmfadNCDBpmbtGYM'
                ]
            },
            {
                'xpub': 'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # noqa
                'network': BTC,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '1',
                'expected_addresses': [
                    '174DQfugnSBTt9t5ougkkSTZeMDzAohC2a',
                    '16MfiKgwzJCqKBBM5eMg6Kkm5eKCCMjYyv',
                    '1PrHBVBAzyM355n4vNkCpZrLNyTzN2RPXz'
                ]
            },
            {
                'xpub': 'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # noqa
                'network': BTC,
                'script_type': 'p2sh-p2wpkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    '3KvSENViwbVnNVAe5oG7Rse1aNPAcv7oN5',
                    '38vz31fgUCCoZNChrtXN7QpVfXrn1XooEC',
                    '34oD2Lw9rt445yk8MV4aDMURtKH3xeeRya'
                ]
            },
            {
                'xpub': 'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # noqa
                'network': BTC,
                'script_type': 'p2sh-p2wpkh',
                'from_index': 0,
                'derivation_path': '1',
                'expected_addresses': [
                    '37Lu8GzuNibBKGf9nC3myeCPMjBcqG5Jxr',
                    '3N4bGvtLwYHWQxp8L1CFPnN23hq9FC5KWZ',
                    '3JFBNtM9UUKsxqxtcFtQgD7kRZvQM7eg3t'
                ]
            },
            {
                'xpub': 'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # noqa
                'network': BTC,
                'script_type': 'p2wpkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'bc1qflaufxz8fsjr4ul4gzpzvknkzf2du6lj5u7kcs',
                    'bc1qzyxec0urrjw6kffqg0vds3r6n0nc3544xjsct7',
                    'bc1qn0274anykdngsen3xezzcfwfucgddynq3j6ynt'
                ]
            },
            {
                'xpub': 'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # noqa
                'network': BTC,
                'script_type': 'p2wpkh',
                'from_index': 0,
                'derivation_path': '1',
                'expected_addresses': [
                    'bc1qgfk9csxzlqtj8unhuu4smhtzqgst5jwmz25mkj',
                    'bc1q8tq58q9wgsphdrqsfzfyf9m7zzjym066pxgmkq',
                    'bc1ql2j2sz4h03vf7p8zg0xdxu74yhzdrrquwq2gpq'
                ]
            },
            {
                'xpub': 'xpub6DUDogLM5zJ4GrLWvJZK5wSj7DoVFvSGhrYHUsoGCBTA7j1rZmDqWkPMe5QCjvPz6RohS8pVDEYgQfgsTFosspqupjdATHWQ3onWenVKP86',  # noqa
                'network': BCH,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    '1685u8nRJoSeypXnmTXfq2qArjm3WRwWaK',
                    '1DvbuU78EEcABvwJ5fzfCNndQYDBJqcxke',
                    '16EyxzXpUDyLBnnMP5cjksGSgGxNVmxqDG'
                ]
            },
            {
                'xpub': 'xpub6DUDogLM5zJ4GrLWvJZK5wSj7DoVFvSGhrYHUsoGCBTA7j1rZmDqWkPMe5QCjvPz6RohS8pVDEYgQfgsTFosspqupjdATHWQ3onWenVKP86',  # noqa
                'network': BCH,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '1',
                'expected_addresses': [
                    '17HjKBeyvEQgxK1EcFB6vh27SEFTmyUbP6',
                    '1AddqmnXezDWzJaHwzmdgtbyeX1Mc1aQAA',
                    '14EEwqvwT5DvwfT5yqbw7hFk94bKs7RPb9'
                ]
            },
            {
                'xpub': 'xpub6CrGVCaQj1tWwrwpnUamn1tAEroA3uC18YW9o1wUJLMdXUJwXAVt18c7i3aJmW66ybrjTNK6A7qimAjepF9fwj8BXVeF3w1sqUQB8zUMF1J',  # noqa
                'network': LTC,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'LSj5ZMQeSHaz5fAeNBTv9kqVXN9YuYkm89',
                    'LPHgACzAHyK8bJc8oqQ3rW4JU8foLEKk3x',
                    'LRTuV99b2YLARzzJqnQFNaELNKmpzXamnp'
                ]
            },
            {
                'xpub': 'xpub6CrGVCaQj1tWwrwpnUamn1tAEroA3uC18YW9o1wUJLMdXUJwXAVt18c7i3aJmW66ybrjTNK6A7qimAjepF9fwj8BXVeF3w1sqUQB8zUMF1J',  # noqa
                'network': LTC,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'LSj5ZMQeSHaz5fAeNBTv9kqVXN9YuYkm89',
                    'LPHgACzAHyK8bJc8oqQ3rW4JU8foLEKk3x',
                    'LRTuV99b2YLARzzJqnQFNaELNKmpzXamnp'
                ]
            },
            {
                # ['all'] * 12 at m/49'/2'/0'
                'xpub': 'xpub6CiC8X1b4eeiriD8eJx5xH9GhxCxw1XQvCwFUTNAru75T9Z9xD8hQsPaCoUoeJMRUhNs3gHZGSotHCYin7kmkMrCSjerDnfzhmc2PG8tXYB',  # noqa
                'network': LTC,
                'script_type': 'p2sh-p2wpkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'MUbHn23ZL733kCUbvQ88ZhVSWMdFQMEoV8',
                    'MSxTNYpZGqmk2FNFZr1p2f7wZ6GJmwf8jL',
                    'MHqboKdC8QYQcYzCCSinx1zTtZwi5Wpq7o'
                ]
            },
            {
                # ['all'] * 12 at m/84'/2'/0'
                'xpub': 'xpub6C3TZMSFkRKCbyLJTJa24JQ1JaxKxaMbpDf24NogUKDoTw9ZzHRDhU7Rnk3fQAREjNeTxESUHEWaxMquw1CpMFDs3JJ8RSC7ZFzGqN2PL53',  # noqa
                'network': LTC,
                'script_type': 'p2wpkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'ltc1qkzyarpkhdecu5rzeuj78pwpr5sfm798afny4n6',
                    'ltc1qwxtmkev2vwj5qg7vwcvwj88z9uf3cea8mparml',
                    'ltc1qhjlp4eg4rludl9kzuwx6p6e5n40etu5gx7tgp8'
                ]
            },
            {
                'xpub': 'xpub6DB2ES6MHh21hCyudFAVi2A3epinboHb3hAcaU9eBgQGo8jy9r5b5JKNtv7dFSg2snVFuzkrkgaHESFmDU57Mf7feC2zowdibA58ANZ1F3p',  # noqa
                'network': DOGE,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'DQTjL9vfXVbMfCGM49KWeYvvvNzRPaoiFp',
                    'DAytULhYbMroCHtPvPzTqVktkpnk9RmXNo',
                    'DJUWuypc7k9M2kWWMK9y3cFi2E2iRk791L'
                ]
            },
            {
                'xpub': 'xpub6DB2ES6MHh21hCyudFAVi2A3epinboHb3hAcaU9eBgQGo8jy9r5b5JKNtv7dFSg2snVFuzkrkgaHESFmDU57Mf7feC2zowdibA58ANZ1F3p',  # noqa
                'network': DOGE,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '1',
                'expected_addresses': [
                    'DPCPWrTEMLXhP8o57jH3i6ZbwAQwNHNFdq',
                    'DJo7oANJo8evZJreeRWyoVJmiPRK41YQpi',
                    'DJic3xV9Sp7HnwGpKJM7R7VP7Xw2PaX8xx'
                ]
            },
            {
                'xpub': 'xpub6DEWzMgzsq2At3bK8m1nthjTdQ9VGTrkDrtpaQJX5JqQeuvXFZL4sUiX6Knwph6NCyWoRAMaRAX1mQ3uVCXc1FPYu4Ar1ZAZkFsTjRZ2A35',  # noqa
                'network': DASH,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'XiZjikCwLtpMuf9J32Hu1XG1MLevKejXod',
                    'XkbZFqLHUppDQvzr29MjyFQ77wbpwh4Xa9',
                    'Xhi62QXbKCxDLnXtBatyyYeww3JRjvAr5x'
                ]
            },
            {
                'xpub': 'xpub6DEWzMgzsq2At3bK8m1nthjTdQ9VGTrkDrtpaQJX5JqQeuvXFZL4sUiX6Knwph6NCyWoRAMaRAX1mQ3uVCXc1FPYu4Ar1ZAZkFsTjRZ2A35',  # noqa
                'network': DASH,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '1',
                'expected_addresses': [
                    'XmmF3XjyrHvK8J91HijGbiwSLFjqwB12z5',
                    'XdxZAxmoXeY2GMtif5BkrXY8nQquDpQiG2',
                    'XtwgwaFS7swi2g33ufeAxCXpPrjqVNPYSx'
                ]
            },
            {
                'xpub': 'xpub6CqTerEbegsjrhHTuRNGVdkqfksFMjrZsmf3Lp5JtbiFSgJgCSeodsjAUvXXksAkvAYHYhMeZcjmDRhixpZwYkuMAWf5fAW5ncPzmkcBrHp',  # noqa
                'network': DGB,
                'script_type': 'p2pkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'DLA4uzW4TC3eKHLwWY39egmKBVhoFnPYa5',
                    'DHVw3DYTStDJoKA4zptA3SiZVWtRujFiQW',
                    'D9kMypsSEoRVtZBtdZwaCfxdGwk7j9cq6C'
                ]
            },
            {
                'xpub': 'xpub6CHZ4pRtkriEMy6d7r6yaQ3jQEVP9Hz14kqNdgWDmKugzLhFtP8ZHYFe1uGihkbVSEKTei5RapVd76Gyf1B4We7nSFfuLgRffbtYM3vR2VS',  # noqa
                'network': DGB,
                'script_type': 'p2sh-p2wpkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'SgbK2hJXBUccpQgj41fR4VMZqVPesPZgzC',
                    'SckT6Snbv1WR2VYEuCh3upSPquHN57N314',
                    'SWq7GiwSS9614vh8A423ptdcgqGzCAAfZp'
                ]
            },
            {
                'xpub': 'xpub6DKDLU1zVekkX3P4QxhnzBHxaPkPCiDLY8HK937HSFu454GR5XEBypFNZFwcRwADBz7SFfC3QcFDnh9CF7UQfThgjwqJJm3BZgfVF5zRmLv',  # noqa
                'network': DGB,
                'script_type': 'p2wpkh',
                'from_index': 0,
                'derivation_path': '0',
                'expected_addresses': [
                    'dgb1qr06r5knyw0c9phk46c3hl3q2mp4ertlxs8mf4k',
                    'dgb1qklascxtrdahse6wnp2gyeem6690r0uprysj96m',
                    'dgb1qcwyv3pvdr6q29wnaupw9gj7zp45wfjzt6rajvc'
                ]
            }
        ]

        # Derive addresses for each supported asset and confirm they are equal to the expected value
        for data in test_payloads:
            derived_addresses = derive_addresses(
                data['xpub'],
                data['derivation_path'],
                len(data['expected_addresses']),
                data['from_index'],
                data['network'],
                data['script_type']
            )
            self.assertEqual(data['expected_addresses'], derived_addresses, data)

    def test_derive_addresses_with_invalid_child_path(self):
        valid_xpubs = [
            'xpub6CTku1vN2G5NzQMCiwhWZytt8Zuoz8RXuRzhUyQqomdY755uUgQwjiU82Syu1w9DVMjmwX3yRPAoZdyrmXpXqaYhz5rB51S8ufBVR94Qxc7',  # BTC
            'xpub6DUDogLM5zJ4GrLWvJZK5wSj7DoVFvSGhrYHUsoGCBTA7j1rZmDqWkPMe5QCjvPz6RohS8pVDEYgQfgsTFosspqupjdATHWQ3onWenVKP86', # BCH
            'xpub6CrGVCaQj1tWwrwpnUamn1tAEroA3uC18YW9o1wUJLMdXUJwXAVt18c7i3aJmW66ybrjTNK6A7qimAjepF9fwj8BXVeF3w1sqUQB8zUMF1J', # LTC
            'xpub6DB2ES6MHh21hCyudFAVi2A3epinboHb3hAcaU9eBgQGo8jy9r5b5JKNtv7dFSg2snVFuzkrkgaHESFmDU57Mf7feC2zowdibA58ANZ1F3p', # DOGE
            'xpub6DEWzMgzsq2At3bK8m1nthjTdQ9VGTrkDrtpaQJX5JqQeuvXFZL4sUiX6Knwph6NCyWoRAMaRAX1mQ3uVCXc1FPYu4Ar1ZAZkFsTjRZ2A35', # DASH
        ]
        valid_count = 1
        valid_from_index = 0

        invalid_child_paths = [0, 1, 'invalid_child_path']

        # Confirm that an exception is raised if a non-string value is passed as the child_path
        for network, valid_xpub in zip(SUPPORTED_NETWORKS, valid_xpubs):
            if network not in (ATOM, BNB, XRP, EOS):
                for invalid_child_path in invalid_child_paths:
                    with self.assertRaises(Exception):  # TODO: Catch specific error
                        derive_addresses(valid_xpub, invalid_child_path, valid_count, valid_from_index, network)

    def test_derive_addresses_with_invalid_xpub(self):
        invalid_xpubs = [
            None,
            '1Mz7153HMuxXTuR2R1t78mGSdzaAtNbBWX',
            '17v9bcxrrKF4V2uyRtZR9QHRRcMFvG7pdq',
            'invalid_address',
            u'asdf',
            '',
            1234,
            b'invalid_type'
        ]

        valid_count = 1
        valid_from_index = 0
        valid_child_path = '0'

        # Confirm that an exception is raised if derivation is run on an invalid xpub
        for network in SUPPORTED_NETWORKS:
            if network not in (ATOM, BNB, XRP, EOS, RUNE, SCRT, KAVA, OSMO):
                for invalid_xpub in invalid_xpubs:
                    with self.assertRaises(Exception):  # TODO: Catch specific error
                        derive_addresses(invalid_xpub, valid_child_path, valid_count, valid_from_index, network)

    def test_derive_ethereum_address(self):
        valid_eth_xpub = 'xpub6BmmseiBVq4zNQp4k26ch3SXUJ1sjpovyL1S5YWioM8brrgvYMJUbfw6aqJQWhFMLF5hoj9ZPrZXF4fowmmiJtiakwm6rbsumBMstja3S1A'  # noqa
        expected_eth_address = '0x076FE2f8aBB803dE699d8dD9858fbf59829d6688'

        self.assertEqual(
            derive_ethereum_address(valid_eth_xpub),
            expected_eth_address
        )


class TimestampToUnixTestCase(TestCase):
    def test_timestamp_to_unix(self):

        tests = [
            ('2019-05-23 10:56:38-06:00', 1558630598),
            ('2019-05-23 10:56:38+00:00', 1558608998),
            ('2019-05-23 10:56:38+12:00', 1558565798),
            ('2019-12-27T19:38:40Z', 1577475520),
            ('2019-abc-invalid', '2019-abc-invalid')
        ]

        for stamp, expected in tests:
            self.assertEqual(timestamp_to_unix(stamp), expected)



class CreateUnsignedTransactionTestCase(TestCase):
    def test_create_unsigned_utxo_transaction_without_errors(self):
        utxos = [
            {
                'txid': 'txid1',
                'vout': 3,
                'address': 'address1',
                'script_type': 'p2pkh',
                'satoshis': 2000000000,
                'amount': 200000000 / (10 ** 8),
                'confirmations': 2,
                'address_n': [2147483692, 2147483648, 2147483648, 1, 0],
                'spend_required': False
            }
        ]

        change_address = 'change_address'
        change_script_type = 'p2pkh'
        change_index = 0
        change_path = '1/0'
        change_address_n = [2147483692, 2147483648, 2147483648, 1, 0]
        desired_conf_time = '1hour'
        op_return_data = None

        for network in [BTC, BCH, LTC, DASH, DOGE]:
            # create_unsigned_utxo_transaction mutates the passed recipients array, adding the change recipient.
            # init inside loop to prevent InsufficientFundsError
            recipients = [
                {'address': 'recipient1', 'script_type': 'p2pkh', 'amount': 100}
            ]
            create_unsigned_utxo_transaction(
                network,
                utxos,
                recipients,
                change_address,
                change_script_type,
                change_index,
                change_path,
                change_address_n,
                desired_conf_time,
                op_return_data
            )


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    if args[0] == 'https://mock-gaia-api.com/txs?tx.height=5&page=1':
        return MockResponse({
            'page_total': 3,
            'txs': [
                {
                    'height': '1'
                },
                {
                    'height': '2'
                }
            ]
        }, 200)
    elif args[0] == 'https://mock-gaia-api.com/txs?tx.height=5&page=2':
        return MockResponse({
            'page_total': 3,
            'txs': [
                {
                    'height': '3'
                },
                {
                    'height': '4'
                }
            ]
        }, 200)
    elif args[0] == 'https://mock-gaia-api.com/txs?tx.height=5&page=3':
        return MockResponse({
            'page_total': 3,
            'txs': [
                {
                    'height': '5'
                }
            ]
        }, 200)
    elif args[0] == 'https://mock-gaia-api.com/txs?transfer.recipient=cosmos195sem3se46&page=1':
        return MockResponse({
            'page_total': 2,
            'txs': [
                {
                    'height': '1'
                }
            ]
        }, 200)
    elif args[0] == 'https://mock-gaia-api.com/txs?transfer.recipient=cosmos195sem3se46&page=2':
        return MockResponse({
            'page_total': 2,
            'txs': [
                {
                    'height': '2'
                }
            ]
        }, 200)
    elif args[0] == 'https://mock-gaia-api.com/txs?message.sender=cosmos195sem3se56&page=1':
        return MockResponse({
            'page_total': 1,
            'txs': [
                {
                    'height': '1'
                }
            ]
        }, 200)

    return MockResponse(None, 404)

# TODO: add tests for TendermintGaiaClient since CosmosGaiaClient is no more
