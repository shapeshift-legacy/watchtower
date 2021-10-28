# E2E

### Watchtower e2e test suite

This directory provides a base for us to test asset integrations. 
Each asset (as required by axiom) should provide the following interface.

```
# see axiom/packages/watchtower-service/src/urls.js

`${WATCHTOWER_URL}/register`
`${WATCHTOWER_URL}/unregister`
`${WATCHTOWER_URL}/balance`
`${WATCHTOWER_URL}/balance/multihistory`
`${WATCHTOWER_URL}/sync_account_based_balances`
`${WATCHTOWER_URL}/receive`
`${WATCHTOWER_URL}/xpubs`
`${WATCHTOWER_URL}/transactions`
`${WATCHTOWER_URL}/tools/create_unsigned_transaction`
`${WATCHTOWER_URL}/send`
```

## Run Tests

Uses `docker-compose` to fire up a test container. 
Pinging a locally running watchtower service `localhost:8000`.
Unless overwritten by config.

This can easily be ported into a kubernetes job of which we can leverage after megacluster migration.

#### Default Config

```
WATCHTOWER_URL=localhost:8000/api/v1
```

#### Run Watchtower

NOTE if you only want to test one coin, say `fio`, then update `watchtower/settings/local.py` with something like the below. This will only ingest FIO stuff, and make things a lot less noisy / resource intensive.

```
...
CELERY_BEAT_SCHEDULE = {
    'refresh_chainheights': {
        'task': 'ingester.tasks.refresh_chainheights',
        'schedule': timedelta(seconds=30)
    },
    'sync_blocks_fio': {
        'task': 'ingester.tasks.sync_blocks_fio',
        'schedule': timedelta(seconds=10)
    },
    'update_fio_block_height': {
        'task': 'common.tasks.update_fio_block_height',
        'schedule': timedelta(seconds=10)
    },
}
```

Run `watchtower` in background

```
# in root dir
docker-compose up -d

# tail logs
docker-compose logs -f
```

#### Test

```
# in e2e dir
docker-compose up
```
