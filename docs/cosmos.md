# ATOM intergration overview

## Dev repl workflow example
```
docker exec -ti watchtower python manage.py shell
```
### enable hot reloading
```
%load_ext autoreload
%autoreload 2
```

#### at this point you can import modules and they will hot reload on changes i.e.

init atom

```
from common.services import gaia_cosmos
gaia_cosmos.get_latest_block_height()
gaia_cosmos.get_block_at_height(3382389)
gaia_cosmos.get_transactions_at_height(3382381)

```
get block at height


Format tx
```
            'txid': tx.get('txhash'),
            'block_height': tx.get('height'),
            'block_hash': '',
            'block_time': tx.get('timestamp'),
            'raw': tx.get('raw_log'),
            'fee': self.get_fee(tx),
            'value': 0
            'from':address
    `       'to':address
            'value':1000000
```

