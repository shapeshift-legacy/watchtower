import json

from functools import reduce
import itertools
import asyncio
import logging
import time
import requests
import os

from django.http import JsonResponse
from django.db.models import Q
from django.db import connection as db_connection
from django.core.paginator import Paginator

import arrow
from requests.adapters import HTTPAdapter
from rest_framework.views import APIView
from ingester.tasks import initial_sync_xpub
from ingester.eth.balance_sync import sync_eth_account_balances
from ingester.tendermint.balance_sync import sync_account_balances
from ingester.bnb.balance_sync import sync_bnb_account_balances
from ingester.xrp.balance_sync import sync_xrp_account_balances
from ingester.fio.balance_sync import sync_fio_account_balances
from tracker.models import Account, AccountBalance, Transaction, BalanceChange, ERC20Token, Address
from tracker.signals import should_migrate
from common.exceptions import XPubNotRegisteredError
from common.services.coinquery import get_client as get_coinquery_client
from common.services.unchained import get_client as get_unchained_client
from common.services import cointainer_web3 as web3, eos_client
from common.utils.ethereum import get_token_balance as get_eth_token_balance
from common.utils.ethereum import get_balance as get_eth_balance
from common.utils.bip32 import is_valid_bip32_xpub, CHANGE, GAP_LIMIT
from common.utils.networks import SUPPORTED_NETWORKS, ATOM, BNB, ETH, BCH, XRP, EOS, FIO, RUNE, OSMO, NETWORK_CONFIGS
from common.utils.time_series import INTERVALS
from common.utils.transactions import SMALLEST_VALUE_FIRST
from common.utils.transactions import (
    InsufficientFundsError,
    create_unsigned_utxo_transaction,
    get_dust_limit
)
from common.utils.utils import current_time_millis
from common.utils.ethereum import (
    get_cached_gas_price,
    get_cached_eip1559_fees,
    estimate_ethereum_gas_limit,
    estimate_token_gas_limit,
    get_token_transfer_data,
    get_transaction_count as get_ethereum_transaction_count,
    format_address as format_ethereum_address
)

from api.rest.v1.data.transactions import fetcher as tx_fetcher

from common.services.redis import redisClient, WATCH_ADDRESS_PREFIX, WATCH_ADDRESS_SET_KEY, WATCH_TX_SET_KEY, ETH_ACCOUNT
from common.services.launchdarkly import is_feature_enabled, ACCOUNT_BALANCE_TIMINGS, LOCAL_ACCOUNT_BALANCES, ALWAYS_HARD_REFRESH, UNCHAINED_ACCOUNT_BALANCES, INCLUDE_EIP1559_FEES
from common.utils.ethereum import eth_balance_cache_key_format
from cashaddress import convert as convert_bch

from common.services import binance_client, ripple, fio, get_gaia_client

ETH_BALANCE_TTL = 600
BALANCE_SYNC_TTL = 60 * 60 * 24
DEFAULT_PAGE_SIZE = 10
DEFAULT_TIME_SERIES_LIMIT = 1000

WATCH_ADDRESS_EXPIRATION_SECONDS = 60 * 60

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger('watchtower.rest.views')

def _unpack_and_validate_xpubs(request):
    request_json = json.loads(request.body)
    xpub_payload = request_json.get('data', [])
    xpub_list = [xpub_payload] if isinstance(xpub_payload, dict) else xpub_payload
    xpubs = []

    for xpub_dict in xpub_list:
        xpub = xpub_dict.get('xpub')
        network = xpub_dict.get('network')
        if network:
            network = network.upper()
        _validate_network(network)
        script_type = xpub_dict.get('script_type')
        # EOS Hack:
        # if we are given a pub key and not an account name
        # we must append all respective account names to the xpubs list
        # this way the rest of WT sees this as separate account registrations
        result = _validate_xpub(xpub, network, script_type)
        if result is not None and type(result) == list:  # i.e not a bool
            xpubs += [(acc, network, script_type) for acc in result]
        else:
            xpubs.append((xpub, network, script_type))

    return xpubs


def _validate_xpub(xpub, network, script_type):
    _validate_network(network)
    _validate_script_type(network, script_type)

    # EOS hack - we need the (possible) returned results from validate
    # everything other than EOS this is simply tested for truthiness
    valid_xpub = is_valid_bip32_xpub(xpub, network)
    if not valid_xpub:
        raise ValueError('Invalid xpub: {xpub}'.format(xpub=xpub))
    return valid_xpub

def _validate_network(network):
    if not network or network.upper() not in SUPPORTED_NETWORKS:
        raise ValueError('Invalid network: {network}. Current supported networks are: {supported_networks}'.format(  # noqa
            network=network,
            supported_networks=", ".join(SUPPORTED_NETWORKS)
        ))

def _validate_script_type(network, script_type):
    _validate_network(network)
    config = NETWORK_CONFIGS[network]
    if script_type not in config['script_types']:
        raise ValueError('Unsupported script_type \'{script_type}\' for network: {network}'.format(
            script_type=script_type,
            network=network
        ))

def _fetch_xpubs_from_db(requested_xpubs):
    if not requested_xpubs:
        return []

    # get xpubs from db
    xpub_queries = [Q(xpub=xpub, network=network, script_type=script_type) for xpub, network, script_type in requested_xpubs]
    xpub_aggregate_query = reduce(lambda x, y: x | y, xpub_queries)
    account_objects = Account.objects.filter(xpub_aggregate_query)

    # raise exception if requested xpubs aren't registered
    registered_xpubs = [(obj.xpub, obj.network, obj.script_type) for obj in account_objects]
    for requested_xpub in requested_xpubs:
        if requested_xpub not in registered_xpubs:
            xpub, network, script_type = requested_xpub
            raise ValueError('Account is not registered: {network} {xpub} {script_type}'.format(
                network=network,
                xpub=xpub,
                script_type=script_type
            ))

    return account_objects


def _fetch_xpub_from_db(xpub, network, script_type):
    try:
        return Account.objects.get(xpub=xpub, network=network, script_type=script_type)
    except Account.DoesNotExist:
        raise XPubNotRegisteredError('Account is not registered: {network} {xpub} {script_type}'.format(
            network=network,
            xpub=xpub,
            script_type=script_type
        ))


def _paginate(request, queryset):
    page_number = request.GET.get('page', 1)
    page_size = request.GET.get('pageSize', DEFAULT_PAGE_SIZE)
    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)
    page_objects = page.object_list

    return page_objects, {
        'page': page.number,
        'total_objects': paginator.count,
        'total_pages': paginator.num_pages
    }


