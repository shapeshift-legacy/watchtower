from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from tracker.models import Account, Address, Transaction, BalanceChange, ProcessedBlock, ERC20Token


class AddressInline(admin.TabularInline):
    model = Address
    fields = (
        'address',
        'type',
        'relpath',
        'index',
        'balance'
    )
    readonly_fields = fields
    can_delete = False
    extra = 0
    show_change_link = True

    def has_add_permission(self, request):
        return False

    def balance(self, obj):
        sats = BalanceChange.objects.filter(address=obj).aggregate(Sum('amount')).get('amount__sum') or 0  # noqa
        balance_str = '{0:.8f} BTC'.format(sats / (10 ** 8))
        if sats > 0:
            return format_html(
                '<span style="color: #28a745;">{balance}</span>',
                balance=balance_str
            )
        elif sats < 0:
            return format_html(
                '<span style="color: red;">{balance}</span>',
                balance=balance_str
            )
        else:
            return balance_str

    balance.allow_tags = True


class XpubTransactionInline(admin.TabularInline):
    model = Transaction
    fields = (
        'txid',
        'block_time',
        'balance_change',
    )
    readonly_fields = fields
    can_delete = False
    extra = 0
    show_change_link = True
    ordering = ('-block_time',)

    def has_add_permission(self, request):
        return False

    def balance_change(self, obj):
        sats = BalanceChange.objects.filter(transaction=obj, account=obj.account).aggregate(Sum('amount')).get('amount__sum') or 0  # noqa
        balance_str = '{0:.8f} BTC'.format(sats / (10 ** 8))
        if sats > 0:
            return format_html(
                '<span style="color: #28a745;">+{balance}</span>',
                balance=balance_str
            )
        elif sats < 0:
            return format_html(
                '<span style="color: red;">{balance}</span>',
                balance=balance_str
            )
        else:
            return balance_str

    balance_change.allow_tags = True


class AddressBalanceChangeInline(admin.TabularInline):
    model = BalanceChange
    fields = (
        'transaction',
        'change',
    )
    readonly_fields = fields
    can_delete = False
    extra = 0
    show_change_link = True
    ordering = ()

    def has_add_permission(self, request):
        return False

    def change(self, obj):
        if obj.amount is None:
            return 'n/a'
        balance_str = '{0:.8f} BTC'.format(obj.amount / (10 ** 8))
        if obj.amount > 0:
            return format_html(
                '<span style="color: #28a745;">+{balance}</span>',
                balance=balance_str
            )
        elif obj.amount < 0:
            return format_html(
                '<span style="color: red;">{balance}</span>',
                balance=balance_str
            )
        else:
            return balance_str


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        'xpub',
        'network',
        'transactions_count',
        'total_received',
        'final_balance',
        'block_explorer',
        'registered_at',
        'updated_at'
    )
    list_filter = (
        'network',
    )
    list_select_related = ()
    readonly_fields = (
        'xpub',
        'network',
        'transactions_count',
        'total_received',
        'final_balance',
        'block_explorer',
        'registered_at',
        'updated_at'
    )
    search_fields = [
        'xpub',
        'network',
    ]
    inlines = [XpubTransactionInline, AddressInline]

    def transactions(self, obj):
        count = Transaction.objects.filter(account=obj).count()
        received = BalanceChange.objects.filter(account=obj, amount__gt=0).aggregate(Sum('amount')).get('amount__sum') or 0  # noqa
        balance = BalanceChange.objects.filter(account=obj, amount__gt=0).aggregate(Sum('amount')).get('amount__sum') or 0  # noqa

        html = '<table><tbody>'
        html += '<tr><td>No. Transactions</td><td>{}</td></tr>'.format(count)
        html += '<tr><td>Total Received</td><td>{}</td></tr>'.format(received)
        html += '<tr><td>Final Balance</td><td>{}</td></tr>'.format(balance)
        html += '</tbody></table>'

        return format_html(html)

    def transactions_count(self, obj):
        return obj.transactions_count()

    def total_received(self, obj):
        sats = obj.total_received()
        balance_str = '{0:.8f} BTC'.format(sats / (10 ** 8))
        return balance_str

    def final_balance(self, obj):
        sats = obj.final_balance()
        balance_str = '{0:.8f} BTC'.format(sats / (10 ** 8))
        return balance_str

    def block_explorer(self, obj):
        return format_html(
            '<a href="{link}" target="_blank">{link}</a>',  # noqa
            link=obj.block_explorer_link()
        )

    transactions_count.short_description = 'No. Transactions'
    block_explorer.allow_tags = True


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    model = Transaction


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        'address',
        'network',
        'type',
        'relpath',
        'index',
        'total_received',
        'final_balance',
        'block_explorer'
    )
    list_filter = (
        'account__network',
        'type',
    )
    list_select_related = ()
    readonly_fields = (
        'address',
        'type',
        'account',
        'relpath',
        'index',
        'total_received',
        'final_balance',
        'block_explorer'
    )
    search_fields = [
        'address'
    ]
    inlines = [AddressBalanceChangeInline]

    def total_received(self, obj):
        sats = BalanceChange.objects.filter(address=obj, amount__gt=0).aggregate(Sum('amount')).get('amount__sum') or 0  # noqa
        balance_str = '{0:.8f} BTC'.format(sats / (10 ** 8))
        return balance_str

    def final_balance(self, obj):
        sats = BalanceChange.objects.filter(address=obj).aggregate(Sum('amount')).get('amount__sum') or 0  # noqa
        balance_str = '{0:.8f} BTC'.format(sats / (10 ** 8))
        return balance_str

    def network(self, obj):
        return obj.account.network

    def block_explorer(self, obj):
        return format_html(
            '<a href="https://www.blockchain.com/btc/address/{address}" target="_blank">https://www.blockchain.com/btc/address/{address}</a>',  # noqa
            address=obj.address
        )

    block_explorer.allow_tags = True


@admin.register(ProcessedBlock)
class ProcessedBlockAdmin(admin.ModelAdmin):
    ordering = ('-block_height', '-block_time')
    list_display = (
        'block_height',
        'network',
        'block_time',
        'processed_at',
        'block_hash',
        'is_orphaned',
    )
    list_filter = (
        'network',
        'is_orphaned',
    )
    list_select_related = ()
    readonly_fields = (
        'network',
    )
    search_fields = [
        'network',
        'block_hash',
    ]
    inlines = []


@admin.register(ERC20Token)
class ERC20TokenAdmin(admin.ModelAdmin):
    ordering = ['symbol']
    list_display = (
        'symbol',
        'name',
        'contract_address',
        'precision'
    )
    list_filter = (
        'precision',
    )
    list_select_related = ()
    readonly_fields = (
        'symbol',
        'name',
        'contract_address',
        'precision'
    )
    search_fields = [
        'symbol',
        'name',
        'contract_address',
        'precision'
    ]
    inlines = []
