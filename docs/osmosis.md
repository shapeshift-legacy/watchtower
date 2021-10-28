# OSMO intergration overview

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


init osmo
```
from common.services import get_gaia_client
gaia = get_gaia_client('OSMO')
gaia.get_native_asset('OSMO')
```

get current height
```
gaia.get_latest_block_height()
```
(compare this to block explorers)



get block at height
```
gaia.get_block_at_height(1562112)
gaia.get_block_hash_at_height(1562112)
```

get txs by address
```
gaia.get_transactions_by_sender("osmo1k0kzs2ygjsext3hx7mf00dfrfh8hl3e85s23kn")
gaia.get_transactions_by_recipient(osmo1k0kzs2ygjsext3hx7mf00dfrfh8hl3e85s23kn"")
```

#### get transactions at height

```
gaia.get_transactions_at_height(9382)
```



## ingester

```
from common.services import get_gaia_client
```

get block
```

```

get txs at height

```
gaia.get_transactions_at_height(1562112)
```

example response
```
[{'height': '1562109',
  'txhash': '58B7739E225EC29D262752EA624E6CF4AB359E7CAD8D60ACC7C59774446A161E',
  'data': '0A160A14737761705F65786163745F616D6F756E745F696E',
  'raw_log': '[{"events":[{"type":"message","attributes":[{"key":"action","value":"swap_exact_amount_in"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"sender","value":"osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu"},{"key":"module","value":"gamm"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"}]},{"type":"token_swapped","attributes":[{"key":"module","value":"gamm"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"pool_id","value":"6"},{"key":"tokens_in","value":"19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2"},{"key":"tokens_out","value":"20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"amount","value":"19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2"},{"key":"recipient","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"sender","value":"osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu"},{"key":"amount","value":"20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84"}]}]}]',
  'logs': [{'events': [{'type': 'message',
      'attributes': [{'key': 'action', 'value': 'swap_exact_amount_in'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'sender',
        'value': 'osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu'},
       {'key': 'module', 'value': 'gamm'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'}]},
     {'type': 'token_swapped',
      'attributes': [{'key': 'module', 'value': 'gamm'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'pool_id', 'value': '6'},
       {'key': 'tokens_in',
        'value': '19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2'},
       {'key': 'tokens_out',
        'value': '20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84'}]},
     {'type': 'transfer',
      'attributes': [{'key': 'recipient',
        'value': 'osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'amount',
        'value': '19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2'},
       {'key': 'recipient',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'sender',
        'value': 'osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu'},
       {'key': 'amount',
        'value': '20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84'}]}]}],
  'gas_wanted': '1000000',
  'gas_used': '253674',
  'tx': {'type': 'cosmos-sdk/StdTx',
   'value': {'msg': [{'type': 'osmosis/gamm/swap-exact-amount-in',
      'value': {'sender': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5',
       'routes': [{'poolId': '6',
         'tokenOutDenom': 'ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84'}],
       'tokenIn': {'denom': 'ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2',
        'amount': '19027900'},
       'tokenOutMinAmount': '1'}}],
    'fee': {'amount': [], 'gas': '1000000'},
    'signatures': [],
    'memo': '',
    'timeout_height': '0'}},
  'timestamp': '2021-10-13T03:58:52Z'}]
```

test format
```
gaia.format_tx_osmo({'height': '1562109',
  'txhash': '58B7739E225EC29D262752EA624E6CF4AB359E7CAD8D60ACC7C59774446A161E',
  'data': '0A160A14737761705F65786163745F616D6F756E745F696E',
  'raw_log': '[{"events":[{"type":"message","attributes":[{"key":"action","value":"swap_exact_amount_in"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"sender","value":"osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu"},{"key":"module","value":"gamm"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"}]},{"type":"token_swapped","attributes":[{"key":"module","value":"gamm"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"pool_id","value":"6"},{"key":"tokens_in","value":"19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2"},{"key":"tokens_out","value":"20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu"},{"key":"sender","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"amount","value":"19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2"},{"key":"recipient","value":"osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5"},{"key":"sender","value":"osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu"},{"key":"amount","value":"20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84"}]}]}]',
  'logs': [{'events': [{'type': 'message',
      'attributes': [{'key': 'action', 'value': 'swap_exact_amount_in'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'sender',
        'value': 'osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu'},
       {'key': 'module', 'value': 'gamm'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'}]},
     {'type': 'token_swapped',
      'attributes': [{'key': 'module', 'value': 'gamm'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'pool_id', 'value': '6'},
       {'key': 'tokens_in',
        'value': '19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2'},
       {'key': 'tokens_out',
        'value': '20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84'}]},
     {'type': 'transfer',
      'attributes': [{'key': 'recipient',
        'value': 'osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu'},
       {'key': 'sender',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'amount',
        'value': '19027900ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2'},
       {'key': 'recipient',
        'value': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5'},
       {'key': 'sender',
        'value': 'osmo1p0rpttlp8v2hy7m82l2t9p6545788f2ac3yksgrlycke2wr4mu0qdr7ytu'},
       {'key': 'amount',
        'value': '20126103649ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84'}]}]}],
  'gas_wanted': '1000000',
  'gas_used': '253674',
  'tx': {'type': 'cosmos-sdk/StdTx',
   'value': {'msg': [{'type': 'osmosis/gamm/swap-exact-amount-in',
      'value': {'sender': 'osmo1ayg7fz0qzq93htp2qg4jt5nzr4mv67jglmx2l5',
       'routes': [{'poolId': '6',
         'tokenOutDenom': 'ibc/9712DBB13B9631EDFA9BF61B55F1B2D290B2ADB67E3A4EB3A875F3B6081B3B84'}],
       'tokenIn': {'denom': 'ibc/27394FB092D2ECCD56123C74F36E4C1F926001CEADA9CA97EA622B25F41E5EB2',
        'amount': '19027900'},
       'tokenOutMinAmount': '1'}}],
    'fee': {'amount': [], 'gas': '1000000'},
    'signatures': [],
    'memo': '',
    'timeout_height': '0'}},
  'timestamp': '2021-10-13T03:58:52Z'})
```


# Monitors

```

from tracker.models import ProcessedBlock, ChainHeight

block = ProcessedBlock.latest('OSMO')

```


update_osmo_block_height

```

```

test block ingest
```
from ingester.tendermint import atom_block_ingester, rune_block_ingester, scrt_block_ingester, kava_block_ingester, osmo_block_ingester
osmo_block_ingester.poll_blocks()
```



E2E test

register pubkey

