import asyncio
import json
import time
import websockets

from common.services import binance_client


WSS_URI = 'wss://node-binance-063.cointainers.stage.redacted.example.com/websocket'


async def ping_pong(rpc_json=None):
    '''
    Get a single response over socket
    '''
    if rpc_json is None:
        rpc_json = '{"jsonrpc":"2.0","method":"status"}'
    async with websockets.connect(WSS_URI, ssl=True) as websocket:
        await websocket.send(rpc_json)
        pong = await websocket.recv()
        print(f'{pong}')
        return pong

def _transform_block(_this, _next):
    try:
        this_block = _this.get('result', {}).get('data', {}).get('value', {}).get('block', {})
        next_block = _next.get('result', {}).get('data', {}).get('value', {}).get('block', {})
        return {}
            # this_block['hash'] does not exist
            'hash': next_block['header']['last_block_id']['hash'],
            'height': this_block['header']['height'],
            'num_txs': this_block['header']['num_txs'],
            'previous_hash': this_block['header']['last_block_id']['hash'],
            'time': this_block['header']['time'],
            'txs': this_block['data']['txs'],
        }
    except Exception as e:
        return None

def _handle_message(msg, last_msg):
    block = _transform_block(json.loads(last_msg), json.loads(msg))
    block_queue_length = binance_client.queue_block(block)
    print('block_queue_length:', block_queue_length)


async def _get_stream(rpc_json):
    async with websockets.connect(WSS_URI, ssl=True) as websocket:
        batch = []
        prev_msg = None
        await websocket.send(rpc_json)
        async for msg in websocket:
            # `prev_msg` required to determine `msg` block hash
            if prev_msg is None:
                prev_msg = msg
                continue
            # perform ETL
            handled = _handle_msg(msg, prev_msg)
            # update pointers
            prev_msg = msg

def queue_blocks():
    asyncio.run(_get_stream(
        '{"jsonrpc":"2.0","method":"subscribe","id":0,"params":{"query":"tm.event=\'NewBlock\'"}}'
    ))

def run():
    # start = time.time()
    queue_blocks()
    # finish = time.time()
    # print(finish - start)
