import json

from django.test import TestCase
from unittest import mock
from common.services.rabbitmq import RabbitConnection, EXCHANGE_TXS

from ingester.tasks import sync_blocks, sync_block, sync_xpub, initial_sync_xpub
from tracker.models import ProcessedBlock, Account, Address, ERC20Token, BalanceChange, Transaction
from common.utils.networks import SUPPORTED_NETWORKS, ETH, BCH

ROOT_582697 =   '000000000000000000b727132c210aa2ec9ccdcc9f17e8a4dda4cdc7400add71'
ORPHAN_582698 = '0000000000000000013821c4378e842401ac54371a8afa81777327266bf418af'
ORPHAN_582699 = '000000000000000000944485965a7172b18962c953da005afd648fe2f6abe650'
REORG_582698 =  '000000000000000001562c1487f79367fb8d2207e3279ee73452933d449e2bb4'
REORG_582699 =  '000000000000000002afe7b89110ee0207fa39015d3496df1e9eef57224e2f00'
REORG_582700 =  '00000000000000000211f85fbe5789a3a7a9116a8c933c94ba320e76bf893d07'

VALID_BLOCK_FIXTURES = {
    '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687': 'ingester/fixtures/valid_blocks/btc/block_537817.json',  # BTC
    '0000000000000000001567e1f77d087d56e991c5abfdfaeb6fa06059953780c8': 'ingester/fixtures/valid_blocks/btc/block_537818.json',  # BTC
    '0000000000000000000567a7ca994a0a5749344142325d4c6e90e6b8835ed835': 'ingester/fixtures/valid_blocks/btc/block_537819.json',  # BTC
    '000000000000000000ddb9950ce3ddc923181961e9a1cd3f2a4c2233744e0abc': 'ingester/fixtures/valid_blocks/bch/block_548425.json',  # BCH
    '000000000000000001d998188563195c7232562e3fe7a5ddff7728385b5b3e97': 'ingester/fixtures/valid_blocks/bch/block_548426.json',  # BCH
    '0000000000000000019c1e122c0fcbf985d93c9ae49a74c8178f66fab2b459cd': 'ingester/fixtures/valid_blocks/bch/block_548427.json',  # BCH
    '387d673b1d282dea77cf84efc16adf701d1fe5f1d4519ea60a7b2fa67576925c': 'ingester/fixtures/valid_blocks/ltc/block_1494276.json',  # LTC
    '5daad59e597741e5ffa734fd514f0fff09e0f6a96211db6b60664e0ab7909f8d': 'ingester/fixtures/valid_blocks/ltc/block_1494277.json',  # LTC
    '64d345d347125ad72f8b251c831de76ec56a509b8e948e2f6756c15fac7b9f4e': 'ingester/fixtures/valid_blocks/ltc/block_1494278.json',  # LTC
    'e87029d56438262885f5b397fe76e683609e0fd844944fdec9a9979d0939b318': 'ingester/fixtures/valid_blocks/doge/block_2395204.json',  # DOGE
    '68658ff42cf64d14c9bbf90eaf91aaca7fce988ddfbded8c132278e73766c759': 'ingester/fixtures/valid_blocks/doge/block_2395205.json',  # DOGE
    'c0c29ac4e925592e19cfbe56d1113baa8dbb112b9df4f75fe80ebeeacef89d1f': 'ingester/fixtures/valid_blocks/doge/block_2395206.json',  # DOGE
    '000000000000000b62732e9fd1b901056fcd18e1c75ee6c5302f236776b435fc': 'ingester/fixtures/valid_blocks/dash/block_939556.json',  # DASH
    '000000000000000bfa1da040ad722cae658cc316338fb02d9d8ccf90a7e69da1': 'ingester/fixtures/valid_blocks/dash/block_939557.json',  # DASH
    '000000000000001d3c595fc14ed2604a579f7121b39713a00cd6858aae8a29f3': 'ingester/fixtures/valid_blocks/dash/block_939558.json',  # DASH
    ROOT_582697: 'ingester/fixtures/valid_blocks/bch/block_582697.json',
    ORPHAN_582698: 'ingester/fixtures/valid_blocks/bch/orphaned_582698.json',
    ORPHAN_582699: 'ingester/fixtures/valid_blocks/bch/orphaned_582699.json',
    REORG_582698: 'ingester/fixtures/valid_blocks/bch/block_582698.json',
    REORG_582699: 'ingester/fixtures/valid_blocks/bch/block_582699.json',
    REORG_582700: 'ingester/fixtures/valid_blocks/bch/block_582700.json',
}

