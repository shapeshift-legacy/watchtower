# THORCHAIN intergration overview

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


init thorchain
```
from common.services import get_gaia_client
gaia = get_gaia_client('RUNE')
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
gaia.get_transactions_by_sender("tthor1x00pfwyx8xld45sdlmyn29vjf7ev0mv380z4y6")
gaia.get_transactions_by_recipient("tthor1x00pfwyx8xld45sdlmyn29vjf7ev0mv380z4y6")
```

## Block schema

```
{
   "header":{
      "version":{
         "block":"11"
      },
      "chain_id":"thorchain",
      "height":"56616",
      "time":"2021-03-16T17:08:08.006546036Z",
      "last_block_id":{
         "hash":"F2B89D138F7C4D95ACB2E642B2B9DBCDE0D9EACC21212972D89640CF24C9FD83",
         "parts":{
            "total":1,
            "hash":"70C7B2090FB5355B7E4CE7FC952239314169728BB5B4D627CE4ADBCA0A61F142"
         }
      },
      "last_commit_hash":"7C9479CA0B48A726B45EE57E6089A6F7AC5FE3AAACDF2D12C36FDB3B94516F52",
      "data_hash":"E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
      "validators_hash":"9F8996B5FC5F698269BA669A60805F1405B36E82B8A4C90DECD1DD8570D56D3A",
      "next_validators_hash":"9F8996B5FC5F698269BA669A60805F1405B36E82B8A4C90DECD1DD8570D56D3A",
      "consensus_hash":"048091BC7DDC283F77BFBF91D73C44DA58C3DF8A9CBC867405D8B7F3DAADA22F",
      "app_hash":"6A42E509DEE8B9351ADB3A85D74FBE9061B1A721BD118AD9975E4017DAC5B359",
      "last_results_hash":"E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
      "evidence_hash":"E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
      "proposer_address":"8CB740EF60A417B474870B6415490122D1A02729"
   },
   "data":{
      "txs":[
         
      ]
   },
   "evidence":{
      "evidence":[
         
      ]
   },
   "last_commit":{
      "height":"56615",
      "round":0,
      "block_id":{
         "hash":"F2B89D138F7C4D95ACB2E642B2B9DBCDE0D9EACC21212972D89640CF24C9FD83",
         "parts":{
            "total":1,
            "hash":"70C7B2090FB5355B7E4CE7FC952239314169728BB5B4D627CE4ADBCA0A61F142"
         }
      },
      "signatures":[
         {
            "block_id_flag":2,
            "validator_address":"8CB740EF60A417B474870B6415490122D1A02729",
            "timestamp":"2021-03-16T17:08:08.006546036Z",
            "signature":"OYjHlS2pzcRNPKwYMpRnwEBBkyZAI4iWdkF3MDfadYRk0P0lYlUxsFqsXh35cpc5eSsP6zlrpY3RWIHJZHpDCw=="
         }
      ]
   }
}
```

Note: this block is empty data/tx's.

hash for block explorers: header/last_block_id.hash


#### get transactions at height

```
gaia.get_transactions_at_height(9382)
```

#### get transactions by address

```
gaia.get_transactions_by_sender("tthor1x00pfwyx8xld45sdlmyn29vjf7ev0mv380z4y6")
gaia.get_transactions_by_recipient("tthor1x00pfwyx8xld45sdlmyn29vjf7ev0mv380z4y6")

```