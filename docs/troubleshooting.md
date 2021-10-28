
# Stuck on block checklist

1. verify coinquery/node are using correct version

2. verify cq/cointainer is height >= public block explorer (check a couple, block explorers suck)

3. is WT is behind cq?

    a. multipule coins behind?
    
        1a. check resources
        1b. check timeout on workers  
        
        
    b. if just x
    
    	1a. is error in datadog?
            - Fix errors
        
        2b. if no errors      
            - Probally "stuck"
    
    
For error:

MultipleObjectsReturned
`failed to sync block: get() returned more than one Transaction -- it returned 2!`

Starting from the block_height that is stuck, remove the block and associated balance changes and transactions. Continue doing this for each sequential block after the stuck block until watchtower starts syncing again. Usually only stuck block_height+1 is required.   

The sequel statements you will need are shown below. Make sure to update with the correct `network` for the coin you are trying to fix and just update the `block_height` in each statement accordingly
    
```
delete from tracker_processedblock where network ='DASH' and block_height >= 1380403;
delete from tracker_balancechange where id in (
	select bc.id FROM tracker_transaction tt
	INNER JOIN tracker_balancechange bc
  		ON bc.transaction_id=tt.id
	inner join tracker_account ta 
  		on ta.id = tt.account_id 
	where block_height = 1380403 and network = 'DASH'
);
delete from tracker_transaction where id in (
	select tt.id from tracker_transaction tt
	join tracker_account ta
		on ta.id = tt.account_id
	where block_height = 1380403 and network = 'DASH'
);
```

## (1b) expand timeouts
edit timeouts in celery

1. bash into container that has access to watchtower redis
2. get url from sops

```
redis-cli -h redis://watchtower.***************
```

3. run commands

```
# check to make sure the worker you want is running
get qo_ingester.tasks.sync_blocks_xrp
ttl qo_ingester.tasks.sync_blocks_xrp
(integer) 586
# set 24hour TTL on this task
EXPIRE qo_ingester.tasks.sync_blocks_xrp 86400
(integer) 1
# check status
ttl qo_ingester.tasks.sync_blocks_xrp
(integer) 86397
```      

expand tasks to long time*

if a worker "hangs" it can cause multiple workers to work at the same time. This will task hog and kill OTHER COINS! extending this task timeout will allow WT to catch up.

MAKE SURE TO REMOVE TIMEOUT AFTER SYNCED!

otherwise the node could stop syncing and get stuck for the assets effected. 

## 4) watchtower stuck on block (erroring)

Notes:  Watchtower will NOT skip any block ever. if there is a tx or new data watchtower doesnt understand it will freeze and stop all scanning untill that issue is fixed.

Common issues:
* Timestamp changes format slightly
* new transaction format releases into wild
* api spec changes on node
* customer tx is new format released x cycles ago we never tested

NOTE: one stuck block on any single chain CAN bring all coins behind as celery is not smart and will task additional workers to stuck asset 

  4a ) Check datadog for error on broken block
        Do you see the error? yolo change.
        
  4b ) Need more context?
        Spin up local WT (see doc)
   
#### 5 debugging blocked scan
5a) analyse stuck block   
    Acquire block height stuck from datadog.
    
use docker exec to view single block

get block at height
```
fio.get_block_at_height(29990325)
```

5b) Attempt block digestion locally


note: watchtower will always start from the current block.

To debug a stuck block from production you must grab the block entry from the db.

start watchtower

docker-compose stop workers

truncate the block db

insert row

sample block
```
111006842   61165191    03a54e87f14ad6483856863d3af63879f88010691011cc97132029bfd4989d2d    2021-03-14 08:59:58.5+00    2021-03-14 02:00:02.383225+00   03a54e86fd4c3ef02af7eb0ddc5eab14f1b93bdecb7a17ea44643aec87a0420b    111006841   FALSE   FIO
```
leave 


watch sync get stuck at same place

(possibly there is an error on a transaction)
this will require looking up the pubkey in the block erroring. And registering that pubkey into your local WT

Block ingester

```

from ingester.fio import fio_block_ingester
fio_block_ingester.process_block(fio.get_block_at_height(29990325))

```

fix block ingester
try again