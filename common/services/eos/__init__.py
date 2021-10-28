import base64
import datetime
import time
import json
import hashlib
import logging
import requests
import subprocess
import os
from decimal import Decimal

import grpc
from .graphql import graphql_pb2_grpc
from .graphql.graphql_pb2 import Request

from ...utils.networks import EOS, NETWORK_CONFIGS
from common.services.redis import redisClient as redis_client, EOS_BLOCK_QUEUE, EOS_BLOCK_QUEUE_HEIGHT


logger = logging.getLogger('watchtower.common.services.eos')


class EOSClient(object):

    DFUSE_API_KEY = os.environ.get('DFUSE_API_KEY')
    DFUSE_GRPC = os.environ.get('DFUSE_GRPC')
    DFUSE_AUTH = os.environ.get('DFUSE_AUTH')
    DFUSE_REST = os.environ.get('DFUSE_REST')
    # fail fast
    assert(DFUSE_API_KEY and DFUSE_GRPC and DFUSE_AUTH and DFUSE_REST)

    @staticmethod
    def _decimal_to_int(value):
        # left shift the decimal place according to precision (varies per coin)
        # i.e. 2.6970  -> 26970
        if not value:
            return 0
        return int(Decimal(value) * Decimal(10**NETWORK_CONFIGS[EOS]['precision']))

    def __init__(self):
        super().__init__()

    def get_token(self):
        # use cached token if valid
        try:
            if int(time.time()) - self._token.get('expires_at', 0) < 0:
                # tokens expire after 24 hours
                # a negative value means seconds still remain and token is still valid
                return self._token.get('token')
        except:
            pass

        # otherwise get a new token
        response = requests.post(
            self.DFUSE_AUTH + '/v1/auth/issue', json={'api_key': self.DFUSE_API_KEY}
        )
        try:
            self._token = response.json()
            return self._token.get('token')
        except:
            self._token = None  # purge cache
            return response.text

    def get_stub(self):
        # use cached stub if valid - i.e. token may have expired
        try:
            if self._stub and int(time.time()) - self._token.get('expires_at', 0) < 0:
                # tokens expire after 24 hours
                # a negative value means seconds still remain and token is still valid
                return self._stub
        except:
            pass

        credentials = grpc.access_token_call_credentials(self.get_token())
        channel = grpc.secure_channel(
            self.DFUSE_GRPC,
            credentials=grpc.composite_channel_credentials(
                grpc.ssl_channel_credentials(), credentials
            )
        )
        self._stub = graphql_pb2_grpc.GraphQLStub(channel)
        return self._stub

    def _graphql_grpc_unary_unary(self, query):
        response = self.get_stub().unary_unary(Request(query=query))
        if response.errors:
            return response.errors
        return json.loads(response.data)

    def _graphql_grpc_unary_stream(self, subscription):
        return self.get_stub().unary_stream(Request(query=subscription))

    def _filter_tx_actions(self, tx):
        '''
        multiple actions are possible in any one tx
        our schemas effectively expect 1 action per tx

        thus, we filter out any actions that are not the user's transfer
        i.e. whereby there is only one authorizing actor
        '''
        filtered_actions = []
        for action in tx['topLevelActions']:
            if action['name'] == 'transfer' and len(action['authorization']) == 1:
                filtered_actions.append(action)
        tx['topLevelActions'] = filtered_actions
        return tx

    def _format_tx(self, tx):
        tx = self._filter_tx_actions(tx)
        try:
            # expects transfers only after filtering
            return {
                'txid': tx['id'],
                'block_height': tx['block']['num'],
                'block_hash': tx['block']['id'],
                'block_time': tx['block']['timestamp'],
                'raw': '',
                'from': tx['topLevelActions'][0]['data']['from'],
                'to': tx['topLevelActions'][0]['data']['to'],
                'memo': tx['topLevelActions'][0]['data']['memo'],
                'type': tx['topLevelActions'][0]['name'],
                'asset': 'u' + tx['topLevelActions'][0]['data']['quantity'].split()[1],
                'value':  self._decimal_to_int(tx['topLevelActions'][0]['data']['quantity'].split()[0]),
                'fee': '',
            }
        except Exception as e:
            txid = tx.get('id')
            logger.warn(f'EOS _format_tx {txid}: {type(e).__name__}: {e}')
        return None

    def _format_txs(self, txs):
        return list(filter(lambda x: x is not None, [self._format_tx(tx['trace']) for tx in txs]))

    def get_accounts_for_key(self, public_key, height=None):
        # fetches the accounts controlled by the given public key
        headers = {'Authorization': 'Bearer {}'.format(self.get_token())}
        params = {
            'public_key': public_key,
            'block_num': height,
        }
        response = requests.get(
            self.DFUSE_REST + '/v0/state/key_accounts', headers=headers, params=params
        )
        try:
            # sample response json:
            # {'block_num': 118977992, 'account_names': ['2wsgjqwb2hrp']}
            return response.json()['account_names']
        except:
            return response.text

    def get_account_balance(self, account, limit=0):
        query = f'''
            query {{
                accountBalances(account:"{account}", limit:{limit}) {{
                    edges {{
                        node {{
                            account
                            contract
                            symbol
                            precision
                            balance
                        }}
                    }}
                }}
            }}
        '''
        response = self._graphql_grpc_unary_unary(query)
        try:
            for edge in response['accountBalances']['edges']:
                if edge['node']['symbol'] == 'EOS':
                    return self._decimal_to_int(edge['node']['balance'].split()[0])
        except Exception as e:
            logger.error(f'EOS get_balance {account}: {type(e).__name__}: {e}')
        return 0

    def get_account_tx(self, account, format=True):
        query = f'''
            query {{
                searchTransactionsBackward(query:"receiver:{account}") {{
                    results {{
                        trace {{
                            id
                            block {{
                                id
                                num
                                timestamp
                            }}
                            topLevelActions {{
                                name
                                seq
                                data
                                authorization {{
                                    actor
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        '''
        response = self._graphql_grpc_unary_unary(query)
        try:
            txs = response['searchTransactionsBackward']['results']
            if format:
                return self._format_txs(txs)
            return txs
        except Exception as e:
            logger.error(f'EOS get_account_tx {account}: {type(e).__name__}: {e}')
            raise(e)
        return []

    def get_block_txs_for_accounts(self, accounts, low_block=-11, high_block=-1, format=True):
        '''
        Return a list of txs for the supplied accounts over a specified block range.
        Method defaults to last 10 blocks.

        https://docs.dfuse.io/reference/eosio/graphql/#query-searchtransactionsbackward
        '''
        if not len(accounts):
            return []

        dfuse_search_query = '(' + ' OR '.join([f'receiver:{account}' for account in accounts]) + ')'

        if len(accounts) == 1:
            # parenthesis will break expression if there is no `OR` operand
            dfuse_search_query =  dfuse_search_query[1:-1]

        query = f'''
            query {{
                searchTransactionsBackward(query:"{dfuse_search_query}", lowBlockNum:{low_block}, highBlockNum:{high_block}) {{
                    results {{
                        trace {{
                            id
                            block {{
                                id
                                num
                                timestamp
                            }}
                            topLevelActions {{
                                name
                                seq
                                data
                                authorization {{
                                    actor
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        '''
        response = self._graphql_grpc_unary_unary(query)
        try:
            txs = response['searchTransactionsBackward']['results']
            if format:
                return self._format_txs(txs)
            return txs
        except Exception as e:
            logger.error(f'EOS search_transactions_backward {query}: {type(e).__name__}: {e}')
            raise(e)
        return []

    def broadcast(self, encoded_tx, signatures, push_guarantee=True):
        # we use dfuse
        # https://docs.dfuse.io/reference/eosio/rest/push-transaction/
        # which is really a wrapper around
        # https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/push_transaction
        headers = {
            'Authorization': 'Bearer {}'.format(self.get_token()),
        }
        if push_guarantee:
            # the call is blocking until the transaction makes it into a valid block
            ## headers['X-Eos-Push-Guarantee'] = 'in-block'
            # the call is blocking until the transaction makes it into a block that is
            # still in the longest chain after block production got handed off to a
            # different BP 1 (handoff:1), 2 or 3 times (with handoffs:2 and handoffs:3)
            headers['X-Eos-Push-Guarantee'] = 'handoffs:2'

        data = {
            'signatures': signatures,
            'compression': 0,  # https://eosio.stackexchange.com/questions/4065/unable-to-send-transaction
            'packed_context_free_data': '',
            'packed_trx': encoded_tx,
        }
        response = requests.post(
            self.DFUSE_REST + '/v1/chain/push_transaction', headers=headers, json=data
        )
        try:
            return response.json()
        except:
            return response.text

    def __get_account_tx_forward(self, account, limit=0):
        # UNUSED CODE
        # WIP - example of how to handle subscription call
        subscription = f'''
            subscription {{
                searchTransactionsForward(query:"account:{account} receiver:{account} action:transfer", limit:{limit}) {{
                    trace {{
                        id
                        matchingActions {{
                            account
                            receiver
                            name
                            json
                        }}
                    }}
                }}
            }}
        '''
        stream = self._graphql_grpc_unary_stream(subscription)
        for result in stream:
            if result.errors:
                print(result.errors)
            else:
                print(json.loads(result.data))
