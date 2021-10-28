# BNB intergration overview

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

init bnb
```

from common.services import binance_client
binance.get_height()


binance_client.get_block()
binance_client.get_block_txs(binance_client.get_block(113970319))
```
get block at height
```

get_block_txs

binance_client.get_txs_for_height(113970319)
```

