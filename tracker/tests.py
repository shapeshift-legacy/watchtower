from django.test import TestCase
from unittest import mock
import json

from tracker.models import ProcessedBlock
from common.utils.networks import SUPPORTED_NETWORKS


class ProcessedBlockWithNoProcessedBlocksTest(TestCase):
    def test_processed_block_get_or_none(self):
        # Define blocks
        blocks = [
            '0000000000000000001c16ae9e7d8877b481eff4c34e66010f524110112a621c',  # BTC
            '00000000000000000045acb1b96242fa30e2c5e1f7b80c2181d5be89e8fdfd58',  # BCH
            '9105b1f300555eb4331232ca27665bb6e7c5150a3a11a6cd407f7dfed7e17ebd',  # LTC
            '2eced3b12d929e7bf53eef78941d95ab3046183dda7848b4ea56f5d3f75dc643',  # DOGE
            '00000000000000286e11cf2491617c99a77b52ebc755eba241bbad7befdda30f'  # DASH
        ]

        # Call ProcessedBlock.get_or_none
        for block_hash, network in zip(blocks, SUPPORTED_NETWORKS):
            empty_block = ProcessedBlock.get_or_none(block_hash, network)

        # Confirm that reponse = None because of empty database
            self.assertEqual(empty_block, None)

    def test_processed_block_get_or_create(self):
        # Define blocks
        blocks = [
            '0000000000000000001c16ae9e7d8877b481eff4c34e66010f524110112a621c',  # BTC
            '00000000000000000045acb1b96242fa30e2c5e1f7b80c2181d5be89e8fdfd58',  # BCH
            '9105b1f300555eb4331232ca27665bb6e7c5150a3a11a6cd407f7dfed7e17ebd',  # LTC
            '2eced3b12d929e7bf53eef78941d95ab3046183dda7848b4ea56f5d3f75dc643',  # DOGE
            # '00000000000000286e11cf2491617c99a77b52ebc755eba241bbad7befdda30f'  # DASH
        ]

        # Call ProcessedBlock.get_or_none
        for block_hash, network in zip(blocks, SUPPORTED_NETWORKS):
            ProcessedBlock.get_or_create(block_hash, network)

        # Confirm that the ProcessedBlock object is created for the expected block_hash
        for block, block_hash in zip(ProcessedBlock.objects.all(), blocks):
            self.assertEqual(block.block_hash, block_hash)


class ProcessedBlockWithExistingDatabase(TestCase):
    # Define test database fixture
    fixtures = ['test_database.json']

    def test_processed_block_get_or_none(self):
        # Define block_hash
        valid_hashes = [
            '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687',  # BTC
            '000000000000000000ddb9950ce3ddc923181961e9a1cd3f2a4c2233744e0abc',  # BCH
            '387d673b1d282dea77cf84efc16adf701d1fe5f1d4519ea60a7b2fa67576925c',  # LTC
            'e87029d56438262885f5b397fe76e683609e0fd844944fdec9a9979d0939b318',  # DOGE
            '000000000000000b62732e9fd1b901056fcd18e1c75ee6c5302f236776b435fc'  # DASH
        ]

        for valid_hash, network in zip(valid_hashes, SUPPORTED_NETWORKS):
            # Call ProcessedBlock.get_or_none
            existing_block = ProcessedBlock.get_or_none(valid_hash, network)

            # Confirm that the expected block_hash is equal to the existing block in the database
            self.assertEqual(existing_block.block_hash, valid_hash)

    def test_processed_block_get_or_create(self):
        # Define block_hash
        valid_hashes = [
            '0000000000000000001153f0e26631565d174286327a2afd50f6f5103985c687',  # BTC
            '000000000000000000ddb9950ce3ddc923181961e9a1cd3f2a4c2233744e0abc',  # BCH
            '387d673b1d282dea77cf84efc16adf701d1fe5f1d4519ea60a7b2fa67576925c',  # LTC
            'e87029d56438262885f5b397fe76e683609e0fd844944fdec9a9979d0939b318',  # DOGE
            '000000000000000b62732e9fd1b901056fcd18e1c75ee6c5302f236776b435fc'  # DASH
        ]
        for valid_hash, network in zip(valid_hashes, SUPPORTED_NETWORKS):
            # Call ProcessedBlock.get_or_create
            existing_block = ProcessedBlock.get_or_create(valid_hash, network)

            # Confirm that the expected block_hash is returned from the test database
            self.assertEqual(existing_block.block_hash, valid_hash)

    def test_processed_block_latest(self):
        # Define block_hash
        latest_block_hashes = [
            '0000000000000000001567e1f77d087d56e991c5abfdfaeb6fa06059953780c8',  # BTC
            '000000000000000001d998188563195c7232562e3fe7a5ddff7728385b5b3e97',  # BCH
            '5daad59e597741e5ffa734fd514f0fff09e0f6a96211db6b60664e0ab7909f8d',  # LTC
            '68658ff42cf64d14c9bbf90eaf91aaca7fce988ddfbded8c132278e73766c759',  # DOGE
            '000000000000000bfa1da040ad722cae658cc316338fb02d9d8ccf90a7e69da1',  # DASH
            ]
        for latest_block_hash, network in zip(latest_block_hashes, SUPPORTED_NETWORKS):
            # Call ProcessedBlock.latest
            latest = ProcessedBlock.latest(network)

            # Confirm that the expected block_hash is returned from the test database
            self.assertEqual(latest.block_hash, latest_block_hash)

    @mock.patch('common.services.coinquery.CoinQueryClient.get_block_by_hash')
    def test_processed_block_invalidate_orphans_with_valid_block(self, mock_get_block_by_hash):
        network = 'BTC'
        json_data = open(
            'ingester/fixtures/valid_blocks/btc/block_537818.json')
        json_data = json.load(json_data)
        mock_get_block_by_hash.return_value = json_data
        # Call ProcessedBlock.latest_hash
        ProcessedBlock.invalidate_orphans(network)

        # Confirm that mock was called
        self.assertEqual(mock_get_block_by_hash.called, True)

        # Confirm that the valid processed block is not marked orphan
        for block in ProcessedBlock.objects.all():
            self.assertFalse(block.is_orphaned)


