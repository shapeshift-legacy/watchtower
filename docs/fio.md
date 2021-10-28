# FIO intergration overview

## start wt

```
docker-compose up -d
```

## Dev repl workflow example
```
docker exec -ti watchtower python manage.py shell
```

## staging repl example
```
kubectl 
```

### enable hot reloading
```
%load_ext autoreload
%autoreload 2
```

#### at this point you can import modules and they will hot reload on changes i.e.

init fio
```
from common.services import fio
fio.get_latest_block_height()
```
get block at height
```
fio.get_block_at_height(29990325)
```

is available
```

fio.is_username_available("highlander@scatter")

False
```
pubkey from username
```
fio.get_pubkey_from_account("highlander@scatter")

FIO6Lxx7BTA8zbgPuqn4QidNNdTCHisXU7RpxJxLwxAka7NV7SoBW
```

actor from pubkey
```
fio.get_actor_from_pubkey("FIO6Lxx7BTA8zbgPuqn4QidNNdTCHisXU7RpxJxLwxAka7NV7SoBW")

zkfounmxdmls
```

pubkey from actor
```
iyz3zveyg23i
fio.get_pubkey_from_actor("iyz3zveyg23i")
```

Block ingester
```
from common.services import fio
from ingester.fio import fio_block_ingester

fio_block_ingester.process_blocks(61165193)

fio_block_ingester.process_block(fio.get_block_at_height(61165193))

```


Block get transactions at height 

```
fio.get_transactions_at_height(29990325)
```

History api get transactions for pubkey

```
fio.get_transactions_by_pubkey("FIO6Lxx7BTA8zbgPuqn4QidNNdTCHisXU7RpxJxLwxAka7NV7SoBW")
```

reponse:

```
{
actions:
    [
        {action1},
        {action2},
        .....
    ]
}
```


actions: An action is the smallest block of logic on the eos/fio network.
A single transaction may have many actions
examples:

Register Username
```
{'global_action_seq': 26787744,
   'account_action_seq': 0,
   'block_num': 25943723,
   'block_time': '2020-08-22T04:35:18.000',
   'action_trace': {'receipt': {'receiver': 'fio.address',
     'response': '{"status": "OK","expiration":"2021-08-22T04:35:18","fee_collected":7105740181}',
     'act_digest': '788ce92f2beb02a02ecd27594d1e8e82999dd9239d42de0d81a4f8ec1ec4edcc',
     'global_sequence': 26787744,
     'recv_sequence': 86625,
     'auth_sequence': [['fntk2uk3xv12', 10165]],
     'code_sequence': 3,
     'abi_sequence': 1},
    'receiver': 'fio.address',
    'act': {'account': 'fio.address',
     'name': 'regaddress',
     'authorization': [{'actor': 'fntk2uk3xv12', 'permission': 'active'}],
     'data': {'fio_address': 'highlander@scatter',
      'owner_fio_public_key': 'FIO6Lxx7BTA8zbgPuqn4QidNNdTCHisXU7RpxJxLwxAka7NV7SoBW',
      'max_fee': 7105740181,
      'actor': 'fntk2uk3xv12',
      'tpid': 'scatter@fiomembers'},
     'hex_data': '12686967686c616e64657240736361747465723546494f364c787837425441387a62675075716e345169644e4e6454434869735855375270784a784c7778416b61374e5637536f425795fd88a70100000020c2ee036a01f35c12736361747465724066696f6d656d62657273'},
    'context_free': False,
    'elapsed': 3296,
    'console': '',
    'trx_id': 'eeab254b5f2dabcc39827a5a53ac434fdaecf48b4cca93b1b592c56f78977d17',
    'block_num': 25943723,
    'block_time': '2020-08-22T04:35:18.000',
    'producer_block_id': '018bdeab88fbf2ba752f5bd2053a2455e431763e7eb601e5d59f386d78834f80',
    'account_ram_deltas': [{'account': 'fio.address', 'delta': 334},
     {'account': 'fntk2uk3xv12', 'delta': 810}],
    'except': None,
    'error_code': None,
    'action_ordinal': 1,
    'creator_action_ordinal': 0,
    'closest_unnotified_ancestor_action_ordinal': 0}}
```