VALID_TX_FIXTURES = {
    '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687': 'ingester/fixtures/valid_txs/btc/txs_537817.json',  # BTC
    '0000000000000000001567e1f77d087d56e991c5abfdfaeb6fa06059953780c8': 'ingester/fixtures/valid_txs/btc/txs_537818.json',  # BTC
    '0000000000000000000567a7ca994a0a5749344142325d4c6e90e6b8835ed835': 'ingester/fixtures/valid_txs/btc/txs_537819.json',  # BTC
    '000000000000000000ddb9950ce3ddc923181961e9a1cd3f2a4c2233744e0abc': 'ingester/fixtures/valid_txs/bch/txs_548425.json',  # BCH
    '000000000000000001d998188563195c7232562e3fe7a5ddff7728385b5b3e97': 'ingester/fixtures/valid_txs/bch/txs_548426.json',  # BCH
    '0000000000000000019c1e122c0fcbf985d93c9ae49a74c8178f66fab2b459cd': 'ingester/fixtures/valid_txs/bch/txs_548427.json',  # BCH
    '387d673b1d282dea77cf84efc16adf701d1fe5f1d4519ea60a7b2fa67576925c': 'ingester/fixtures/valid_txs/ltc/txs_1494276.json',  # LTC
    '5daad59e597741e5ffa734fd514f0fff09e0f6a96211db6b60664e0ab7909f8d': 'ingester/fixtures/valid_txs/ltc/txs_1494277.json',  # LTC
    '64d345d347125ad72f8b251c831de76ec56a509b8e948e2f6756c15fac7b9f4e': 'ingester/fixtures/valid_txs/ltc/txs_1494278.json',  # LTC
    'e87029d56438262885f5b397fe76e683609e0fd844944fdec9a9979d0939b318': 'ingester/fixtures/valid_txs/doge/txs_2395204.json',  # DOGE
    '68658ff42cf64d14c9bbf90eaf91aaca7fce988ddfbded8c132278e73766c759': 'ingester/fixtures/valid_txs/doge/txs_2395205.json',  # DOGE
    'c0c29ac4e925592e19cfbe56d1113baa8dbb112b9df4f75fe80ebeeacef89d1f': 'ingester/fixtures/valid_txs/doge/txs_2395206.json',  # DOGE
    '000000000000000b62732e9fd1b901056fcd18e1c75ee6c5302f236776b435fc': 'ingester/fixtures/valid_txs/dash/txs_939556.json',  # DASH
    '000000000000000bfa1da040ad722cae658cc316338fb02d9d8ccf90a7e69da1': 'ingester/fixtures/valid_txs/dash/txs_939557.json',  # DASH
    '000000000000001d3c595fc14ed2604a579f7121b39713a00cd6858aae8a29f3': 'ingester/fixtures/valid_txs/dash/txs_939558.json',  # DASH
    ROOT_582697: 'ingester/fixtures/valid_txs/bch/txs_empty.json',
    ORPHAN_582698: 'ingester/fixtures/valid_txs/bch/txs_empty.json',
    ORPHAN_582699: 'ingester/fixtures/valid_txs/bch/txs_empty.json',
    REORG_582698: 'ingester/fixtures/valid_txs/bch/txs_empty.json',
    REORG_582699: 'ingester/fixtures/valid_txs/bch/txs_empty.json',
    REORG_582700: 'ingester/fixtures/valid_txs/bch/txs_empty.json',
}