class ProcessedBlockWithOrphansTest(TestCase):
    @mock.patch('common.services.coinquery.CoinQueryClient.get_block_by_hash')
    def test_processed_block_invalidate_orphan_chain(self, mock_get_block_by_hash):
        # Define block hashes to mark as orphan
        expected_orphans = {
            '000000000000000000_ORPHAN_BLOCKY_5': True,
            '000000000000000000_ORPHAN_BLOCKY_4': True,
            '000000000000000000_ORPHAN_BLOCKY_3': True,
            '000000000000000000_ORPHAN_BLOCKY_2': False,
            '000000000000000000_ORPHAN_BLOCKY_1': False
        }

        # Mock out Coinquery response for get current block by block hash
        def mocked_get_block_by_hash_responses(block_hash):
            should_be_orphaned = expected_orphans.get(block_hash, None)

            # If block is orphaned cq returns -1 for confirmations
            if should_be_orphaned:
                return {'confirmations': -1}
            return {'confirmations': 1}

        mock_get_block_by_hash.side_effect = mocked_get_block_by_hash_responses

        # Define valid blocks to add to test database
        blocks = [
            {
                'network': 'BTC',
                'block_hash': '000000000000000000_ORPHAN_BLOCKY_1',
                'block_height': 1,
                'block_time': '2018-09-18T21:48:08Z',
                'previous_hash': '000000000000000000_ORPHAN_BLOCKY_0',
                'is_orphaned': False
            },
            {
                'network': 'BTC',
                'block_hash': '000000000000000000_ORPHAN_BLOCKY_2',
                'block_height': 2,
                'block_time': '2018-09-18T21:58:08Z',
                'previous_hash': '000000000000000000_ORPHAN_BLOCKY_1',
                'is_orphaned': False
            },
            {
                'network': 'BTC',
                'block_hash': '000000000000000000_ORPHAN_BLOCKY_3',
                'block_height': 3,
                'block_time': '2018-09-18T22:08:08Z',
                'previous_hash': '000000000000000000_ORPHAN_BLOCKY_2',
                'is_orphaned': False
            },
            {
                'network': 'BTC',
                'block_hash': '000000000000000000_ORPHAN_BLOCKY_4',
                'block_height': 4,
                'block_time': '2018-09-18T22:18:08Z',
                'previous_hash': '000000000000000000_ORPHAN_BLOCKY_3',
                'is_orphaned': False
            },
            {
                'network': 'BTC',
                'block_hash': '000000000000000000_ORPHAN_BLOCKY_5',
                'block_height': 5,
                'block_time': '2018-09-18T22:28:08Z',
                'previous_hash': '000000000000000000_ORPHAN_BLOCKY_4',
                'is_orphaned': False
            },
        ]

        # Create and save ProcessedBlocks for each defined block hash
        for block_dict in blocks:
            processed_block = ProcessedBlock(**block_dict)
            processed_block.save()

        # Populate previous_block field
        for block in ProcessedBlock.objects.all():
            previous_block = ProcessedBlock.objects.filter(
                network=block.network,
                block_hash=block.previous_hash
            ).first()
            block.previous_block = previous_block
            block.save()

        # Call ProcessedBlock.invalidate_orphans on the most recent ProcessedBlock
        ProcessedBlock.invalidate_orphans(ProcessedBlock.objects.last().network)

        # Confirm the expected blocks are marked as orphans
        for block_hash, should_be_orphaned in expected_orphans.items():
            block = ProcessedBlock.objects.get(block_hash=block_hash)
            self.assertEqual(block.is_orphaned, should_be_orphaned)
