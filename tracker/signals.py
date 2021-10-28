import os
import json

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver

from tracker.models import Account, Address
from common.services.rabbitmq import RabbitConnection, EXCHANGE_UNCHAINED
from common.services.launchdarkly import is_feature_enabled, UNCHAINED_REGISTRY

host = os.environ.get('UNCHAINED_RABBIT_HOST')
port = os.environ.get('UNCHAINED_RABBIT_PORT')
user = os.environ.get('UNCHAINED_RABBIT_USER')
password = os.environ.get('UNCHAINED_RABBIT_PASS')

is_enabled = is_feature_enabled(UNCHAINED_REGISTRY) and os.environ.get('UNCHAINED_RABBIT_ENABLED').lower() == 'true'


class ConnectionError(Exception):
    pass


def should_migrate(account):
    is_supported = _network_to_name(account.network) is not None
    return account.migrated is False and is_enabled and is_supported


def _network_to_name(network):
    network_lookup = {
        'ETH': "ethereum"
    }

    return network_lookup.get(network)


@receiver(pre_delete, sender=Account)
def check_unregister_account(sender, instance, **kwargs):
    if is_enabled is False:
        return

    name = _network_to_name(instance.network)
    if name is None:
        return

    rabbit = RabbitConnection(host, port, user, password)
    if rabbit._connection and rabbit._connection.is_open is True:
        return

    raise ConnectionError("unable to connect to rabbitmq at {}:{}".format(host, port))


@receiver(post_delete, sender=Account)
def unregister_account(sender, instance, **kwargs):
    if is_enabled is False:
        return

    name = _network_to_name(instance.network)
    if name is None:
        return

    msg = {
        'action': 'unregister',
        'client_id': 'axiom',
        'watchtower_meta': {
            'tracker_account_id': instance.id
        },
        'registration': {
            'pubkey': instance.xpub
        }
    }

    RabbitConnection(host, port, user, password).publish(
        exchange=EXCHANGE_UNCHAINED,
        routing_key='{}.registry'.format(name),
        message_type='unchained.registry',
        body=json.dumps(msg)
    )


@receiver(pre_save, sender=Address)
def check_register_address(sender, instance, **kwargs):
    if is_enabled is False:
        return

    name = _network_to_name(instance.account.network)
    if name is None:
        return

    rabbit = RabbitConnection(host, port, user, password)
    if rabbit._connection and rabbit._connection.is_open is True:
        return

    raise ConnectionError("unable to connect to rabbitmq at {}:{}".format(host, port))


@receiver(post_save, sender=Address)
def register_address(sender, instance, created, **kwargs):
    if is_enabled is False:
        return

    name = _network_to_name(instance.account.network)
    if name is None:
        return

    instance.account.migrated = True
    instance.account.save()

    msg = {
        'action': 'register',
        'client_id': 'axiom',
        'watchtower_meta': {
            'tracker_account_id': instance.account.id,
            'tracker_address_ids': {instance.address: instance.id}
        },
        'registration': {
            'addresses': [instance.address],
            'pubkey': instance.account.xpub
        }
    }

    RabbitConnection(host, port, user, password).publish(
        exchange=EXCHANGE_UNCHAINED,
        routing_key='{}.registry'.format(name),
        message_type='unchained.registry',
        body=json.dumps(msg)
    )


@receiver(pre_delete, sender=Address)
def check_unregister_address(sender, instance, **kwargs):
    if is_enabled is False:
        return

    name = _network_to_name(instance.account.network)
    if name is None:
        return

    rabbit = RabbitConnection(host, port, user, password)
    if rabbit._connection and rabbit._connection.is_open is True:
        return

    raise ConnectionError("unable to connect to rabbitmq at {}:{}".format(host, port))


@receiver(post_delete, sender=Address)
def unregister_address(sender, instance, **kwargs):
    if is_enabled is False:
        return

    name = _network_to_name(instance.account.network)
    if name is None:
        return

    msg = {
        'action': 'unregister',
        'client_id': 'axiom',
        'watchtower_meta': {
            'tracker_account_id': instance.account.id,
            'tracker_address_ids': {instance.address: instance.id}
        },
        'registration': {
            'addresses': [instance.address],
            'pubkey': instance.account.xpub
        }
    }

    RabbitConnection(host, port, user, password).publish(
        exchange=EXCHANGE_UNCHAINED,
        routing_key='{}.registry'.format(name),
        message_type='unchained.registry',
        body=json.dumps(msg)
    )