VALID_ETH_FIXTURES = {
    '0x076FE2f8aBB803dE699d8dD9858fbf59829d6688': 'ingester/fixtures/valid_txs/eth/tokens/txs_0x076fe2f8abb803de699d8dd9858fbf59829d6688.json'
}


# Define mock responses for coinquery get_block_by_hash API calls:
def mocked_blocks_by_hash(block_hash):
    with open(VALID_BLOCK_FIXTURES[block_hash]) as block_file:
        block = json.load(block_file)
        return block


# Define mock responses for coinquery get_next_block_hash API calls:
def mocked_txs_by_hash(block_hash):
    with open(VALID_TX_FIXTURES[block_hash]) as tx_file:
        transactions = json.load(tx_file)
        return transactions['txs']


# Define mock responses for etherscan API calls:
def mocked_eth_token_txs_by_address(address, **kwargs):
    with open(VALID_ETH_FIXTURES[address]) as tx_file:
        transactions = json.load(tx_file)
        return transactions


class SyncBlocksWithNoProcessedBlocksTest(TestCase):
    def test_fixtures_sanity_check(self):
        # Confirm database does not contain any processed blocks
        self.assertEqual(ProcessedBlock.objects.count(), 0)

    @mock.patch('common.services.coinquery.CoinQueryClient.get_block_by_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_transactions_by_block_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_next_block_hash')
    def test_sync_blocks_from_empty_db(self, mock_get_next_block_hash, mock_get_transactions_by_block_hash, mock_get_block_by_hash):
        starting_hashes = [
            '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687',  # BTC
            '000000000000000000ddb9950ce3ddc923181961e9a1cd3f2a4c2233744e0abc',  # BCH
            '387d673b1d282dea77cf84efc16adf701d1fe5f1d4519ea60a7b2fa67576925c',  # LTC
            'e87029d56438262885f5b397fe76e683609e0fd844944fdec9a9979d0939b318',  # DOGE
            '000000000000000b62732e9fd1b901056fcd18e1c75ee6c5302f236776b435fc'  # DASH
        ]

        # Mock out each coinquery api call to return expected data
        mock_get_next_block_hash.side_effect = [
            '0000000000000000001567e1f77d087d56e991c5abfdfaeb6fa06059953780c8',  # BTC
            '0000000000000000000567a7ca994a0a5749344142325d4c6e90e6b8835ed835',
            None,
            '000000000000000001d998188563195c7232562e3fe7a5ddff7728385b5b3e97',  # BCH
            '0000000000000000019c1e122c0fcbf985d93c9ae49a74c8178f66fab2b459cd',
            None,
            '5daad59e597741e5ffa734fd514f0fff09e0f6a96211db6b60664e0ab7909f8d',  # LTC
            '64d345d347125ad72f8b251c831de76ec56a509b8e948e2f6756c15fac7b9f4e',
            None,
            '68658ff42cf64d14c9bbf90eaf91aaca7fce988ddfbded8c132278e73766c759',  # DOGE
            'c0c29ac4e925592e19cfbe56d1113baa8dbb112b9df4f75fe80ebeeacef89d1f',
            None,
            '000000000000000bfa1da040ad722cae658cc316338fb02d9d8ccf90a7e69da1',  # DASH
            '000000000000001d3c595fc14ed2604a579f7121b39713a00cd6858aae8a29f3',
            None
        ]

        # Call mocked_txs_by_hash to retrieve mocked api json data
        mock_get_transactions_by_block_hash.side_effect = mocked_txs_by_hash
        mock_get_block_by_hash.side_effect = mocked_blocks_by_hash

        for network, starting_hash in zip(SUPPORTED_NETWORKS, starting_hashes):
            # Call the sync_blocks function to populate db with mocked cq data
            sync_blocks(network, starting_hash)

            # Confirm the mocks were called
            self.assertEqual(mock_get_next_block_hash.called, True)
            self.assertEqual(mock_get_transactions_by_block_hash.called, True)
            self.assertEqual(mock_get_block_by_hash.called, True)

        # Confirm the processed block hashes are equal to the expected fixtures
        for key, block in zip(VALID_TX_FIXTURES.keys(), ProcessedBlock.objects.all()):
            self.assertEqual(block.block_hash, key)

    @mock.patch('common.services.coinquery.CoinQueryClient.get_block_by_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_transactions_by_block_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_next_block_hash')
    def test_sync_blocks_with_no_new_blocks(self, mock_get_next_block_hash, mock_get_transactions_by_block_hash, mock_get_block_by_hash):
        network = 'BTC'
        starting_hash = '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687'

        # Mock out each coinquery api call to return expected data
        mock_get_next_block_hash.return_value = None
        mock_get_transactions_by_block_hash.side_effect = mocked_txs_by_hash
        mock_get_block_by_hash.side_effect = mocked_blocks_by_hash

        # Call the sync_blocks function to populate db with mocked cq data
        sync_blocks(network, starting_hash)

        # Confirm the mocks were called:
        self.assertEqual(mock_get_next_block_hash.called, True)
        self.assertEqual(mock_get_transactions_by_block_hash.called, True)
        self.assertEqual(mock_get_block_by_hash.called, True)

        # Confirm only one block was processed
        self.assertEqual(ProcessedBlock.objects.count(), 1)

        # Confirm processed block hash is equal to defined starting_block_hash
        for block in ProcessedBlock.objects.all():
            self.assertEqual(
                block.block_hash, starting_hash)


