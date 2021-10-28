# RIPPLE intergration overview

## start wt

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

init ripple
```
from common.services import ripple
ripple.get_latest_block_height()
```
get block at height
```
ripple.get_block_at_height(59284370)


ripple.get_block_at_height(59284368)
```

Block ingester
```

from ingester.xrp import xrp_block_ingester
xrp_block_ingester.process_block(ripple.get_block_at_height(59284370))

```