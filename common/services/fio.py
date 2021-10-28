'''
    FIO network module

            ______ _____ _____
            |  ___|_   _|  _  |
            | |_    | | | | | |
            |  _|   | | | | | |
            | |    _| |_\ \_/ /
            \_|    \___/ \___/
                                -Highlander

    OpenApi
    APIspec: https://developers.fioprotocol.io/api/api-spec/FIOChainAPI.oas2.json


Sample Tx
  {'global_action_seq': 30239959,
   'account_action_seq': 21,
   'block_num': 29362286,
   'block_time': '2020-09-10T23:25:20.000',
   'action_trace': {'receipt': {'receiver': 'iyz3zveyg23i',
     'response': '',
     'act_digest': '96a741a74b98f5030e57f47f337c1f3056e6705feb0b46fa6ee12e41e7dc78e9',
     'global_sequence': 30239959,
     'recv_sequence': 6,
     'auth_sequence': [['eosio', 29806451]],
     'code_sequence': 1,
     'abi_sequence': 1},
    'receiver': 'iyz3zveyg23i',
    'act': {'account': 'fio.token',
     'name': 'transfer',
     'authorization': [{'actor': 'eosio', 'permission': 'active'}],
     'data': {'from': 'iyz3zveyg23i',
      'to': 'fio.treasury',
      'quantity': '0.453303965 FIO',
      'memo': 'FIO API fees. Thank you.'},
     'hex_data': 'e086605eed3fbe77e0afc646dd0ca85b9dde041b000000000946494f000000001846494f2041504920666565732e205468616e6b20796f752e'},
    'context_free': False,
    'elapsed': 3,
    'console': '',
    'trx_id': 'c546480957d7b1dbfb9f15ef1f63bcda2e7337404c1ef0c2ed0036d6179bba87',
    'block_num': 29362286,
    'block_time': '2020-09-10T23:25:20.000',
    'producer_block_id': '01c0086ed8a35fa18c9d4e3b2bc3234a7a17e60d82795b6e788269436a5bbf02',
    'account_ram_deltas': [],
    'except': None,
    'error_code': None,
    'action_ordinal': 14,
    'creator_action_ordinal': 2,
    'closest_unnotified_ancestor_action_ordinal': 2}}],

'''

import requests
import os
import json
import datetime
import logging
from dateutil import parser

logger = logging.getLogger('watchtower.common.services.fio')

