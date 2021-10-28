from datetime import datetime, timezone

from django.db import models

from common.services.coinquery import get_client as get_coinquery_client
from common.utils.networks import SUPPORTED_NETWORK_CHOICES, ETH, ATOM, BNB, XRP, EOS, FIO, RUNE, KAVA, SCRT, OSMO
from common.utils.bip32 import derive_addresses, derive_ethereum_address, SUPPORTED_ADDR_KIND_CHOICES
from common.utils.blockchain import get_latest_block_height
from common.services import cointainer_web3 as web3
from common.utils.ethereum import ERC20_ABI

import logging
from django.db import connection

logger = logging.getLogger('watchtower.tracker.models')

SUPPORTED_SYNC_STATUS_CHOICES = (
    ('NOT_STARTED', 'NOT_STARTED'),
    ('SYNCING', 'SYNCING'),
    ('FAILED', 'FAILED'),
    ('COMPLETE', 'COMPLETE'),
)


class Account(models.Model):
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    xpub = models.CharField(max_length=255)
    network = models.CharField(max_length=100, choices=SUPPORTED_NETWORK_CHOICES)
    script_type = models.CharField(max_length=16, choices=SUPPORTED_ADDR_KIND_CHOICES)
    sync_status = models.CharField(max_length=16, choices=SUPPORTED_SYNC_STATUS_CHOICES, default='NOT_STARTED')
    migrated = models.BooleanField(default=False)

    class Meta:
        unique_together = ('xpub', 'network', 'script_type')

    def __str__(self):
        return '<Account: {}, {}, {}>'.format(self.xpub, self.network, self.script_type)

    def update_sync_status(self, status):
        self.sync_status = status
        self.save()

    def get_addresses(self):
        return Address.objects.filter(account=self)

    def get_addresses_with_balance(self):
        non_zero_balance_address_ids = []
        for address in Address.objects.filter(account=self):
            balance = address.get_balance()
            if balance.__bool__() == True:
                if balance < 0:
                    logger.error('Address {} has a negative balance tracked in watchtower DB'.format(address.address))
                non_zero_balance_address_ids.append(address.id)
        return Address.objects.filter(id__in=non_zero_balance_address_ids)

    def get_transactions(self):
        return Transaction.objects.filter(account=self)

    def sync(self, _async=True, start_index=0):
        from ingester.tasks import sync_xpub

        sync_function = sync_xpub.delay if _async else sync_xpub
        # Passing False avoids publish on initial sync
        sync_function(self.xpub, self.network, self.script_type, False, start_index=start_index)

    def derive_external_addresses(self, count, from_index=0):
        return derive_addresses(self.xpub, '0', count, from_index=from_index, network=self.network,
                                script_type=self.script_type)

    def derive_internal_addresses(self, count, from_index=0):
        return derive_addresses(self.xpub, '1', count, from_index=from_index, network=self.network,
                                script_type=self.script_type)

    def derive_ethereum_address(self):
        assert self.network == ETH, 'Network must be ETH.'
        return derive_ethereum_address(self.xpub)

    def transactions_count(self):
        return Transaction.objects.filter(account=self).count()

    def total_received(self):
        return Transaction.objects.filter(account=self).annotate(
            balance_change=models.Sum('balancechange__amount')
        ).filter(
            balance_change__gte=0
        ).aggregate(
            models.Sum('balance_change')
        ).get('balance_change__sum') or 0

    def final_balance(self):
        if self.network == ETH:
            address = self.derive_ethereum_address()
            try:
                eth_balance = AccountBalance.objects.get(
                    network=ETH,
                    address=address,
                    identifier=address,
                    balance_type='R'
                ).balance
            except AccountBalance.DoesNotExist:
                logger.error('Account.final_balance: no eth account balance found for %s', address)
                eth_balance = 0

            return eth_balance

        return (BalanceChange.objects
                .filter(account=self)
                .aggregate(models.Sum('amount'))
                .get('amount__sum') or 0)

    def block_explorer_link(self):
        return 'https://www.blockchain.com/{}/xpub/{}'.format(self.network.lower(), self.xpub)

    def get_account_address(self):
        if self.network == ETH:
            address = self.derive_ethereum_address()
        elif self.network in (ATOM, BNB, XRP, EOS, FIO, RUNE, KAVA, SCRT, OSMO):
            address = self.xpub  # Cosmos/Binance account and address are the same
        else:
            assert False, 'Network must be ETH, ATOM, BNB, EOS, FIO, RUNE, KAVA, SCRT, OSMO'

        address_object, created = Address.objects.get_or_create(
            address=address,
            account=self,
            defaults={
                "type": Address.RECEIVE,
                "relpath": '0/0',
                "index": 0
            }
        )
        return address_object

    def get_change_address(self):
        addrs = self.get_addresses().filter(
            type=Address.CHANGE,
            balancechange__isnull=True
        ).order_by('index')

        if not len(addrs):
            # Need to derive more addresses
            max_index = self.get_addresses().filter(type=Address.CHANGE).aggregate(models.Max('index'))[
                            'index__max'] or 0

            self.sync(_async=False, start_index=max_index)

            addrs = self.get_addresses().filter(
                type=Address.CHANGE,
                balancechange__isnull=True
            ).order_by('index')

            if not len(addrs):
                raise ValueError('Not Enough Addresses')

        return addrs[0]

    def get_receive_addresses(self, count=1):
        if self.network in (ETH, ATOM, BNB, XRP, EOS, FIO, RUNE):
            return [self.get_account_address()]

        addrs = self.get_addresses().filter(
            type=Address.RECEIVE,
            balancechange__isnull=True
        ).order_by('index')

        count = max(count, 1)

        if len(addrs) < count:
            # Need to derive more addresses
            max_index = self.get_addresses().filter(type=Address.RECEIVE).aggregate(models.Max('index'))[
                            'index__max'] or 0

            self.sync(_async=False, start_index=max_index)

            addrs = self.get_addresses().filter(
                type=Address.RECEIVE,
                balancechange__isnull=True
            ).order_by('index')

            if len(addrs) < count:
                raise ValueError('Not Enough Addresses')

        return addrs[:count]

    def get_utxos(self, account_address_n):
        # TODO: Track utxos in db to save a network request to coinquery
        addresses = self.get_addresses_with_balance()
        coinquery = get_coinquery_client(self.network)
        utxos = coinquery.get_utxos_for_addresses([obj.address for obj in addresses])

        # Clean up after our change address selection bug.
        # See: https://www.reddit.com/r/TREZOR/comments/czo3yo/change_address_issue/
        change_index = self.get_change_address().index

        for i, utxo in enumerate(utxos):
            utxo_address = addresses.filter(address=utxo['address']).first()
            utxos[i]['address_n'] = utxo_address.get_address_n(account_address_n)
            utxos[i]['script_type'] = self.script_type
            utxos[i]['spend_required'] = (utxo_address.type == Address.CHANGE and utxo_address.index > change_index)

        return utxos


