import requests


class EtherscanClient:
    API_BASE_URL = 'https://api.etherscan.io/api'

    # User to override incorrect values from etherscan
    REP_OVERIDE_SETTINGS = {
        'address': '0x1985365e9f78359a9b6ad760e32412f4a445e862',
        'symbol': 'REP',
        'name': 'Augur',
        'decimals': '18'
    }

    def __init__(self, api_key):
        super().__init__()
        self.API_KEY = api_key

    def get(self, params):
        query_string = '&'.join(['{}={}'.format(k, v) for k, v in params.items()])

        url = '{base_url}?{query_string}'.format(
            base_url=self.API_BASE_URL,
            query_string=query_string
        )
        response = requests.get(url)
        json_data = response.json()
        json_result = json_data.get('result', None)
        return json_result

    def get_balance(self, address):
        query_params = {
            'module': 'account',
            'action': 'balance',
            'address': address,
            'tag': 'latest',
            'apikey': self.API_KEY,
        }
        return self.get(query_params)

    def get_token_balance(self, contract_address, address):
        query_params = {
            'module': 'account',
            'action': 'tokenbalance',
            'contractaddress': contract_address,
            'address': address,
            'tag': 'latest',
            'apikey': self.API_KEY,
        }
        return self.get(query_params)

    def get_ethereum_transactions(
        self,
        address,
        start_block=None,
        end_block=None,
        sort='desc',
        page=None,
        limit=1000
    ):
        """
        Returns up to a maximum of the last `limit` transactions.
        """
        query_params = {
            'module': 'account',
            'action': 'txlist',
            'address': address,
            'sort': sort,
            'apikey': self.API_KEY
        }

        if isinstance(start_block, int):
            query_params['startblock'] = start_block

        if isinstance(end_block, int):
            query_params['endblock'] = end_block

        if isinstance(page, int):  # page number, starting at 1
            query_params['page'] = page

        if isinstance(limit, int):  # max records to return
            query_params['offset'] = limit

        return self.get(query_params)

    def get_internal_ethereum_transactions(
        self,
        address,
        start_block=None,
        end_block=None,
        sort='desc',
        page=None,
        limit=1000
    ):
        """
        Returns up to a maximum of the last `limit` transactions.
        """
        query_params = {
            'module': 'account',
            'action': 'txlistinternal',
            'address': address,
            'sort': sort,
            'apikey': self.API_KEY
        }

        if isinstance(start_block, int):
            query_params['startblock'] = start_block

        if isinstance(end_block, int):
            query_params['endblock'] = end_block

        if isinstance(page, int):  # page number, starting at 1
            query_params['page'] = page

        if isinstance(limit, int):  # max records to return
            query_params['offset'] = limit

        return self.get(query_params)

    def get_internal_txs_by_block_number(
        self,
        block_number,
        sort='desc',
        limit=1000
    ):
        query_params = {
            'module': 'account',
            'action': 'txlistinternal',
            'startBlock': block_number,
            'endBlock': block_number,
            'sort': sort,
            'apikey': self.API_KEY
        }

        if isinstance(limit, int):  # max records to return
            query_params['offset'] = limit

        page = 1
        processing = True
        transactions = dict()
        while processing:
            query_params['page'] = page
            txs = self.get(query_params)

            # only support eth internal transactions at this time
            ethTxs = list(filter(lambda tx: tx.get('contractAddress') == '' and tx.get('from') and tx.get('to'), txs))

            for tx in ethTxs:
                txid = tx.get('hash')

                if transactions.get(txid) is None:
                    transactions[txid] = []

                transactions[txid].append(tx)

            page += 1

            if len(txs) < limit:
                processing = False

        return transactions

    def get_token_transfer_events(
        self,
        address=None,
        contract_address=None,
        start_block=None,
        end_block=None,
        sort='desc',
        page=None,
        limit=1000
    ):
        """
        Returns up to a maximum of the last `limit` transactions.
        """
        query_params = {
            'module': 'account',
            'action': 'tokentx',
            'sort': sort,
            'apikey': self.API_KEY
        }

        if address and isinstance(address, str):
            query_params['address'] = address

        if contract_address and isinstance(contract_address, str):
            query_params['contractaddress'] = contract_address

        if isinstance(start_block, int):
            query_params['startblock'] = start_block

        if isinstance(end_block, int):
            query_params['endblock'] = end_block

        if isinstance(page, int):  # page number, starting at 1
            query_params['page'] = page

        if isinstance(limit, int):  # max records to return
            query_params['offset'] = limit

        transactions = self.get(query_params)

        # Special case fix for REP which does not return symbol and token_name from etherscan
        for transaction in transactions:
            if transaction['contractAddress'].lower() == self.REP_OVERIDE_SETTINGS['address']:
                transaction['tokenSymbol'] = self.REP_OVERIDE_SETTINGS['symbol']
                transaction['tokenName'] = self.REP_OVERIDE_SETTINGS['name']
                transaction['tokenDecimal'] = self.REP_OVERIDE_SETTINGS['decimals']

        return transactions

    def get_latest_block_height(self):
        query_params = {
            'module': 'proxy',
            'action': 'eth_blockNumber',
            'apikey': self.API_KEY
        }

        block_height_hex = self.get(query_params)
        block_height_int = int(block_height_hex, 0)
        return block_height_int