class FioClient:
    API_BASE_URL = os.environ.get('FIO_REMOTE_URL')

    def __init__(self):
        super().__init__()

    def get(self, query_string):
        url = '{base_url}{query_string}'.format(
            base_url=self.API_BASE_URL,
            query_string=query_string
        )

        response = requests.get(url)
        json_data = response.json()
        return json_data

    def post(self, query_string, data):
        url = '{base_url}{query_string}'.format(
            base_url=self.API_BASE_URL,
            query_string=query_string
        )
        response = requests.post(url, json=data)

        json_data = response.json()
        return json_data

    # tx is a raw JSON string
    def broadcast(self, tx):
        response = self.post('/v1/chain/push_transaction', json.loads(tx))
        return response.get('transaction_id')

    def get_balance(self, address):
        data = {
            'fio_public_key': address
        }
        response = self.post('/v1/chain/get_fio_balance',data)
        balance = response.get('balance', 0)
        return balance

    def get_transactions(self, address):
        #Get account for pubkey
        data = {
            "fio_public_key":address
        }
        pubkeyInfo = self.post('/v1/chain/get_actor',data)
        actor = pubkeyInfo.get('actor')

        data = {
            "account_name" : actor,
            "pos": -1
        }
        txs = self.post('/v1/history/get_actions',data)

        return txs

    def get_latest_block_height(self):
        response = self.post('/v1/chain/get_info', {})
        height = response['fork_db_head_block_num']
        return height

    def get_block_at_height(self, height):
        data = {
            "block_num_or_id":height
        }
        response = self.post('/v1/chain/get_block', data)
        return response

    def is_username_available(self, username):
        data = {
            "fio_name":username
        }
        response = self.post('/v1/chain/avail_check', data)
        if response.get('is_registered') == 0:
            return True
        return False

    def get_accounts_from_pubkey(self, pubkey):
        data = {
            "fio_public_key": pubkey
        }
        response = self.post('/v1/chain/get_fio_names', data)
        return response

    def get_pubkey_from_account(self, account):
        data = {
            "fio_address": account,
            "chain_code": "FIO",
            "token_code": "FIO"
        }
        response = self.post('/v1/chain/get_pub_address', data)
        return response.get('public_address')

    def get_pubkey_from_actor(self, actor):

        payload = "{\"account_name\":\""+actor+"\"}"
        headers = {'content-type': 'application/json'}

        response = requests.request("GET", self.API_BASE_URL+"/v1/chain/get_account", data=payload, headers=headers)
        response = json.loads(response.text)
        try:
            retval = response['permissions'][0]['required_auth']['keys'][0]['key']
        except:
            # no pubkey
            retval = None
        return

    def get_actor_from_pubkey(self, pubkey):
        data = {
            "fio_public_key":pubkey
        }
        response = self.post('/v1/chain/get_actor', data)
        return response.get('actor')

    def get_transactions_by_pubkey(self, pubkey):
        actor = self.get_actor_from_pubkey(pubkey)
        data = {
            "account_name":actor,
            "pos": -1
        }
        response = self.post('/v1/history/get_actions', data)
        output = self.format_actions(response['actions'])
        return output

    def format_actions(self, actions):
        # print(txs)
        actions_formatted = []
        for action in actions:
            new_action = self.format_action(action)
            if new_action:
                actions_formatted.append(new_action)
        return actions_formatted

    def format_action(self, action):
        new_action = {
            'txid': action['action_trace']['trx_id'],
            'block_height': action['block_num'],
            'block_hash': '',
            'block_time': self._date_to_standard_format(action['block_time']),
            # 'raw': tx,
            'fee': 0,
            'value': 0
        }
        actionType = action['action_trace']['act']['name']

        if(actionType == 'trnsfiopubky'):
            new_action['type'] = 'transfer'
            new_action['to'] = action.get('action_trace',{}).get('act',{}).get('data',{}).get('payee_public_key',{})
            actor = action['action_trace']['act']['authorization'][0]['actor']
            new_action['from'] = self.get_pubkey_from_actor(actor)
            amount = action['action_trace']['act']['data']['amount']
            new_action['value'] = amount
            return new_action
        else:
            print("tx type not supported: "+actionType)
            return

    def format_tx(self, tx):
        trx = tx.get('trx')
        if isinstance(trx, str):
          logger.info('skipping txid only tx: %s', trx)
          return

        new_tx = {
            'txid': trx.get('id'),
            'block_height': tx['height'],
            'block_hash': tx['block'],
            'block_time': self._date_to_standard_format(tx['time']),
            # 'raw': tx,
            'fee': 0,
            'value': 0
        }
        #for actions
        # if action = transfer
        for action in tx['trx']['transaction']['actions']:
            txType = action['name']
            if txType == 'trnsfiopubky':
                new_tx['type'] = 'transfer'
                new_tx['to'] = action['data']['payee_public_key']
                actor = action['authorization'][0]['actor']
                new_tx['from'] = self.get_pubkey_from_actor(actor)
                new_tx['amount'] = action['data']['amount']
                return new_tx
            else:
                return

    def parse_block_txs(self, block):
        #normalize transactions
        txs = block['transactions']
        # print("txs: ",txs)
        txs_formatted = []
        for tx in txs:
            tx['height'] = block['block_num']
            tx['block'] = block['id']
            tx['time'] = self._date_to_standard_format(block['timestamp'])
            new_tx = self.format_tx(tx)
            if new_tx:
                txs_formatted.append(new_tx)
        return txs_formatted

    def _date_to_standard_format(self,date_string):
        if not date_string:
            return None
        STANDARD_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S%z'
        try:
            return datetime.datetime.strftime(parser.parse(date_string), STANDARD_DATE_FORMAT)
        except Exception as e:
            logger.warn('Unable to convert DATETIME - {}'.format(e))
            return date_string

    def get_transactions_at_height(self, height):
        #get block
        block = self.get_block_at_height(height)
        #normalize transactions
        txs = block['transactions']
        print("txs: ",txs)
        txs_formatted = []
        for tx in txs:
            tx['height'] = height
            tx['block'] = block['id']
            tx['time'] = block['timestamp']
            new_tx = self.format_tx(tx)
            if new_tx:
                txs_formatted.append(new_tx)
        return txs_formatted

    @staticmethod
    def get_fee(tx):
        return 0


