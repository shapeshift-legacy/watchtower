import logging
import math
from django.db import connection

from common.services.redis import redisClient, ETH_BLOCK_HEIGHT
from common.utils.networks import ETH

from .queries import (
    UTXO_TRANSACTIONS_SQL,
    ETH_TRANSACTIONS_SQL,
    ERC20_TRANSACTIONS_SQL,
    ERC20_CONTRACT_ADDRESS_SQL,
    ERC20_SYMBOL_SQL,
    ERC20_GROUP_BY_SQL,
    UNION_ALL_SQL,
    COUNT_SQL,
    ORDER_BY_SQL,
    LIMIT_OFFSET_SQL,
    TOKENS_WITH_TX,
    PENDING_TXS,
    TX_BY_TXID_SQL,
)

logger = logging.getLogger('watchtower.rest.views.data.transactions.fetcher')

class TransactionFetcher:
    DEFAULT_PAGE_SIZE = 10

    @staticmethod
    def tx_erc20_history_query_build(xpub, script_type, eth_height, token=None, contract_address=None, dex_trades=False, thor_trades=False):
        params = [eth_height, xpub, script_type, dex_trades, dex_trades, thor_trades, thor_trades]

        sql = ERC20_TRANSACTIONS_SQL
        if isinstance(contract_address, str):
            sql += ERC20_CONTRACT_ADDRESS_SQL
            params.append(contract_address.lower())
        else:
            sql += ERC20_SYMBOL_SQL
            params.append(token)

        sql += ERC20_GROUP_BY_SQL

        return sql, params

    def tx_unconfirmed_query_build(self, network):
        return PENDING_TXS, [network]

    def tx_eth_history_query_build(self, xpub, script_type, eth_height, token=None, contract_address=None, dex_trades=False, thor_trades=False):
        if token or contract_address:
            return self.tx_erc20_history_query_build(xpub, script_type, eth_height, token, contract_address, dex_trades, thor_trades)

        return ETH_TRANSACTIONS_SQL, [eth_height, xpub, script_type, dex_trades, dex_trades, thor_trades, thor_trades]

    def tx_history_query_build(self, xpub, script_type, network, token=None, contract_address=None, dex_trades=False, thor_trades=False):
        if dex_trades == None:
            dex_trades = False
        if thor_trades == None:
            thor_trades = False

        if network == ETH:
            eth_height = int(redisClient.get(ETH_BLOCK_HEIGHT))
            return self.tx_eth_history_query_build(xpub, script_type, eth_height, token, contract_address, dex_trades, thor_trades)

        return UTXO_TRANSACTIONS_SQL, [xpub, script_type, network, thor_trades, thor_trades]

    @staticmethod
    def fetchall(cursor):
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row)) for row in cursor.fetchall()
        ]

    # filter list of xpubs limiting ERC20s to those that have tx history
    def filter_xpubs(self, xpub_list):
        xpubs = []
        # extract eth_xpubs from request
        eth_xpubs = list(filter(lambda x: x.get('network') == ETH, xpub_list))
        eth_xpubs = set(map(lambda x: x.get('xpub'), eth_xpubs))
        # fetch erc20 symbols/addresses for given eth xpubs that have transaction history
        with connection.cursor() as cursor:
            cursor.execute(TOKENS_WITH_TX, [list(eth_xpubs)])
            tokens_with_tx = self.fetchall(cursor)
            tokens_by_symbol = set(map(lambda token: token.get('symbol'), tokens_with_tx))
            tokens_by_contract_address = set(map(lambda token: token.get('contract_address'), tokens_with_tx))

        for xpub in xpub_list:
            if xpub.get('token') is None and xpub.get('contract_address') is None:
                xpubs.append(xpub)
            elif xpub.get('contract_address') is not None and xpub.get('contract_address') in tokens_by_contract_address:
                xpubs.append(xpub)
            elif xpub.get('token') is not None and xpub.get('token') in tokens_by_symbol:
                xpubs.append(xpub)

        return xpubs

    def fetch_unconfirmed_transactions(self, network):
        sql, params = self.tx_unconfirmed_query_build(network)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            results = self.fetchall(cursor)

        # format result data
        data = []
        for t in results:
            data.append({
                'id': t.get('id'),
                'txid': t.get('txid'),
                'block_height': t.get('block_height'),
            })

        return {
            'success': True,
            'data': data
        }

    def fetch_by_txid(self, txid):
        sql, params = TX_BY_TXID_SQL, [txid]

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            results = self.fetchall(cursor)

        return {
            'success': True,
            'tx': results
        }


    def fetch(self, xpub_list, page_number=1, page_size=DEFAULT_PAGE_SIZE):
        queries = []
        all_params = []

        xpubs = self.filter_xpubs(xpub_list)

        # handle case where no xpubs with tx history provided
        if len(xpubs) == 0:
            return {
                'success': True,
                'pagination': {
                    'page': 1,
                    'total_objects': 0,
                    'total_pages': 1
                },
                'data': []
            }

        # Build SQL for each requested xpubs transactions"
        for xpub in xpubs:
            sql, params = self.tx_history_query_build(
                xpub.get('xpub'),
                xpub.get('script_type'),
                xpub.get('network'),
                xpub.get('token'),
                xpub.get('contract_address'),
                xpub.get('dex_trades'),
                xpub.get('thor_trades'))
            queries.append(sql)
            all_params += params

        # UNION the individual xpub queries together
        query = UNION_ALL_SQL.join(queries)

        # create the query to get the total count from full query
        count_query = COUNT_SQL.format(query)

        query += ORDER_BY_SQL
        query += LIMIT_OFFSET_SQL

        with connection.cursor() as cursor:
            # execute the total count query
            cursor.execute(count_query, all_params)
            total = cursor.fetchone()[0]

            # calc pagination data
            total_pages = math.ceil(total / page_size)
            offset = (page_number - 1) * page_size
            all_params.append(page_size)
            all_params.append(offset)

            # execute paginated query for tx list
            cursor.execute(query, all_params)
            results = self.fetchall(cursor)

        # format result data
        data = []
        for t in results:
            # opted to do this here, rather than nest the query another level deep to get it there
            tx_amount = int(t.get('amount'))
            if t.get('success') == False:
                tx_type = 'error'
            elif t.get('is_erc20_fee'):
                tx_type = 'fee'
            elif tx_amount > 0:
                tx_type = 'receive'
            else:
                tx_type = 'send'

            data.append({
                'txid': t.get('txid'),
                'status': t.get('status'),
                'type': tx_type,
                'amount': tx_amount,
                'date': t.get('block_time'),
                'confirmations': t.get('confirmations'),
                'network': t.get('network'),
                'symbol': t.get('network'),
                'xpub': t.get('xpub'),
                'thor_memo': t.get('thor_memo'),
                'fee': t.get('fee'),
            })

        return {
            'success': True,
            'pagination': {
                'page': page_number,
                'total_objects': total,
                'total_pages': total_pages
            },
            'data': data
        }
