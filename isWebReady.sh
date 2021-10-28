#!/bin/bash
# This script is executed by kubernetes readiness probes in order to determine if watchtower web is healthy
# Kubernetes expects a 0 exit code to be healthy

# exit when any command fails
set -e

STATUSCODE=$(curl --silent --output /dev/stderr --write-out "%{http_code}" localhost:8000/api/v1/)
if [ $STATUSCODE -ne 200 ]; then
    echo "/api/v1/ returned status code: $STATUSCODE, expected 200"
    exit 1
fi

LATEST_BLOCKS=$(curl --silent localhost:8000/api/v1/metrics/latest_block | jq -r '.success') 
if [ $LATEST_BLOCKS != 'true' ]; then
    echo "/api/v1/metrics/latest_block returned: $LATEST_BLOCKS, expected .success=true"
    exit 1
fi

exit 0