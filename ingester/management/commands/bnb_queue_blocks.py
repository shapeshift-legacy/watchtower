from django.core.management.base import BaseCommand, CommandError

from ingester.bnb import bnb_block_ingester


class Command(BaseCommand):
    help = 'Stream BNB blocks and queue in redis via node websocket'

    def handle(self, *args, **options):
        bnb_block_ingester.queue_blocks_ws()
