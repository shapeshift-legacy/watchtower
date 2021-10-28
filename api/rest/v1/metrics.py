import json
import logging

from common.utils.networks import SUPPORTED_NETWORKS
from django.http import JsonResponse
from rest_framework.views import APIView
from tracker.models import ProcessedBlock, ChainHeight

logger = logging.getLogger('watchtower.metrics')

class LatestBlockPage(APIView):

    def get(self, request):

        height = {}
        for network in SUPPORTED_NETWORKS:
            block = ProcessedBlock.latest(network)

            # watchtower returns nothing here if any of the ingestors are still starting up
            if block is None:
                return JsonResponse({
                        'success': False,
                        'error': 'Ingestors are still starting',
                    }, status=400)

            height[network] = block.block_height

        return JsonResponse({
            'success': True,
            'data': height
        })
