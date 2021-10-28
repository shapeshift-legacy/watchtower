# Watchtower

Watchtower is a microservice and REST API to monitor transactions, balances,
and derived addresses for BIP32 ExtendedPublicKeys (xpubs). This enables
view-only functionality in HD wallets such as KeepKey without needing the
actual device connected (after initizliation with Watchtower) and without
storing any private keys.

### Supported coins
BTC, BCH, LTC, DASH, DOGE, DGB, ETH, ERC-20 tokens

### API

[API.md](API.md)

## Development Environment

### Requirements
Docker and Docker-Compose

### Quick Start

1. Make sure you have `docker` and `docker-compose` installed on your system
2. Make a local copy of the sample config file: `cp config/sample.local.json config/local.json`
3. Create a unique apiKey or else you will be 4XX'd by CoinQuery:
    1. Edit `.env` and change the `ENV` var to `local-{name}`
    11. Make a copy or symlink of `watchtower/settings/local.py` and rename to `local-{name}.py`
    111. Add `watchtower/settings/local-{name}.py` to `.git/info/exclude` or your global .gitignore file
4. Run `docker-compose up --build` to quickly bring up `watchtower`, `postgres`, and `redis` preconfigured and bound to their default ports

### Docker Containers
* **Scheduler** - kicks off tasks using Celery
* **Workers** - includes block ingester
* **Postgres** - transaction and balance history indexed by xpub
* **Redis** - Celery message broker.  Stores addresses to monitor in the mempool (generated receive addresses for currently connected clients)
* **RabbitMQ** - AMQP message broker.  The block ingester service publishes messages to RabbitMQ when it detects a new transaction that affects an xpub in the watchtower DB.

### Test
Manually run watchtower tests:

```
docker-compose up --build

(and in a separate terminal)
docker exec -it watchtower bash
python manage.py test
```

### Utils
Rabbit Logger is a script that connects to the local RabbitMQ server and prints each message published to exchange `<exchange>`.  For watchtower, this is typically `exchange.watchtower.txs` or `exchange.watchtower.blocks`

```
`python3 utils/rabbit-logger.py <exchange>`
```

### Misc dev notes

- `python manage.py migrate` - initialize database tables
- `python manage.py createsuperuser` - create admin user for debugging
- `fab serve` - start local webserver
- `fab celery_scheduler` - start periodic job scheduler
- `fab celery_workers` - start worker daemons to process jobs (optional)
- `docker-compose down -v` - clear persistent postgres data
- developer workflow: hot reloading in iPython

## Dev repl workflow example

```
docker exec -ti watchtower python manage.py shell
```
### enable hot reloading
```
%load_ext autoreload
%autoreload 2
```

#### at this point you can import modules and they will hot reload on changes e.g.
init bnb
```
from common.services import binance_client
binance_client.get_latest_block_height()
```

init fio
```
from common.services import fio
fio.get_latest_block_height()
```
get block at height
```
fio.get_block_at_height(29990325)
```
History api get transactions at height 
```
fio.get_transactions_at_height("iyz3zveyg23i")
```

### RabbitMQ Admin interface

* http://localhost:15672
* default rabbit user/pass

## Design Considerations

The primary goals in designing Watchtower's architecture were the following:

1. Infrastructure costs will scale:
    - independent of the number of users/xpubs/transactions being tracked, and
    - proportional to the number of supported blockchains
2. Easily add support for new assets


## Known Limitations
- Watchtower does not publish *internal* Ethereum transactions to RabbitMQ (i.e. smart contract calls).  Instead WT users should query (poll) the ethereum transaction history endpoint to get a list of internal transactions for an account.

## troubleshooting

if rabbit is refusing connections. And docker-compose failing to startup locally. Increase your CPU