# Get balance history for a given xpub
def getBalanceHistoryForXpub(account_object_id, interval, limit, end, start, ordering, address):

    if interval not in INTERVALS:
        return JsonResponse({
            'success': False,
            'error': 'Invalid interval: {interval}. Choices: {choices}.'.format(
                interval=interval,
                choices=', '.join(INTERVALS.keys())
            )
        }, status=400)

    if end:
        end = arrow.get(end)
    else:
        end = arrow.utcnow()

    if start:
        start = arrow.get(start)
    else:
        interval_unit = INTERVALS[interval]['unit']
        interval_unit_amount = INTERVALS[interval]['amount']
        start = end.shift(**{interval_unit: -interval_unit_amount * limit})

    allowed_ordering_values = ['asc', 'desc']
    if ordering not in allowed_ordering_values:
        return JsonResponse({
            'success': False,
            'error': 'Invalid ordering parameter: {ordering}. Choices: {choices}.'.format(
                ordering=ordering,
                choices=', '.join(allowed_ordering_values)
            )
        }, status=400)

    if address is not None:
        address = address.lower()

    token_obj = ERC20Token.objects.filter(contract_address=address).first() if address else None

    if address:
        erc20_token_id = token_obj.id if token_obj else -1
    else:
        erc20_token_id = None

    results = None
    with db_connection.cursor() as cursor:
        sql_format = """
            WITH series AS (
                SELECT generate_series(
                    TO_TIMESTAMP(
                        floor(
                            extract(
                                'epoch' FROM TIMESTAMP WITH TIME ZONE '{start}'
                            ) / {interval_seconds}
                        ) * {interval_seconds}
                    ),
                    TIMESTAMP WITH TIME ZONE '{end}',
                    '{interval}'
                ) AS period_start
            ), balance_change AS (
                SELECT
                    TO_TIMESTAMP(
                        floor(
                            extract(
                                'epoch' FROM {transaction_table}.block_time
                            ) / {interval_seconds}
                        ) * {interval_seconds}
                    ) AS ts,
                    SUM({balance_change_table}.amount) AS amount
                FROM {balance_change_table}
                INNER JOIN {transaction_table}
                ON ({balance_change_table}.transaction_id = {transaction_table}.id)
                WHERE {balance_change_table}.account_id = {account_id}
                AND {transaction_table}.erc20_token_id {erc20_token_id}
                GROUP BY ts
            ), starting_balance AS (
                SELECT COALESCE(SUM(balance_change.amount), 0) AS amount
                FROM balance_change
                WHERE balance_change.ts < (TIMESTAMP WITH TIME ZONE '{start}')
            )
            SELECT
                series.period_start,
                COALESCE(SUM(balance_change.amount) OVER (ORDER BY series.period_start ASC), 0) + (
                    SELECT starting_balance.amount FROM starting_balance
                ) AS balance
            FROM balance_change
            RIGHT JOIN series
            ON series.period_start = balance_change.ts
            ORDER BY series.period_start {ordering}
        """  # noqa

        sql = sql_format.format(
            balance_change_table=BalanceChange._meta.db_table,
            transaction_table=Transaction._meta.db_table,
            erc20_token_table=ERC20Token._meta.db_table,
            account_id=account_object_id,
            erc20_token_id="= '{}'".format(erc20_token_id) if erc20_token_id else 'IS NULL',
            interval_seconds=INTERVALS[interval]['seconds'],
            start=start.format('YYYY-MM-DD HH:mm:ssZZ'),
            end=end.format('YYYY-MM-DD HH:mm:ssZZ'),
            interval='{} {}'.format(INTERVALS[interval]['amount'], INTERVALS[interval]['unit']),
            ordering=ordering.upper()
        )

        cursor.execute(sql)
        results = cursor.fetchall()
        try:
            query_time_ms = int(float(db_connection.queries[1]['time']) * 1000)
        except Exception:
            query_time_ms = None

    formatted_results = [[time, int(balance)] for time, balance in results] if results else None

    results = {
        'success': True,
        'params': {
            'interval': interval,
            'start': start.format(),
            'end': end.format(),
            'limit': limit,
            'ordering': ordering
        },
        'query_execution_time': '{}ms'.format(query_time_ms) if query_time_ms else None,
        'data': formatted_results
    }

    return results

class APIInfoPage(APIView):
    def get(self, request):
        data = {
            'description': 'Welcome to the Watchtower API!',
            'version': request.version,
            'environment': request.META.get('env'),
            'server': request.META.get('SERVER_NAME')
        }
        return JsonResponse(data)


class XpubRegistrationPage(APIView):
    def post(self, request):
        """
        Example Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "network": "BTC",
                    "script_type": "p2pkh"
                },
                ...
            ]
        }

        Query  Params: async=Boolean and hard_refresh=Boolean
        """

        start = time.time()

        request_data = json.loads(request.body)

        # flag indicating whether to always perform registration as a hard refresh
        always_hard_refresh = is_feature_enabled(ALWAYS_HARD_REFRESH)

        data = request_data.get('data', None)
        _async = request.GET.get('async', 'true') == 'true'
        hard_refresh = True if always_hard_refresh else request.GET.get('hard_refresh', 'false') == 'true'

        try:
            xpubs = _unpack_and_validate_xpubs(request)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        # After data is validated, update each xpub
        for xpub, network, script_type in xpubs:
            if _async:
                initial_sync_xpub.s(xpub, network, script_type, hard_refresh, publish=False).apply_async()
            else:
                initial_sync_xpub(xpub, network, script_type, hard_refresh, publish=False)

        end = time.time()

        return JsonResponse({
            'success': True,
            'data': data,
            'duration': end - start
        })


class XpubUnregistrationPage(APIView):
    def post(self, request):
        """
        Example Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "network": "BTC",
                    "script_type": "p2pkh"
                },
                ...
            ]
        }

        Query Params: none
        """
        try:
            xpubs = _unpack_and_validate_xpubs(request)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        xpub_queries = [Q(xpub=xpub, network=network, script_type=script_type) for xpub, network, script_type in xpubs]
        xpub_aggregate_query = reduce(lambda x, y: x | y, xpub_queries)
        records_deleted, _ = Account.objects.filter(xpub_aggregate_query).delete()

        return JsonResponse({
            'success': True,
            'data': {
              'records_deleted': records_deleted
            }
        })


class TransactionListPage(APIView):

    def post(self, request):
        """
        Example Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "network": "BTC",
                    "script_type": "p2pkh",
                    "token": "SALT",  // Optional. If provided, network must be ETH.
                    "contract_address": "0xfeasdf...",  // Optional. Overrides "token".
                    "dex_trades": true, // Optional. gets dex trades only
                },
                ...
            ]
        }
        """
        try:
            request_json = json.loads(request.body)

            xpub_payload = request_json.get('data', [])
            xpub_list = [xpub_payload] if isinstance(xpub_payload, dict) else xpub_payload

            page_number = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('pageSize', DEFAULT_PAGE_SIZE))

            start = int(round(time.time() * 1000))
            response = tx_fetcher.fetch(xpub_list, page_number, page_size)

            duration = int(round(time.time() * 1000)) - start
            logger.debug('fetched transactions for %s xpubs in %sms', len(xpub_list), duration)

            return JsonResponse(response)
        except Exception as e:
            logger.exception('Error getting tx history for %s, error = %s', request_json, e)
            return JsonResponse({
                'success': False,
                'error': 'Error fetching transaction history'
            }, status=500)

class TransactionDetailsPage(APIView):
    def get(self, request):
        """
        Example Request Query:
            /transaction?txid=f45cc0854e37f5a280824157428e88f260f03704d8dbd2d1fd86c669cf2de7f1

        Example Response:
            {
                "success": true,
                "tx": [
                    {
                        "id": 14,
                        "txid": "f45cc0854e37f5a280824157428e88f260f03704d8dbd2d1fd86c669cf2de7f1",
                        "block_height": 632791,
                        "block_hash": "000000000000000000077ee87a5915c31afa88756bcc10b4fdf21987ddf7681c",
                        "raw": "",
                        "status": "confirmed",
                        "is_erc20_fee": false,
                        "erc20_token_id": null,
                        "is_dex_trade": false,
                        "success": true
                    }
                ]
            }
        """
        try:
            txid = request.query_params['txid']
            response = tx_fetcher.fetch_by_txid(txid)
            return JsonResponse(response)
        except Exception as err:
            logger.exception('Error getting transaction details for %s, error = %s', request.query_params, err)
            return JsonResponse({
                'success': False,
                'error': 'Error fetching transaction details'
            }, status=500)


