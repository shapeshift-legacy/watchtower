# KAVA intergration overview

```
docker-compose up -d
```

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


init kava
```
from common.services import get_gaia_client
gaia = get_gaia_client('KAVA')
gaia.get_latest_block_height()
```

get current height
```
gaia.get_latest_block_height()
```
(compare this to block explorers)



get block at height
```
gaia.get_block_at_height(9382)
```

get txs by address
```
gaia.get_transactions_by_sender("kava1lqk43hvysuzymrgg08q45234z6jzth325pg8sk")
gaia.get_transactions_by_recipient("kava1lqk43hvysuzymrgg08q45234z6jzth325pg8sk")
```