class Address(models.Model):
    RECEIVE = 'receive'
    CHANGE = 'change'

    ADDRESS_TYPES = (
        (RECEIVE, 'Receive'),
        (CHANGE, 'Change')
    )

    address = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=ADDRESS_TYPES)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    relpath = models.CharField(max_length=100)
    index = models.IntegerField()

    class Meta:
        # prevent upsert datarace
        unique_together = ('address', 'account')

    def __str__(self):
        return '<Address: {}>'.format(self.address)

    def get_address_n(self, account_address_n):
        change = 1 if self.type == self.CHANGE else 0
        address_index = self.index
        return account_address_n + [change, address_index]

    def get_balance(self):
        balance = BalanceChange.objects.filter(
            address=self,
            transaction__is_erc20_token_transfer=False
        ).aggregate(
            models.Sum('amount')
        ).get('amount__sum')

        return balance

    def get_erc20_contract_balance(self, contract_address):
        balance = BalanceChange.objects.filter(
            address=self,
            transaction__erc20_token__contract_address__iexact=contract_address
        ).aggregate(
            models.Sum('amount')
        ).get('amount__sum') or 0

        return balance


class ERC20Token(models.Model):
    contract_address = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    symbol = models.CharField(max_length=100, null=True, blank=True)
    precision = models.IntegerField()
    supported = models.BooleanField(default=False)

    def get_symbol(self):
        return self.symbol if self.symbol else self.contract_address

    @classmethod
    def lookup_contract_address(cls, token):
        token_object = ERC20Token.objects.filter(symbol__iexact=token).first()  # case-insensitive
        if not token_object:
            raise Exception('Unable to find {} contract address.'.format(token))
        return token_object.contract_address

    @classmethod
    def get_or_none(cls, contract_address):
        try:
            return cls.objects.get(contract_address=contract_address.lower())
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_create(cls, contract_address):
        token = cls.get_or_none(contract_address)
        if token:
            return token

        address = web3.toChecksumAddress(contract_address)
        contract = web3.eth.contract(address=address, abi=ERC20_ABI)
        name = contract.functions.name().call()
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()

        token = ERC20Token(
            contract_address=contract_address.lower(),
            name=name,
            symbol=symbol,
            precision=decimals)

        token.save()
        logger.info('saved new ERC20Token with contract address %s', contract_address.lower())

        return token


class Transaction(models.Model):
    txid = models.CharField(max_length=500)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    block_height = models.IntegerField(null=True)
    block_hash = models.CharField(max_length=500, null=True)
    block_time = models.DateTimeField(null=True)
    raw = models.TextField()

    # Ethereum-related fields
    is_erc20_token_transfer = models.BooleanField(default=False)
    erc20_token = models.ForeignKey(ERC20Token, null=True, on_delete=models.CASCADE)
    is_erc20_fee = models.BooleanField(default=False)
    is_dex_trade = models.BooleanField(default=False)
    success = models.BooleanField(default=True)
    thor_memo = models.CharField(max_length=500, null=True)
    fee = models.CharField(max_length=500, null=True)

    # eos tx types

    # fio tx types

    def __str__(self):
        # TODO add tx type*
        return '<Transaction: {}>'.format(self.txid)

    def balance_change(self):
        return BalanceChange.objects.filter(
            transaction=self,
            account=self.account
        ).aggregate(models.Sum('amount')).get('amount__sum') or 0

    def status(self):
        if self.block_time:
            return 'confirmed'
        return 'pending'

    def type(self):
        balance_change = self.balance_change()
        if self.is_erc20_fee:
            return 'fee'
        elif balance_change > 0:
            return 'receive'
        else:
            return 'send'

    def has_valid_block_height(self):
        return isinstance(self.block_height, int) and self.block_height is not 0

    def confirmations(self):
        if not self.has_valid_block_height():
            return None

        latest_height = get_latest_block_height(self.account.network)
        return latest_height + 1 - self.block_height

    def get_network(self):
        if self.is_erc20_token_transfer:
            return self.erc20_token.get_symbol()
        else:
            return self.account.network