# Balance history page endpoint with support for multiple xpubs
class MultiBalanceHistoryPage(APIView):
    def post(self, request):
        """
        Example Query Parameters:
        {
            "interval": "daily",    // Required: "weekly", "daily", "hourly", "minutely", "30min", "15min", "10min", "5min", or "1min"
            "start": 1537463623,    // Optional: UNIX time in seconds or ISO-8601 date/datetime format. Defaults to (end - (limit * interval)).
            "end": "2018-06-12",    // Optional: UNIX time in seconds or ISO-8601 date/datetime format. Defaults to current time.
            "limit": 1000,          // Optional: Number of data points to return if both "start" and "end" are not provided. Defaults to 1000.
            "ordering": "asc"       // Optional: Time sort ordering. Possible values are "asc" and "desc". Defaults to "asc".
        }

        Example Request Payload:
        {
            "data": [
                {
                "xpub": "xpub6BiVtCpG9fQPxnP...",
                "network": "ETH",
                "token": "SALT"  # optional
                },
                ...
            ]
        }
        """  # noqa

        request_data = json.loads(request.body).get('data', [])

        # Extract xpubs from the http request.  Adds them to a set to exclude duplicate xpubs (different eth tokens with the same xpub)
        requested_xpubs_set = set()
        for data in request_data:
            xpub = data.get('xpub')
            requested_xpubs_set.add(xpub)
        requested_xpubs_list = list(requested_xpubs_set)

        # keep all requested xpubs that have had a transaction
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                select distinct account.xpub
                from tracker_account account
                join tracker_transaction transaction on account.id = transaction.account_id
                where account.xpub = ANY(%s)
                """,
                [requested_xpubs_list])
            xpub_with_tx = tx_fetcher.fetchall(cursor)

        # convert to set for fast lookup
        xpubs_with_tx_set = set()
        for xpub in xpub_with_tx:
            xpubs_with_tx_set.add(xpub['xpub'])

        # Extract token addresses from the http request
        requested_addresses = []
        for data in request_data:
            address = data.get('contract_address')
            if address is not None:
                requested_addresses.append(address.lower())

        # keep all token addresses that have had a transaction from any of the given xpubs
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                select distinct erc20.contract_address
                from tracker_account account
                join tracker_transaction transaction on account.id = transaction.account_id
                join tracker_erc20token erc20 on transaction.erc20_token_id = erc20.id
                where erc20.contract_address = ANY (%s)
                and account.xpub = ANY(%s)
                """,
            [requested_addresses, requested_xpubs_list])
            tokens_with_tx = tx_fetcher.fetchall(cursor)

        # convert to set for fast lookup
        tokens_with_tx_set = set()
        for token in tokens_with_tx:
            tokens_with_tx_set.add(token['contract_address'])

        combinedResults = []

        for data in request_data:
            interval = request.GET.get('interval', 'daily').lower()
            limit = int(request.GET.get('limit', DEFAULT_TIME_SERIES_LIMIT))
            end = request.GET.get('end', None)
            start = request.GET.get('start', None)
            ordering = request.GET.get('ordering', 'asc').lower()
            address = data.get('contract_address')
            script_type = data.get('script_type')
            network = data.get('network')
            token = data.get('token')
            xpub = data.get('xpub')

            try:
                account_object_id = _fetch_xpub_from_db(xpub, network, script_type).id
            except XPubNotRegisteredError as e:
                logger.error('attempting to get multihistory of unregistered xpub: ' + str(e))
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                    }, status=400)

            # non eth token with tx history || OR || eth token with tx history
            if (address is None and xpub in xpubs_with_tx_set) or (address is not None and address.lower() in tokens_with_tx_set):
                results = getBalanceHistoryForXpub(account_object_id, interval, limit, end, start, ordering, address)
                results['network'] =  network
                results['token'] =  token
                results['xpub'] =  xpub
                combinedResults.append(results)

        return JsonResponse({'combinedResults': combinedResults})

