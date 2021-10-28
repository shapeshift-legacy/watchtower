
import logging

logger = logging.getLogger('common.utils.cosmos')

def calculate_balance_change(address, transaction):
    balance_change = 0.0
    address_to = transaction.get('to')
    address_from = transaction.get('from')
    transfer_value = float(transaction['value'])

    is_send = address_from.lower() == address.lower()
    is_receive = address_to.lower() == address.lower()

    is_error = False #True if transaction.get('isError', '0') == '1' else False

    if is_receive and not is_error:
        balance_change += transfer_value

    if is_send and not is_error:
        balance_change -= transfer_value

    return balance_change