class BalanceChange(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=78, decimal_places=0)

    def __str__(self):
        return '<BalanceChange: {}{} sats to {}>'.format('-' if self.amount < 0 else '+', self.amount,
                                                         self.address.address)  # noqa


class ProcessedBlock(models.Model):
    network = models.CharField(max_length=100, choices=SUPPORTED_NETWORK_CHOICES)
    block_height = models.IntegerField()
    block_hash = models.CharField(max_length=500)
    block_time = models.DateTimeField()
    processed_at = models.DateTimeField(auto_now_add=True)
    previous_hash = models.CharField(max_length=500)
    previous_block = models.ForeignKey('ProcessedBlock', on_delete=models.SET_NULL, null=True, blank=True)  # noqa
    is_orphaned = models.BooleanField(default=False)
    height_idx = models.Index(fields=['network', 'block_height'], name='processedblock_height_idx')

    class Meta:
        unique_together = ('network', 'block_hash')
        index_together = ('network', 'block_height')

    @classmethod
    def get_or_none(cls, block_hash, network):
        try:
            return cls.objects.get(block_hash=block_hash, network=network)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_create(cls, block_hash, network):
        existing = cls.get_or_none(block_hash, network)
        if existing:
            return existing

        block = get_coinquery_client(network).get_block_by_hash(block_hash)
        block_height = block.get('height')
        block_time = datetime.fromtimestamp(block.get('time'), timezone.utc)
        previous_block_hash = block.get('previousblockhash')
        previous_block = cls.get_or_none(previous_block_hash, network)

        obj = cls(
            network=network,
            block_height=block_height,
            block_hash=block_hash,
            block_time=block_time,
            previous_hash=previous_block_hash,
            previous_block=previous_block
        )
        obj.save()
        return obj

    @classmethod
    def latest(cls, network, include_orphans=False):
        blocks = cls.objects.filter(network=network)
        if not include_orphans:
            blocks = blocks.filter(is_orphaned=False)
        return blocks.order_by('-block_height').first()

    # removes all balance changes and transactions that were a result of an orphaned block
    def cleanUpOrphans(block_id):

        logger.debug('cleaning up orphans')

        clean_all_balances_query = """
            DELETE FROM tracker_balancechange USING tracker_transaction, tracker_processedblock
            WHERE
            tracker_transaction.id = tracker_balancechange.transaction_id
            AND
            tracker_transaction.block_hash = tracker_processedblock.block_hash
            AND
            tracker_processedblock.is_orphaned = True
            AND
            tracker_processedblock.id = {block_id};
        """

        formattted_clean_all_balances_query = clean_all_balances_query.format(block_id=block_id)

        clean_all_transactions_query = """
            DELETE FROM tracker_transaction USING tracker_processedblock
            WHERE
            tracker_transaction.block_hash = tracker_processedblock.block_hash
            AND
            tracker_processedblock.is_orphaned = True
            AND
            tracker_processedblock.id = {block_id};
        """

        formattted_clean_all_transactions_query = clean_all_transactions_query.format(block_id=block_id)

        with connection.cursor() as cursor:
            cursor.execute(formattted_clean_all_balances_query)
            cursor.execute(formattted_clean_all_transactions_query)

    @classmethod
    def invalidate_orphans(cls, network):
        latest = cls.latest(network)
        if not latest:
            return

        current = latest
        while isinstance(current, ProcessedBlock):
            block = get_coinquery_client(network).get_block_by_hash(current.block_hash)

            if block.get('confirmations') < 0:
                logger.info('detected orphaned %s block %s', network, current.block_hash)

                # mark orphan
                current.is_orphaned = True
                current.save()

                # clean up transaction and balance changes from orphaned blocks
                cls.cleanUpOrphans(current.id)

                current = cls.get_or_none(current.previous_hash, network)
            else:
                break


class ChainHeight(models.Model):
    network = models.CharField(max_length=100)
    height = models.IntegerField()

    class Meta:
        managed = False


class AccountBalance(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    network = models.CharField(max_length=100, choices=SUPPORTED_NETWORK_CHOICES)
    symbol = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255)  # same as address for ETH account, Token contract address for ERC20s
    balance_type = models.CharField(max_length=10, default="R")  # for delegated, unbonding
    balance = models.DecimalField(max_digits=78, decimal_places=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('network', 'address', 'identifier', 'balance_type')