class SyncBlockTest(TestCase):
    @mock.patch('common.services.coinquery.CoinQueryClient.get_block_by_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_transactions_by_block_hash')
    def test_sync_block_with_block_hash(self, mock_get_transactions_by_block_hash, mock_get_block_by_hash):
        block_hashes = [
            '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687',  # BTC
            '000000000000000000ddb9950ce3ddc923181961e9a1cd3f2a4c2233744e0abc',  # BCH
            '387d673b1d282dea77cf84efc16adf701d1fe5f1d4519ea60a7b2fa67576925c',  # LTC
            'e87029d56438262885f5b397fe76e683609e0fd844944fdec9a9979d0939b318',  # DOGE
            '000000000000000b62732e9fd1b901056fcd18e1c75ee6c5302f236776b435fc'  # DASH
        ]

        # Mock out each coinquery api call to return expected data
        mock_get_transactions_by_block_hash.side_effect = mocked_txs_by_hash
        mock_get_block_by_hash.side_effect = mocked_blocks_by_hash

        for network, block_hash in zip(SUPPORTED_NETWORKS, block_hashes):
            # Call sync_block function with defined block hash
            sync_block(network, block_hash)

            # Confirm the mock is called
            self.assertEqual(mock_get_transactions_by_block_hash.called, True)
            self.assertEqual(mock_get_block_by_hash.called, True)

        for network in SUPPORTED_NETWORKS:
            # Confirm only one block was processed for each asset
            self.assertEqual(ProcessedBlock.objects.count(), 5)

        # Confirm the processed block hashes are equal to the expected fixtures
        for block_hash, block in zip(block_hashes, ProcessedBlock.objects.all()):
            self.assertEqual(block_hash, block.block_hash)