class BalancePage(APIView):
    def post(self, request):
        """
        Example Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "script_type": "p2pkh",
                    "network": "BTC"
                },
                ...
            ],
            supportedTokens: {
                "FOX": "0xc770EEfAd204B5180dF6a14Ee197D99d808ee52d",
               ...
            }
        }
        """

        try:
            request_json = json.loads(request.body)
            supported_tokens = request_json.get('supportedTokens', {})
            requested_xpubs = _unpack_and_validate_xpubs(request)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        try:
            account_objects = _fetch_xpubs_from_db(requested_xpubs)
        except ValueError as e:
            logger.error('ERROR' + str(e))
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        # flag indicating whether to time and log requests for balance data
        balance_timing_enabled = is_feature_enabled(ACCOUNT_BALANCE_TIMINGS)

        # flag indicating whether to use local db for eth and token balances
        local_balances_enabled = is_feature_enabled(LOCAL_ACCOUNT_BALANCES)

        # flag indicating whether to use ethereum unchained for balances
        unchained_balances_enabled = is_feature_enabled(UNCHAINED_ACCOUNT_BALANCES)

        eth_accounts = list(filter(lambda x: x.network == ETH, account_objects))

        if unchained_balances_enabled:
            start = current_time_millis()
            eth_balances, token_balances = self.unchained_eth_balances(eth_accounts, supported_tokens)
            if balance_timing_enabled:
                logger.info('[timing] fetch unchained eth and token balances: %sms', (current_time_millis() - start))
        elif local_balances_enabled:
            start = current_time_millis()
            eth_balances, token_balances = self.eth_balances(eth_accounts, supported_tokens)
            if balance_timing_enabled:
                logger.info('[timing] fetch local eth and token balances: %sms', (current_time_millis() - start))
        else:
            eth_balances, token_balances = self.legacy_eth_balances(eth_accounts, supported_tokens)

        # Cosmos
        cosmos_accounts = list(filter(lambda x: x.network == ATOM, account_objects))
        start = current_time_millis()
        cosmos_balances = self.tendermint_account_balances(ATOM, cosmos_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch cosmos balances: %sms', (current_time_millis() - start))

        # Thorchain
        thor_accounts = list(filter(lambda x: x.network == RUNE, account_objects))
        start = current_time_millis()
        thor_balances = self.tendermint_account_balances(RUNE, thor_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch cosmos balances: %sms', (current_time_millis() - start))

        # Osmosis
        osmo_accounts = list(filter(lambda x: x.network == OSMO, account_objects))
        start = current_time_millis()
        osmo_balances = self.tendermint_account_balances(OSMO, osmo_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch osmo balances: %sms', (current_time_millis() - start))

        # Binance
        binance_accounts = list(filter(lambda x: x.network == BNB, account_objects))
        start = current_time_millis()
        binance_balances = self.binance_balances(binance_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch binance balances: %sms', (current_time_millis() - start))

        # Ripple
        ripple_accounts = list(filter(lambda x: x.network == XRP, account_objects))
        start = current_time_millis()
        ripple_balances = self.ripple_balances(ripple_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch ripple balances: %sms', (current_time_millis() - start))

        # EOS
        eos_accounts = list(filter(lambda x: x.network == EOS, account_objects))
        start = current_time_millis()
        eos_balances = self.eos_balances(eos_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch eos balances: %sms', (current_time_millis() - start))

        # FIO
        fio_accounts = list(filter(lambda x: x.network == FIO, account_objects))
        start = current_time_millis()
        fio_balances = self.fio_balances(fio_accounts)

        if balance_timing_enabled:
            logger.info('[timing] fetch fio balances: %sms', (current_time_millis() - start))

        # this `not in []` statement is gross
        utxo_accounts = list(filter(lambda x: x.network not in [ETH, ATOM, BNB, XRP, EOS, FIO, RUNE, OSMO], account_objects))
        start = current_time_millis()
        utxo_balances = self.utxo_balances(utxo_accounts)
        if balance_timing_enabled:
            logger.info('[timing] fetch utxo balances: %sms', (current_time_millis() - start))

        data = utxo_balances + eth_balances + token_balances + cosmos_balances + thor_balances + binance_balances + ripple_balances + eos_balances + osmo_balances + fio_balances

        return JsonResponse({
            'success': True,
            'data': data
        })

    def utxo_balances(self, accounts):
        return [
            {
                'xpub': account.xpub,
                'network': account.network,
                'symbol': account.network,
                'script_type': account.script_type,
                'balance': account.final_balance()
            } for account in accounts
        ]

    def tendermint_account_balances(self, network, accounts):
        balances = list()
        for account in accounts:
            account_address = account.get_account_address().address
            # fetch balances from the db
            account_balances = list(
                AccountBalance.objects.filter(
                    Q(network=network),
                    Q(address=account_address),
                    Q(balance_type='R'),  # remove when we have the other cosmos balances
                    Q(identifier=account_address)
                )
            )

            for balance in account_balances:
                balances.append({
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': account.script_type,
                    'symbol': network,
                    'address': balance.address,
                    'balance': balance.balance
                })

        return balances

    def binance_balances(self, accounts):
        binance_balances = list()
        for account in accounts:
            binance_address = account.get_account_address().address
            account_balances = list(
                AccountBalance.objects.filter(
                    Q(network=BNB),
                    Q(address=binance_address),
                    Q(balance_type='R'),
                    Q(identifier=binance_address)
                )
            )
            for balance in account_balances:
                binance_balances.append({
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': 'binance',
                    'symbol': BNB,
                    'address': balance.address,
                    'balance': balance.balance
                })
        return binance_balances

    def ripple_balances(self, accounts):
        ripple_balances = list()
        for account in accounts:
            ripple_address = account.get_account_address().address
            account_balances = list(
                AccountBalance.objects.filter(
                    Q(network=XRP),
                    Q(address=ripple_address),
                    Q(balance_type='R'),
                    Q(identifier=ripple_address)
                )
            )
            for balance in account_balances:
                ripple_balances.append({
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': 'ripple',
                    'symbol': XRP,
                    'address': balance.address,
                    'balance': balance.balance
                })
        return ripple_balances

    def eos_balances(self, accounts):
        eos_balances = list()
        for account in accounts:
            eos_address = account.get_account_address().address
            account_balances = list(
                AccountBalance.objects.filter(
                    Q(network=EOS),
                    Q(address=eos_address),
                    Q(balance_type='R'),
                    Q(identifier=eos_address)
                )
            )
            for balance in account_balances:
                eos_balances.append({
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': 'eos',
                    'symbol': EOS,
                    'address': balance.address,
                    'balance': balance.balance
                })
        return eos_balances

    def fio_balances(self, accounts):
        fio_balances = list()
        for account in accounts:
            fio_address = account.get_account_address().address
            account_balances = list(
                AccountBalance.objects.filter(
                    Q(network=FIO),
                    Q(address=fio_address),
                    Q(balance_type='R'),
                    Q(identifier=fio_address)
                )
            )
            for balance in account_balances:
                fio_balances.append({
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': 'fio',
                    'symbol': FIO,
                    'address': balance.address,
                    'balance': balance.balance
                })
        return fio_balances

    def eth_balances(self, accounts, supported_tokens):
        # hack to account for symbol mistmatches from axiom
        symbol_map = {'ST': '1ST', 'BNB': 'BNBOLD'}
        def translate_symbol(inputSymbol):
            return symbol_map.get(inputSymbol, inputSymbol)

        supported_tokens_lower = {}
        for symbol, contract_address in supported_tokens.items():
            supported_tokens_lower[symbol] = contract_address.lower()

        tokens_by_contract_addr = {}
        for symbol, contract_address in supported_tokens_lower.items():
            tokens_by_contract_addr[contract_address] = symbol

        eth_balances = list()
        token_balances = list()
        token_map = {}
        for account in accounts:
            eth_address = account.get_account_address().address
            identifiers = list(supported_tokens_lower.values())
            identifiers.append(eth_address)
            # fetch balances from the db
            account_balances = list(
                AccountBalance.objects.filter(
                    Q(network=ETH),
                    Q(address=eth_address),
                    Q(balance_type='R'),
                    Q(identifier__in=identifiers)
                )
            )

            tokens = tokens_by_contract_addr.copy()
            for balance in account_balances:
                b = {
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': ETH.lower(),
                    'symbol': translate_symbol(balance.symbol),
                    'contract_address': None if balance.symbol == ETH else balance.identifier,
                    'address': eth_address,
                    'balance': balance.balance
                }

                if balance.symbol == ETH:
                    eth_balances.append(b)
                else:
                    if token_map.get(b['contract_address']) is None:
                        token_map[b['contract_address']] = list([b])
                    else:
                        token_map[b['contract_address']].append(b)

                tokens.pop(balance.identifier, None)

            # add 0 balance records for any tokens the user has no activity in to make axiom happy
            for contract_address, symbol in tokens.items():
                logger.debug('%s: no local balance available for requested token %s:%s', eth_address, symbol, contract_address)
                b = {
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': ETH.lower(),
                    'symbol': symbol,
                    'contract_address': contract_address,
                    'address': eth_address,
                    'balance': 0
                }
                if token_map.get(b['contract_address']) is None:
                    token_map[b['contract_address']] = list([b])
                else:
                    token_map[b['contract_address']].append(b)

        for symbol, contract_address in supported_tokens_lower.items():
            t1 = token_map.get(contract_address, [])
            token_balances += t1

        return eth_balances, token_balances

    def unchained_eth_balances(self, accounts, tokens):
        unchained = get_unchained_client(ETH)

        eth_balances = list()
        token_balances = list()
        for account in accounts:
            eth_address = account.get_account_address().address
            balances = unchained.get_balances(eth_address, account.id, tokens)

            eth_balance = balances.get(ETH)
            if eth_balance is None:
                eth_balance = '0'

            eth_balances.append({
                'xpub': account.xpub,
                'network': account.network,
                'script_type': ETH.lower(),
                'symbol': ETH,
                'contract_address': None,
                'address': eth_address,
                'balance': eth_balance
            })

            for symbol, contract_address in tokens.items():
                token_balance = balances.get(contract_address.lower())
                if token_balance is None:
                    token_balance = '0'

                token_balances.append({
                    'xpub': account.xpub,
                    'network': account.network,
                    'script_type': ETH.lower(),
                    'symbol': symbol,
                    'contract_address': contract_address,
                    'address': eth_address,
                    'balance': token_balance
                })

        return eth_balances, token_balances

    def legacy_eth_balances(self, accounts, tokens):
        balance_timing_enabled = is_feature_enabled(ACCOUNT_BALANCE_TIMINGS)
        eth_balances = []
        token_balances = []
        # setup async loop for concurrent token balance requests
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for account in accounts:
            eth_address = account.get_account_address().address

            eth_balances.append({
                'xpub': account.xpub,
                'network': account.network,
                'script_type': ETH.lower(),
                'symbol': ETH,
                'contract_address': None,
                'address': eth_address
            })

            # format ETH token balance request for CQ
            for symbol, contract_address in tokens.items():
                token_balances.append({
                    'xpub': account.xpub,
                    'network': ETH,
                    'script_type': ETH.lower(),
                    'symbol': symbol,
                    'contract_address': contract_address,
                    'address': eth_address,
                    'balance': None
                })

            start = current_time_millis()
            loop.run_until_complete(self._fetch_token_balances(token_balances, eth_address))

            if balance_timing_enabled:
                logger.info('[timing] fetch token balances: %sms', (current_time_millis() - start))

        loop.close()

        # process eth balances
        start = current_time_millis()
        eth_balances = self.get_eth_xpub_balances(eth_balances)
        if balance_timing_enabled:
            logger.info('[timing] fetch eth balances: %sms', (current_time_millis() - start))

        return eth_balances, token_balances

    async def _fetch_token_balances(self, tokens, address):
        loop_ref = asyncio.get_event_loop()
        session = requests.Session()
        session.mount('https://', HTTPAdapter(pool_maxsize=20))
        futures = []

        # get all token balances from redis in one shot
        balance_keys = list(map(lambda token: eth_balance_cache_key_format(token.get('address'), token.get('contract_address')), tokens))
        balances = redisClient.mget(balance_keys)

        for i, t in enumerate(tokens):
            if balances[i] is not None:
                t['balance'] = balances[i]
            else:
                contract_addr = t['contract_address']
                url = self._get_token_balance_url(contract_addr, address)
                futures.append(loop_ref.run_in_executor(None, self._get_token_balance, session, url, contract_addr, balances[i]))

        # await and update balances
        if len(futures):
            results, _ = await asyncio.wait(futures)

            for r in results:
                balance, contract_addr = r.result()
                # store eth token balance in cache
                key = eth_balance_cache_key_format(address, contract_addr)
                redisClient.setex(key, ETH_BALANCE_TTL, balance)
                t = next((t for t in tokens if t['contract_address'] == contract_addr and t['address'] == address), None)
                t['balance'] = balance

        session.close()

    def _get_token_balance_url(self, contract, addr):
        params = {
            'module': 'account',
            'action': 'tokenbalance',
            'contractaddress': contract,
            'address': addr,
            'tag': 'latest',
            'apikey': 'watchtower-' + os.environ.get('ENV'),
        }

        query_string = '&'.join(['{}={}'.format(k, v) for k, v in params.items()])

        return '{base_url}?{query_string}'.format(
            base_url=os.getenv('COINQUERY_ETH_URL'),
            query_string=query_string
        )

    def _get_token_balance(self, session, url, contract_addr, balance):
        if url is not None:
            try:
                response = session.get(url)
                json_data = response.json()
                balance = json_data.get('result', None)
            except Exception as e:
                logger.error('failed to GET ETH token balance from: {} | reason: {}'.format(url, str(e)))

        return balance, contract_addr

    def get_eth_xpub_balances(self, xpubs):
        if xpubs:
            for eth in xpubs:
                key = eth_balance_cache_key_format(eth['address'])
                balance = redisClient.get(key)
                if balance is None:
                    params = {
                        'module': 'account',
                        'action': 'balance',
                        'address': eth['address'],
                        'tag': 'latest',
                        'apikey': 'watchtower-' + os.environ.get('ENV'),
                    }

                    query_string = '&'.join(['{}={}'.format(k, v) for k, v in params.items()])

                    url = '{base_url}?{query_string}'.format(
                        base_url=os.getenv('COINQUERY_ETH_URL'),
                        query_string=query_string
                    )

                    try:
                        response = requests.get(url)
                        json_data = response.json()
                        balance = json_data.get('result', None)
                        # store eth token balance in cache
                        redisClient.setex(key, ETH_BALANCE_TTL, balance)
                    except Exception as e:
                        logger.error('failed to GET ETH balance from %s: %s', os.getenv('COINQUERY_ETH_URL'), str(e))
                    finally:
                        eth.pop('address')

                eth['balance'] = balance

        return xpubs

class CreateUnsignedTransactionPage(APIView):
    def post(self, request):
        """
        Example Request Payload:
        {
            "network": "BTC",
            "inputs": [ // Where to select inputs from. Only one is allowed on ETH.
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "script_type": "p2pkh",
                    "account_address_n": [2147483692, 2147483648, 2147483648]
                }
            ],
            "token": "SALT",  // Optional. If provided, network must be ETH.
            "contract_address": "0xfeasdf...",  // Optional. If provided, will override "token".
            "include_txs": true,  // Optional. Defaults to false
            "include_hex": false, // Optional. Defaults to false (Ledger requires this however)
            "recipients": [
                {
                    "address": 12DrP8aGcXHBkdKEnWVa7t3TJ1FvAzm6Nh,
                    "send_max": false, // If true, amount need not be present
                    "amount": 10000,  // Units in Satoshis (or Wei for Ethereum)
                    "data": "0x",  // Optional for ETH/tokens. Ignored for utxo coins.
                    "script_type": "p2pkh"
                }
            ],
            "desired_conf_time": "halfHour",   // fastest, halfHour, 1hour, 6hour, 24hour (default = halfHour)
                                               // only used for BTC
            "effort": "5"                      // 1-5, 5 = fastest, 1 = cheapest
        }                                      // only used for BTC
        """
        try:
            request_json = json.loads(request.body)  # TODO: Validation
            network = request_json.get('network')
            _validate_network(network)
            input_xpubs = []

            efforts = {
                5: 'fastest',
                4: 'halfHour',
                3: '1hour',
                2: '6hour',
                1: '24hour'
            }
            requested_effort = request_json.get('effort', None)

            desired_conf_time = efforts.get(requested_effort, None)
            if desired_conf_time is None:
                desired_conf_time = request_json.get('desired_conf_time', 'halfHour')

            inputs = request_json.get('inputs', [])
            if not isinstance(inputs, list) or len(inputs) == 0:
                return JsonResponse({
                    'success': False,
                    'error': "Must provide a non-empty array of inputs"
                }, status=400)

            for i in inputs:
                xpub = i.get('xpub')
                script_type = i.get('script_type')
                account_address_n = i.get('account_address_n')
                if account_address_n is None:
                    return JsonResponse({
                        'success': False,
                        'error': "Must provide account_address_n for xpub"
                    }, status=400)
                _validate_xpub(xpub, network, script_type)
                input_xpubs.append((xpub, network, script_type, account_address_n))
            token = request_json.get('token', None)
            contract_address = request_json.get('contract_address', None)
            _recipients = request_json.get('recipients')
            include_txs = request_json.get('include_txs', False)
            include_hex = request_json.get('include_hex', False)
            op_return_data = request_json.get('op_return_data', None)

        except ValueError as e:
            logger.error('Error gathering input for create unsigned tx: %s', e)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        # TODO: validate recipients
        # Coalesce recipient amounts into integers
        recipients = []
        has_max = False
        for recipient in _recipients:
            if recipient.get('send_max', False):
                if has_max:
                    return JsonResponse({
                        'success': False,
                        'error': "Cannot send_max to multiple recipients"
                    })
                recipient['send_max'] = True
                recipient['amount'] = None
                has_max = True
            else:
                recipient['send_max'] = False
                recipient['amount'] = int(recipient['amount'])
            recipients.append(recipient)

        # Fetch xpubs from db or register if they don't exist
        account_objects = []
        for xpub, network, script_type, account_address_n in input_xpubs:
            try:
                account_object = _fetch_xpub_from_db(xpub, network, script_type)
                account_object.account_address_n = account_address_n
            except XPubNotRegisteredError:
                return JsonResponse({
                    'success': False,
                    'error': str(XPubNotRegisteredError)
                }, status=400)

            account_objects.append(account_object)

        if len(set(account_objects)) != len(input_xpubs):
            return JsonResponse({
                'success': False,
                'error': 'Supplied input (xpub, script_type) pairs must be unique'
            }, status=400)

        if network == ETH and len(account_objects) != 1:
            return JsonResponse({
                'success': False,
                'error': 'Only one xpub is allowed in \'inputs\' when network is ETH'
            }, status=400)

        if len(account_objects) < 1:
            return JsonResponse({
                'success': False,
                'error': 'Must provide at least one xpub'
            }, status=400)

        if token and not contract_address:
            contract_address = ERC20Token.lookup_contract_address(token)

        if network == ETH and (token or contract_address):
            return self._handle_erc20_token(
                account_objects[0],
                recipients,
                contract_address,
                token=token,
            )

        elif network == ETH:
            return self._handle_ethereum(account_objects[0], recipients)

        else:
            return self._handle_utxo_coin(account_objects, recipients, network, include_txs, include_hex, desired_conf_time, op_return_data)

    def _handle_utxo_coin(self, account_objects, recipients, network, include_txs, include_hex, desired_conf_time, op_return_data):
        # Always send change back to the 0th xpub:
        change_address_obj = account_objects[0].get_change_address()

        change_script_type = account_objects[0].script_type
        change_account_address_n = account_objects[0].account_address_n + [CHANGE, change_address_obj.index]

        # dont send less than the dust limit
        min_send_amt = get_dust_limit(network, change_script_type)

        for recipient in recipients:
            if recipient['send_max']:
                continue

            if recipient['amount'] < min_send_amt:
                return JsonResponse({
                    'success':False,
                    'error': 'Error: send amount is below the minimum threshold {} satoshis. This prevents creating "dust" utxos that cost more to spend than they are worth'.format(min_send_amt)
                }, status=400)

        try:
            # Gather utxos for all the xpubs
            utxos = reduce(itertools.chain, map(lambda xpub: xpub.get_utxos(xpub.account_address_n), account_objects))
        except Exception as e:
            logger.error('error getting utxos: %s', e)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        try:
            unsigned_tx = create_unsigned_utxo_transaction(
                network,
                utxos,
                recipients,
                change_address_obj.address,
                change_script_type,
                change_address_obj.index,
                change_address_obj.relpath,
                change_account_address_n,
                desired_conf_time,
                op_return_data,
                utxo_selection_strategy=SMALLEST_VALUE_FIRST
            )
        except InsufficientFundsError as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'estimatedFee': e.estimated_fee
            }, status=400)
        except Exception as e:
            logger.error('error in create_unsigned_utxo_transaction: %s', e)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        try:
            # adds prev tx to legacy inputs (utxos) to help with KeepKey signing flow
            def needs_prevtx(tx_input):
                if tx_input['script_type'] == 'p2sh-p2wpkh':
                    return False
                if tx_input['script_type'] == 'p2wpkh':
                    return False
                if tx_input['script_type'] == 'p2wsh':
                    return False
                # ForceBip143 coins:
                if network == BCH:
                    return False
                #if network == BTG:
                #    return False
                return True

            coinquery = get_coinquery_client(network)
            txids_needing_prevtx = [tx_input['txid'] for tx_input in unsigned_tx['inputs'] if include_txs and needs_prevtx(tx_input)]
            txids_needing_raw_hex = [tx_input['txid'] for tx_input in unsigned_tx['inputs'] if include_hex]
            prevtx_map = coinquery.get_transactions_for_txids(txids_needing_prevtx, precise=True)
            rawtx_map = coinquery.get_raw_transactions_for_txids(txids_needing_raw_hex)

            for tx_input in unsigned_tx['inputs']:
                tx_input['tx'] = prevtx_map.get(tx_input['txid'], None)
                tx_input['hex'] = rawtx_map.get(tx_input['txid'], None)

        except Exception as e:
            logger.error('error assembling unsigned tx: %s', e)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        # Convert input and output amounts into strings
        formatted_inputs = []
        for _input in unsigned_tx['inputs']:
            _input['amount'] = str(_input['amount'])
            formatted_inputs.append(_input)

        formatted_outputs = []
        for _output in unsigned_tx['outputs']:
            _output['amount'] = str(_output['amount'])
            formatted_outputs.append(_output)

        formatted_unsigned_tx = {
            'inputs': formatted_inputs,
            'outputs': formatted_outputs,
            'fee': unsigned_tx['fee'],
            'feePerKB': unsigned_tx['feePerKB']
        }

        return JsonResponse({
            'success': True,
            'data': formatted_unsigned_tx
        })

    def _handle_erc20_token(self, account_object, recipients, contract_address, token=None):
        contract_address = format_ethereum_address(contract_address)
        from_address = format_ethereum_address(account_object.get_account_address().address)
        transaction_count = get_ethereum_transaction_count(from_address)
        results = []

        # Make sure we have an ETH xpub
        eth_address_obj = account_object.get_account_address()
        if not eth_address_obj:
            return JsonResponse({
                'success': False,
                'error': 'Unable to find ethereum address.'
            }, status=400)

        token_balance = int(get_eth_token_balance(contract_address, eth_address_obj.address))

        try:
            token = ERC20Token.get_or_create(contract_address)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Could not fetch token precision for {}'.format(contract_address)
            })

        for i, recipient in enumerate(recipients, start=0):
            to_address = recipient['address']
            if recipient['send_max']:
                if len(recipients) > 1:
                    return JsonResponse({
                        'success': False,
                        'error': 'ERC20 send_max not yet supported for multiple recipeints'
                    }, status=400)
                token_value = token_balance
            else:
                token_value = recipient['amount']  # TODO: make sure this is in token's precision format
            nonce = transaction_count + i
            transfer_data = recipient.get('data')

            gas_price = get_cached_gas_price()
            eip1559_fees = get_cached_eip1559_fees()
            priority_fee_per_gas = eip1559_fees.get('priorityFeePerGas', None)
            base_fee_per_gas = eip1559_fees.get('baseFeePerGas', None)

            # Catch and break with any error we get from estimate_toke_gas_limit
            # This should only blow up if the token_value is greater than the balance
            from_address = web3.toChecksumAddress(from_address)
            to_address = web3.toChecksumAddress(to_address)
            try:
                gas_limit = estimate_token_gas_limit(
                    contract_address,
                    from_address,
                    to_address,
                    int(token_value)
                )
            except Exception:
                logger.error('Error estimating gas limit for ERC20 send transaction')
                break

            transaction_params = {
                'from': from_address,
                'to': contract_address,
                'value': 0,
                'nonce': nonce,
                'gas_price': gas_price,
                'gas_limit': gas_limit,
                'maxFeePerGas': base_fee_per_gas + priority_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee_per_gas
            }

            if not transfer_data:
                transfer_data = get_token_transfer_data(
                    contract_address,
                    from_address,
                    to_address,
                    int(token_value),
                    gas_limit,
                    gas_price,
                    nonce
                )

            transaction_params.update({
                'data': transfer_data
            })

            results.append(transaction_params)

        # Make sure we have enough ether to cover gas
        fee_key = 'maxFeePerGas' if is_feature_enabled(INCLUDE_EIP1559_FEES) else 'gas_price'
        gas_needed = sum( [int(tx[fee_key]) * int(tx['gas_limit']) for tx in results] )
        
        eth_balance = account_object.final_balance()
        if gas_needed > eth_balance:
            return JsonResponse({
                'success': False,
                'error': 'Not enough funds to cover gas. {gas_needed} ETH is needed but only {eth_balance} ETH is available.'.format(  # noqa
                    gas_needed=web3.fromWei(gas_needed, 'ether'),
                    eth_balance=web3.fromWei(eth_balance, 'ether')
                )
            }, status=400)

        # Make sure we have enough tokens to send
        token_send_amount = sum([int(r.get('amount') or token_balance) for r in recipients])

        if token_send_amount > token_balance:
            return JsonResponse({
                'success': False,
                'error': str(InsufficientFundsError())
            }, status=400)

        return JsonResponse({
            'success': True,
            'data': results
        })

    def _handle_ethereum(self, account_object, recipients):
        eth_address = account_object.get_account_address().address
        from_address = format_ethereum_address(eth_address)
        transaction_count = get_ethereum_transaction_count(from_address)
        results = []

        total_balance = int(get_eth_balance(eth_address))

        for i, recipient in enumerate(recipients, start=0):
            to_address = recipient['address']
            if recipient['send_max']:
                if len(recipients) > 1:
                    return JsonResponse({
                        'success': False,
                        'error': 'ETH send_max not yet supported for multiple recipeints'
                    }, status=400)
                value = 1 # Placeholder until we know the actual max value we can send
            else:
                value = recipient['amount']
            nonce = transaction_count + i
            data = recipient.get('data', '0x')
            
            from_address = web3.toChecksumAddress(from_address)
            to_address = web3.toChecksumAddress(to_address)

            transaction_params = {
                'from': from_address,
                'to': to_address,
                'value': value,
                'nonce': nonce,
                'data': data
            }

            gas_price = get_cached_gas_price()
            eip1559_fees = get_cached_eip1559_fees()
            priority_fee_per_gas = eip1559_fees.get('priorityFeePerGas', None)
            base_fee_per_gas = eip1559_fees.get('baseFeePerGas', None)
            gas_limit = estimate_ethereum_gas_limit(transaction_params)

            if is_feature_enabled(INCLUDE_EIP1559_FEES):
                fee = (int(base_fee_per_gas) + int(priority_fee_per_gas)) * int(gas_limit)
            else:
                fee = int(gas_price) * int(gas_limit)

            transaction_params.update({
                'gas_price': gas_price,
                'gas_limit': gas_limit,
                'maxFeePerGas': base_fee_per_gas + priority_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee_per_gas
            })

            if recipient['send_max']:
                transaction_params.update({
                    # need to convert to string because javascript sucks at numbers
                    'value': str(total_balance - fee)
                })

            results.append(transaction_params)

        # Make sure we have enough funds
        fee_key = 'maxFeePerGas' if is_feature_enabled(INCLUDE_EIP1559_FEES) else 'gas_price'
        total_send_amount = sum([
            sum([
                int(tx['value']),
                int(tx[fee_key]) * int(tx['gas_limit'])
            ]) for tx in results
        ])

        if total_send_amount > total_balance:
            return JsonResponse({
                'success': False,
                'error': str(InsufficientFundsError())
            }, status=400)

        return JsonResponse({
            'success': True,
            'data': results
        })


class SendTransactionPage(APIView):
    def post(self, request):
        """
        Example Request Payload:
        {
            "network": "BTC",
            "rawtx": "01000000017b1eabe0209b1fe794124..."
        }
        """
        try:
            logger.info('/send request: {}'.format(request.body))
            request_json = json.loads(request.body)
            network = request_json.get('network')
            _validate_network(network)
            # TODO: validate rawtx
            rawtx = request_json.get('rawtx')

        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        try:
            if network == ETH:
                txid = web3.toHex(web3.eth.sendRawTransaction(rawtx))             
            elif network == BNB:
                txid = binance_client.broadcast(rawtx)
            elif network == XRP:
                txid = ripple.broadcast(rawtx)
            elif network == FIO:
                txid = fio.broadcast(rawtx)
            elif network == EOS:
                txid = eos_client.broadcast(rawtx, request_json.get('signatures'))
            elif network in [ATOM, RUNE, OSMO]:
                gaia = get_gaia_client(network)
                txid = gaia.broadcast(rawtx)
            else:
                coinquery = get_coinquery_client(network)
                txid = coinquery.send(rawtx)
                self.start_watching_tx(network, txid)

            return JsonResponse({
                'success': True,
                'txid': txid
            })
        except Exception as e:
            logger.error('error sending tx %s', e)

            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

    def start_watching_tx(self, network, txid):
        redisClient.sadd(WATCH_TX_SET_KEY + network, txid)

class ReceiveAddressPage(APIView):
    def post(self, request):
        """
        Example Request Payload:
        {
            "network": "BTC",
            "xpub": "xpub6BiVtCpG9fQPxnP...",
            "script_type": "p2pkh",
            "count": 3  // Optional. Defaults to 1
        }
        """
        try:
            request_json = json.loads(request.body)
            network = request_json.get('network')
            _validate_network(network)

            xpub = request_json.get('xpub')

            script_type = request_json.get('script_type')
            _validate_xpub(xpub, network, script_type)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        count = max(request_json.get('count', 1), 1)

        if count > GAP_LIMIT:
            return JsonResponse({
                    'success': False,
                    'error': str('Requested more than GAP_LIMIT addresses')
                }, status=400)

        # Fetch xpub from db. If it doesn't exist, go ahead and register it.
        try:
            account_object = _fetch_xpub_from_db(xpub, network, script_type)
        except XPubNotRegisteredError:
            return JsonResponse({
                'success': False,
                'error': str(XPubNotRegisteredError)
            }, status=400)


        receive_addresses = account_object.get_receive_addresses(count)

        # don't watch address on networks with short block times
        if network not in [ETH, ATOM, BNB, XRP, FIO, RUNE, OSMO]:
            self.start_watching_addresses(receive_addresses)

        addrs = receive_addresses
        if network == BCH:
            cash_addrs = []
            for o in receive_addresses:
                o.address = convert_bch.to_cash_address(o.address)
                cash_addrs.append(o)
            addrs = cash_addrs

        return JsonResponse({
            'success': True,
            'data': [{
                'address': obj.address,
                'relpath': obj.relpath
            } for obj in addrs]
        })

    def start_watching_addresses(self, addresses):
        for address in addresses:
            logger.info('start watching addr: {}'.format(address))
            watch = {
                'network': address.account.network,
                'address': address.address,
                'relpath': address.relpath,
                'index': address.index,
                'xpub': address.account.xpub,
                'type': address.type,
                'current': 0
                }
            redisClient.set(WATCH_ADDRESS_PREFIX + address.address,
                            json.dumps(watch),
                            ex=WATCH_ADDRESS_EXPIRATION_SECONDS)
            redisClient.sadd(WATCH_ADDRESS_SET_KEY, address.address)


class AssetsInOrbitPage(APIView):
    def get(self, request):
        with db_connection.cursor() as cursor:
            sql = """
                SELECT network asset, sum(balance) / (10 ^ 6), 'atom'
                FROM tracker_accountbalance
                    WHERE network = 'ATOM' and symbol = 'ATOM'
                GROUP BY network
                UNION ALL
                SELECT network asset, sum(balance) / (10 ^ 6), 'thor'
                FROM tracker_accountbalance
                    WHERE network = 'RUNE' and symbol = 'RUNE'
                GROUP BY network
                UNION ALL
                SELECT network asset, sum(balance) / (10 ^ 6), 'osmo'
                FROM tracker_accountbalance
                    WHERE network = 'OSMO' and symbol = 'OSMO'
                GROUP BY network
                UNION ALL
                SELECT account.network asset, SUM(bc.amount) / (10 ^ 9) total, 'fio'
                FROM tracker_account account
                       JOIN tracker_transaction tx ON account.id = tx.account_id
                       JOIN tracker_balancechange bc ON account.id = bc.account_id AND tx.id = bc.transaction_id
                       JOIN tracker_address addr ON bc.address_id = addr.id
                WHERE account.network in ('FIO')
                GROUP BY account.network
                UNION ALL
                SELECT account.network asset, SUM(bc.amount) / (10 ^ 8) total, 'bnb'
                FROM tracker_account account
                       JOIN tracker_transaction tx ON account.id = tx.account_id
                       JOIN tracker_balancechange bc ON account.id = bc.account_id AND tx.id = bc.transaction_id
                       JOIN tracker_address addr ON bc.address_id = addr.id
                WHERE account.network = 'BNB'
                GROUP BY account.network
                UNION ALL
                SELECT account.network asset, SUM(bc.amount) / (10 ^ 8) total, 'utxo'
                FROM tracker_account account
                       JOIN tracker_transaction tx ON account.id = tx.account_id
                       JOIN tracker_balancechange bc ON account.id = bc.account_id AND tx.id = bc.transaction_id
                       JOIN tracker_address addr ON bc.address_id = addr.id
                WHERE account.network in ('BTC','BCH','DGB','DOGE','DASH','LTC')
                GROUP BY account.network
                UNION ALL
                SELECT account.network asset, SUM(bc.amount) / (10 ^ 6) total, 'xrp'
                FROM tracker_account account
                       JOIN tracker_transaction tx ON account.id = tx.account_id
                       JOIN tracker_balancechange bc ON account.id = bc.account_id AND tx.id = bc.transaction_id
                       JOIN tracker_address addr ON bc.address_id = addr.id
                WHERE account.network in ('XRP')
                GROUP BY account.network
                UNION ALL
                SELECT network asset, sum(balance) / (10 ^ 18), 'eth'
                FROM tracker_accountbalance
                WHERE network = 'ETH' and symbol = 'ETH'
                GROUP BY network
                UNION ALL
                SELECT erc20.symbol, SUM(bc.amount) / (10 ^ erc20.precision), erc20.contract_address
                FROM tracker_account account
                       JOIN tracker_transaction tx ON account.id = tx.account_id
                       JOIN tracker_balancechange bc ON account.id = bc.account_id AND tx.id = bc.transaction_id
                       JOIN tracker_address addr ON bc.address_id = addr.id
                       JOIN tracker_erc20token erc20 ON tx.erc20_token_id = erc20.id
                WHERE account.network = 'ETH'
                  AND tx.is_erc20_token_transfer
                GROUP BY erc20.symbol, erc20.precision, erc20.contract_address
                """
            cursor.execute(sql)
            results = cursor.fetchall()
        return JsonResponse({
            'success': True,
            'data': results
        })

class XPubStatusPage(APIView):
    # migrate handles registering accounts and associated addresses with unchained coinstacks.
    # by calling save on the associated addresses, we can leverage the existing signals to publish the registration message.
    def migrate(self, account):
        if should_migrate(account):
            for address in account.get_addresses():
                try:
                    address.save()
                except Exception as e:
                    logger.error('failed to register existing address: %s: %s', address.address, str(e))
                    raise e


    def post(self, request):
        try:
            xpubs = _unpack_and_validate_xpubs(request)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        results = []

        for xpub, network, script_type in xpubs:
            try:
                account_object = _fetch_xpub_from_db(xpub, network, script_type)
            except XPubNotRegisteredError as e:
                logger.error('attempting to get status of unregistered pubkey: ' + str(e))
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=400)

            try:
                self.migrate(account_object)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=400)

            tx_count = Transaction.objects.filter(account=account_object).count()

            result = {
                'xpub': account_object.xpub,
                'network': account_object.network,
                'script_type': account_object.script_type,
                'registered_at': account_object.registered_at,
                'updated_at': account_object.updated_at,
                'sync_status': account_object.sync_status,
                'tx_count': tx_count
            }
            results.append(result)

        return JsonResponse({
            'success': True,
            'data': results
        })