Register (chain)Address
```
 {'global_action_seq': 26787745,
   'account_action_seq': 1,
   'block_num': 25943723,
   'block_time': '2020-08-22T04:35:18.000',
   'action_trace': {'receipt': {'receiver': 'eosio',
     'response': '',
     'act_digest': 'a8c00898d231f6498c606f150ef3b95911f42f28010f88c243a84e023d389499',
     'global_sequence': 26787745,
     'recv_sequence': 26146935,
     'auth_sequence': [['fio.address', 171487]],
     'code_sequence': 4,
     'abi_sequence': 2},
    'receiver': 'eosio',
    'act': {'account': 'eosio',
     'name': 'newaccount',
     'authorization': [{'actor': 'fio.address', 'permission': 'active'}],
     'data': {'creator': 'fio.address',
      'name': 'zkfounmxdmls',
      'owner': {'threshold': 1,
       'keys': [{'key': 'FIO6Lxx7BTA8zbgPuqn4QidNNdTCHisXU7RpxJxLwxAka7NV7SoBW',
         'weight': 1}],
       'accounts': [],
       'waits': []},
      'active': {'threshold': 1,
       'keys': [{'key': 'FIO6Lxx7BTA8zbgPuqn4QidNNdTCHisXU7RpxJxLwxAka7NV7SoBW',
         'weight': 1}],
       'accounts': [],
       'waits': []}},
     'hex_data': '003056372503a85b80a34c5d4e4d17fc01000000010002bfd00b54fa53f27d09723178a227401db210c8522d2e0ed34acf02b4bd9e5a770100000001000000010002bfd00b54fa53f27d09723178a227401db210c8522d2e0ed34acf02b4bd9e5a7701000000'},
    'context_free': False,
    'elapsed': 325,
    'console': '',
    'trx_id': 'eeab254b5f2dabcc39827a5a53ac434fdaecf48b4cca93b1b592c56f78977d17',
    'block_num': 25943723,
    'block_time': '2020-08-22T04:35:18.000',
    'producer_block_id': '018bdeab88fbf2ba752f5bd2053a2455e431763e7eb601e5d59f386d78834f80',
    'account_ram_deltas': [{'account': 'zkfounmxdmls', 'delta': 2996}],
    'except': None,
    'error_code': None,
    'action_ordinal': 2,
    'creator_action_ordinal': 1,
    'closest_unnotified_ancestor_action_ordinal': 1}}
```

Transfer fio

audit tx

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


## History endpoint info

Get transactions by account
This provides action traces, not just transaction history which has several implications:

Multiple actions can be submitted in a single transaction, so several (different) actions can have the same transaction ID
Not all of the actions may be been performed by the account being queried (triggering internal actions within a contract for example.) It may or may not be beneficial to only show the actions directly performed by the account being queried, for example filtering out internal actions that have a different actor may result in missing some important FIO transactions, such as rewards payouts.
Note: there are some peculiarities in how paging works on this endpoint, this is not a FIO specific issue. We haven’t diverged from how EOS works in this case to avoid unexpected behavior for block explorers etc.

The gettactions endpoint does allow a negative position for finding the most recent actions, but if a negative number is specified, the following caveats apply:

it will only start at the most recent transaction, only -1 is valid, cannot specify a lower offset.
it will not allow paging
it will always return 10 records.
Because of this limitation, getting the last 100 transactions for an account (for example) requires a call with the negative offset to find the highest position (using the last action in the returned array,) and then paging through the actions using positive pos and offset values. accountactionseq is the transaction count for the account, and is what should be used for paging.

https://developers.fioprotocol.io/fio-chain/history