class SyncBlocksReorgTest(TestCase):
    @mock.patch('common.services.coinquery.CoinQueryClient.get_block_by_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_transactions_by_block_hash')
    @mock.patch('common.services.coinquery.CoinQueryClient.get_next_block_hash')
    def test_sync_bch_reorg(self, mock_get_next_block_hash, mock_get_transactions_by_block_hash, mock_get_block_by_hash):
        # Test a real reorg that happened on BCH

        # Common ancestor of the two chains.
        ROOT_582697 =   '000000000000000000b727132c210aa2ec9ccdcc9f17e8a4dda4cdc7400add71'

        # Orphaned chain.
        ORPHAN_582698 = '0000000000000000013821c4378e842401ac54371a8afa81777327266bf418af'
        ORPHAN_582699 = '000000000000000000944485965a7172b18962c953da005afd648fe2f6abe650'

        # Reorg'd new main chain.
        REORG_582698 =  '000000000000000001562c1487f79367fb8d2207e3279ee73452933d449e2bb4'
        REORG_582699 =  '000000000000000002afe7b89110ee0207fa39015d3496df1e9eef57224e2f00'
        REORG_582700 =  '00000000000000000211f85fbe5789a3a7a9116a8c933c94ba320e76bf893d07'

        # Mock out each coinquery api call to return expected data.
        mock_get_next_block_hash.side_effect = [
            ROOT_582697,
            ORPHAN_582698,
            ORPHAN_582699,
            None,
            REORG_582698,
            REORG_582699,
            REORG_582700,
            None
        ]

        # Pretend that the first three of these blocks are all valid.
        def mocked_valid_blocks(block_hash):
            with open(VALID_BLOCK_FIXTURES[block_hash]) as block_file:
                block = json.load(block_file)
                block['confirmations'] = 1
                return block

        # Call mocked_txs_by_hash to retrieve mocked api json data.
        mock_get_transactions_by_block_hash.side_effect = mocked_txs_by_hash
        mock_get_block_by_hash.side_effect = mocked_valid_blocks

        # Sync first from the root, walking down the to-be-orphaned chain.
        sync_blocks(BCH, ROOT_582697)

        # Confirm that only the first three blocks got added.
        self.assertEqual(len(ProcessedBlock.objects.all()), 3)

        # Confirm that none of them are marked orphaned yet.
        for block in ProcessedBlock.objects.all():
            self.assertFalse(block.is_orphaned)

        # Now, when asked about orphaned blocks, report that they're actually orphaned.
        def mocked_orphaned_blocks(block_hash):
            with open(VALID_BLOCK_FIXTURES[block_hash]) as block_file:
                block = json.load(block_file)
                if block_hash == ORPHAN_582698 or block_hash == ORPHAN_582699:
                    block['confirmations'] = -1
                else:
                    block['confirmations'] = 1
                return block

        mock_get_block_by_hash.side_effect = mocked_orphaned_blocks

        # Then sync again from where we left off, completing the reorg.
        sync_blocks(BCH, None)

        # Confirm the mocks were called.
        self.assertEqual(mock_get_next_block_hash.called, True)
        self.assertEqual(mock_get_transactions_by_block_hash.called, True)

        expected_orphanness = {
            ROOT_582697: False,
            ORPHAN_582698: True,
            ORPHAN_582699: True,
            REORG_582698: False,
            REORG_582699: False,
            REORG_582700: False
        }

        # Confrim that all the blocks ended up in the DB.
        self.assertEqual(len(ProcessedBlock.objects.all()), 6)

        # Confirm that the blocks we expected to get orphaned end up getting marked as such.
        for block in ProcessedBlock.objects.all():
            self.assertEqual(block.is_orphaned, expected_orphanness[block.block_hash])


class SyncXpubTest(TestCase):
    def test_xpub_sync_status(self):
        network = "BTC"
        script_type = "p2pkh"
        xpub = "xpub6Chd4kunDV37PJANQzakXojBEUvjfvWk9ZoPuKdc5bDUwFbnA1dd9aScszzcNqzTEMXN9Qor5v9opipuNQf1EVxjdZPs5A5YwuyxFGe4AGu"
        true_publish = True
        hard_refresh = False

        # successful sync
        account_object, created = Account.objects.get_or_create(xpub=xpub, network=network, script_type=script_type)
        self.assertEqual(account_object.sync_status, 'NOT_STARTED')
        initial_sync_xpub(xpub, network, script_type, hard_refresh, true_publish)
        account_object = Account.objects.get(xpub=xpub, network=network, script_type=script_type)
        self.assertEqual(account_object.sync_status, 'COMPLETE')

        # test should throw an exception and the sync_status should be failed
        try:
            false_publish = False
            invalid_xpub = 'xpubinvalid'
            Account.objects.get_or_create(xpub=invalid_xpub, network=network, script_type=script_type)
            initial_sync_xpub(invalid_xpub, network, script_type, hard_refresh, false_publish)
        except Exception as e:
            account_object = Account.objects.get(xpub=invalid_xpub, network=network, script_type=script_type)
            self.assertEqual(account_object.sync_status, 'FAILED')