class SyncAccountBasedBalancesPage(APIView):
    def post(self, request):
        try:
            xpubs = _unpack_and_validate_xpubs(request)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        try:
            account_objects = _fetch_xpubs_from_db(xpubs)
        except ValueError as e:
            logger.error('ERROR' + str(e))
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

        eth_accounts = list(filter(lambda x: x.network == ETH, account_objects))
        cosmos_accounts = list(filter(lambda x: x.network == ATOM, account_objects))
        thorchain_accounts = list(filter(lambda x: x.network == RUNE, account_objects))
        osmo_accounts = list(filter(lambda x: x.network == OSMO, account_objects))
        binance_accounts = list(filter(lambda x: x.network == BNB, account_objects))
        ripple_accounts = list(filter(lambda x: x.network == XRP, account_objects))
        fio_accounts = list(filter(lambda x: x.network == FIO, account_objects))

        result = list()
        for account in eth_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing eth account balances: %s', address)
                sync_eth_account_balances.s(address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        for account in cosmos_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing atom account balances: %s', address)
                sync_account_balances.s(ATOM, address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        for account in thorchain_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing thorchain account balances: %s', address)
                sync_account_balances.s(RUNE, address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        for account in osmo_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing osmo account balances: %s', address)
                sync_account_balances.s(OSMO, address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        for account in binance_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing bnb account balances: %s', address)
                sync_bnb_account_balances.s(address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        for account in fio_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing fio account balances: %s', address)
                sync_fio_account_balances.s(address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        for account in ripple_accounts:
            address = account.get_account_address().address
            locked = redisClient.get(self.cache_key(account.network, address))
            if locked is None:
                logger.info('syncing xrp account balances: %s', address)
                sync_xrp_account_balances.s(address).apply_async()
                result.append(address)
                redisClient.setex(self.cache_key(account.network, address), BALANCE_SYNC_TTL, address)
            else:
                logger.debug('recently synced account %s, ignoring', address)

        return JsonResponse({
            'success': True,
            'data': result
        })

    def cache_key(self, network, address):
        return 'watchtower:{}:balances:sync:lock:{}'.format(network.lower(), address)
