from rest_framework import serializers

from tracker.models import Account, Transaction, BalanceChange


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = (
            'xpub',
            'network',
            'final_balance',
            'total_received',
            'transactions_count',
            'registered_at',
        )


class TransactionSerializer(serializers.ModelSerializer):
    amount = serializers.IntegerField(source='balance_change')  # satoshis
    date = serializers.DateTimeField(source='block_time')
    network = serializers.CharField(source='get_network')
    xpub = serializers.CharField(source='account.xpub')
    addresses = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = (
            'txid',
            'status',
            'type',
            'amount',
            'date',
            'confirmations',
            'network',
            'xpub',
            'addresses'
        )

    def get_addresses(self, obj):
        return [{
            'address': bc['address__address'],
            'type': bc['address__type'],
            'amount': bc['amount']
        } for bc in BalanceChange.objects.filter(
            transaction=obj,
            xpub=obj.xpub
        ).values(
            'address__address',
            'address__type',
            'amount'
        )]