class RabbitTestCase(TestCase):
    def test_publish_consume(self):
        rabbitChannel = RabbitConnection().get_channel()
        rabbitChannel.queue_declare(queue='test')
        rabbitChannel.queue_bind(exchange=EXCHANGE_TXS, queue='test')

        msgs = [
            {"txid": "3195ce3b15a7b4e1503d7f01a92b73f73b2262b0fb8a353640451a7c0c7f1fca"},
            {"txid": "906565c208d412ce131553488f3b6d3dfe6e6dba7dd71a6d759033ade5851aa5"}
        ]

        for msg in msgs:
            RabbitConnection().publish(exchange=EXCHANGE_TXS, routing_key='', message_type='event.platform.transaction', body=json.dumps(msg))

        want = ["3195ce3b15a7b4e1503d7f01a92b73f73b2262b0fb8a353640451a7c0c7f1fca",
                "906565c208d412ce131553488f3b6d3dfe6e6dba7dd71a6d759033ade5851aa5"]
        got = []

        for method_frame, properties, body in rabbitChannel.consume("test"):
            # Acknowledge the message
            rabbitChannel.basic_ack(method_frame.delivery_tag)

            got.append(json.loads(body).get("txid"))

            if method_frame.delivery_tag == 2:
                break

        # Cancel the consumer and return any pending messages
        rabbitChannel.cancel()

        self.assertListEqual(want, got)

    def test_publish_consume_sync_xpub(self):
        network = "BTC"
        script_type = "p2pkh"
        xpubs = ["xpub6Chd4kunDV37PJANQzakXojBEUvjfvWk9ZoPuKdc5bDUwFbnA1dd9aScszzcNqzTEMXN9Qor5v9opipuNQf1EVxjdZPs5A5YwuyxFGe4AGu",
                 "xpub6DPzKSWrxZCShS45Zd2eEZvc49FYa4XkH93kR9p9LkBH2qFAKHz3QZaiF7e2CreNdqaMuE8QFU6ALaCJsBpGDL7HgyrTpfLan4XXmLf3RA5"]

        for xpub in xpubs:
            Account.objects.get_or_create(xpub=xpub, network=network, script_type=script_type)
            sync_xpub(xpub, network, script_type, True)

        rabbitChannel = RabbitConnection().get_channel()
        rabbitChannel.queue_declare(queue="test")
        rabbitChannel.queue_bind(exchange=EXCHANGE_TXS, queue="test")

        want = ["3195ce3b15a7b4e1503d7f01a92b73f73b2262b0fb8a353640451a7c0c7f1fca",
                "906565c208d412ce131553488f3b6d3dfe6e6dba7dd71a6d759033ade5851aa5",
                "d1f025c590381d2059b19f7b91dfdda4644920767a6b921f53aa82867de4ec74",
                "1cdd4c6a03c7cdb568278bb4635a7d7cf6a57cb16e6dedcb287dafafc482e7d8",
                "afa8f9c2e324c3f67c81c5a6d0f46792e140adaf04ab1666481d37c1a54393e9"]
        got = []

        for method_frame, properties, body in rabbitChannel.consume("test"):
            # Acknowledge the message
            rabbitChannel.basic_ack(method_frame.delivery_tag)

            got.append(json.loads(body).get("txid"))

            if method_frame.delivery_tag == 5:
                break

        # Cancel the consumer and return any pending messages
        rabbitChannel.cancel()

        self.assertListEqual(want, got)
