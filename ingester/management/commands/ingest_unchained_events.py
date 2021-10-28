from django.core.management.base import BaseCommand
from ingester.unchained import unchained_event_ingester

class Command(BaseCommand):
    help = 'Ingest account state tracking data from Unchained'

    def handle(self, *args, **options):
        unchained_event_ingester.process_events()