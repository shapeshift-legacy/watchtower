"""
Helpful resources:

https://github.com/bitpay/bitcore-wallet-service/blob/master/lib/model/txproposal.js
https://github.com/shapeshift-legacy/typescript-wallet/blob/master/src/modules/keepkeyjs/services/FeeService/bitcoin-fee-service.ts
"""
from common.utils.networks import BTC, BCH, LTC, DOGE, DASH, ETH, DGB
from common.utils.bitcoin_node import get_cached_bitcoin_fees, MIN_RELAY_FEE as btc_min_relay_fee

FEE_PER_KB = 'FEE_PER_KB'       # satoshis
INPUT_SIZE = 'INPUT_SIZE'       # bytes
OUTPUT_SIZE = 'OUTPUT_SIZE'     # bytes
OVERHEAD_SIZE = 'OVERHEAD_SIZE' # bytes
MIN_RELAY_FEE = 'MIN_RELAY_FEE' # satoshis per kilobyte

DEFAULT_OVERHEAD_SIZE = sum([
    4,  # version
    4,  # locktime
    9,  # maximum allowed bytes for input count varint
    9,  # maximum allowed bytes for output count varint
])

'''
Minimum relay fee is the feerate for defining dust:
https://github.com/bitcoin/bitcoin/blob/c536dfbcb00fb15963bf5d507b7017c241718bf6/src/policy/policy.h#L50
https://github.com/litecoin-project/litecoin/blob/f22cd116c597213753b8cc77ff675ed5be18ec1d/src/policy/policy.h#L48

Doge is a special case, dust limit explicitly defined in the code, rather than a fee rate
https://github.com/dogecoin/dogecoin/blob/10a5e93a055ab5f239c5447a5fe05283af09e293/src/primitives/transaction.h#L151

'''
# Doge dust limit (units of dogetoshis)
DOGE_DUST_LIMIT = 100000000

# Calculate min relay fee in dogetoshis per kB.  Assume min tx size of 200 bytes
DOGE_MIN_RELAY_FEE = DOGE_DUST_LIMIT / 200 * 1024

DEFAULT_INPUT_SIZES = {
    'p2pkh': 147,
    'p2sh-p2wpkh': 91,
    'p2wpkh': 68
}

DEFAULT_OUTPUT_SIZES = {
    'p2pkh': 34,
    'p2sh': 32,
    'p2sh-p2wpkh': 32,
    'p2wpkh': 31
}

COIN_DEFAULTS = {
    BTC: {
        FEE_PER_KB: 50000,
        INPUT_SIZE: {
            'p2pkh': 149,
            'p2sh-p2wpkh': 91,
            'p2wpkh': 68
        },
        OUTPUT_SIZE: {
            'p2pkh': 34,
            'p2sh': 32,
            'p2sh-p2wpkh': 32,
            'p2wpkh': 31
        },
        OVERHEAD_SIZE: DEFAULT_OVERHEAD_SIZE,
        MIN_RELAY_FEE: btc_min_relay_fee
    },
    BCH: {
        FEE_PER_KB: 5000,
        INPUT_SIZE: {
            'p2pkh': 149,
        },
        OUTPUT_SIZE: {
            'p2pkh': 34,
            'p2sh': 32
        },
        OVERHEAD_SIZE: DEFAULT_OVERHEAD_SIZE,
        MIN_RELAY_FEE: 219
    },
    LTC: {
        FEE_PER_KB: 100000,
        INPUT_SIZE: {
            'p2pkh': 149,
            'p2sh-p2wpkh': 91,
            'p2wpkh': 68
        },
        OUTPUT_SIZE: {
            'p2pkh': 34,
            'p2sh': 32,
            'p2sh-p2wpkh': 32,
            'p2wpkh': 31
        },
        OVERHEAD_SIZE: DEFAULT_OVERHEAD_SIZE,
        MIN_RELAY_FEE: 3000
    },
    DOGE: {
        FEE_PER_KB: 500000000,
        INPUT_SIZE: {
            'p2pkh': 149,
        },
        OUTPUT_SIZE: {
            'p2pkh': 34,
            'p2sh': 32
        },
        OVERHEAD_SIZE: DEFAULT_OVERHEAD_SIZE,
        MIN_RELAY_FEE: DOGE_MIN_RELAY_FEE
    },
    DASH: {
        FEE_PER_KB: 5000,
        INPUT_SIZE: {
            'p2pkh': 149,
        },
        OUTPUT_SIZE: {
            'p2pkh': 34,
            'p2sh': 32
        },
        OVERHEAD_SIZE: DEFAULT_OVERHEAD_SIZE,
        MIN_RELAY_FEE: 1000
    },
    DGB: {
        FEE_PER_KB: 5000,
        INPUT_SIZE: {
            'p2pkh': 149,
        },
        OUTPUT_SIZE: {
            'p2pkh': 34,
            'p2sh': 32,
        },
        OVERHEAD_SIZE: DEFAULT_OVERHEAD_SIZE,
        MIN_RELAY_FEE: 1000,
    },
    ETH: {}
}

SMALLEST_VALUE_FIRST = 'SMALLEST_VALUE_FIRST'

UTXO_SELECTION_STRATEGIES = [
    SMALLEST_VALUE_FIRST,
]


class InvalidStrategy(Exception):
    def __init__(self):
        super().__init__('Invalid utxo selection strategy.')

class InsufficientFundsError(Exception):
    def __init__(self):
        super().__init__('Not enough funds.')

class NoSpendableUTXOsError(Exception):
    def __init__(self):
        super().__init__('No spendable UTXOs found.')

def create_unsigned_utxo_transaction(
    network,
    utxos,
    recipients,
    change_address,
    change_script_type,
    change_index,
    change_path,
    change_address_n,
    desired_conf_time,
    op_return_data,
    utxo_selection_strategy=SMALLEST_VALUE_FIRST
):
    fee_per_kb = get_fee_per_kb(network, desired_conf_time)
    dust_limit = get_dust_limit(network, change_script_type)

    # utxo selection
    selected_utxos, change_amount, fee = select_utxos(
        network,
        utxos,
        recipients,
        change_script_type,
        dust_limit,
        fee_per_kb,
        op_return_data,
        strategy=utxo_selection_strategy
    )

    # only add change output if the amount is greater than the fee incurred by adding it
    # (don't generate dust)
    if change_amount > dust_limit:
        assert change_address, 'We have change, but no change address.'
        recipients += [{
            'address': change_address,
            'script_type': change_script_type,
            'amount': change_amount
        }]

    # format inputs
    inputs = [{
        'txid': utxo['txid'],
        'vout': utxo['vout'],
        'address': utxo['address'],
        'script_type': utxo['script_type'],
        'amount': utxo['satoshis'],
        'confirmations': utxo.get('confirmations', None),
        'address_n': utxo['address_n']
    } for utxo in selected_utxos]

    # format outputs
    outputs = []
    for r in recipients:
        is_change = r['address'] == change_address
        output = {
            'address': r['address'],
            'amount': r['amount'],
            'is_change': is_change
        }
        if is_change:
            output.update({
                'index': change_index,
                'relpath': change_path,
                'script_type': change_script_type,
                'address_n': change_address_n
            })
        outputs.append(output)


    return {
        'inputs': inputs,
        'outputs': outputs,
        'fee': fee,
        'feePerKB': fee_per_kb
    }


def select_utxos(network, utxos, recipients, change_script_type, dust_limit, fee_per_kb, op_return_data, strategy=SMALLEST_VALUE_FIRST):
    if strategy == SMALLEST_VALUE_FIRST:
        return select_utxos_by_smallest_value_first(network, utxos, recipients, change_script_type, dust_limit, fee_per_kb, op_return_data)

    raise InvalidStrategy


def get_total_send_amount(recipients):
    return sum([(r.get('amount') or 0) for r in recipients])


def get_total_utxo_value(utxos):
    return sum([utxo['satoshis'] for utxo in utxos])


def select_utxos_by_smallest_value_first(network, utxos, recipients, change_script_type, dust_limit, fee_per_kb, op_return_data):
    # Sort by increasing value with 0-confirmation utxos at the end.
    sorted_utxos = sorted(utxos, key=lambda utxo: (not utxo['confirmations'], utxo['satoshis']))
    has_send_max = len([r for r in recipients if r.get('send_max', False)]) > 0
    total_send_amount = get_total_send_amount(recipients)

    # Clean up after our change index selection bug:
    #   https://www.reddit.com/r/TREZOR/comments/czo3yo/change_address_issue/
    # as well as the segwit-native account change bug.
    selected_utxos = [utxo for utxo in sorted_utxos if utxo['spend_required']]

    # Remove 'spend_required' utxos, since we've already selected them.
    sorted_utxos = [utxo for utxo in sorted_utxos if not utxo['spend_required']]

    total_utxo_value = 0
    for utxo in sorted_utxos:
        # Don't consume dust
        if utxo['satoshis'] <= dust_limit:
            continue

        selected_utxos.append(utxo)
        total_utxo_value = get_total_utxo_value(selected_utxos)

        estimated_fee = get_estimated_fee(network, selected_utxos, recipients, change_script_type, fee_per_kb, op_return_data)

        if has_send_max:
            continue

        minimum_utxo_value = total_send_amount + estimated_fee
        change_amount = total_utxo_value - minimum_utxo_value

        if total_utxo_value >= minimum_utxo_value:
            fee = total_utxo_value - total_send_amount - change_amount
            return selected_utxos, change_amount, fee

    if not len(selected_utxos):
        raise NoSpendableUTXOsError()

    total_utxo_value = get_total_utxo_value(selected_utxos)
    estimated_fee = get_estimated_fee(network, selected_utxos, recipients, change_script_type, fee_per_kb, op_return_data)
    max_val = total_utxo_value - total_send_amount - estimated_fee

    if has_send_max:
        if dust_limit < max_val:
            for r in recipients:
                if r['send_max']:
                    r['amount'] = max_val

            return selected_utxos, 0, estimated_fee
    else:
        minimum_utxo_value = total_send_amount + estimated_fee
        change_amount = total_utxo_value - minimum_utxo_value

        if total_utxo_value >= minimum_utxo_value:
            fee = total_utxo_value - total_send_amount - change_amount
            return selected_utxos, change_amount, fee

    ex = InsufficientFundsError()
    ex.estimated_fee = estimated_fee
    raise ex


def get_estimated_fee(network, inputs, outputs, change_script_type, fee_per_kb, op_return_data = None):
    if op_return_data is not None:
        op_return_bytes = len(op_return_data)
    else:
        op_return_bytes = 0

    estimated_vbytes = get_estimated_vbytes(network, inputs, outputs, change_script_type)
    estimated_fee = fee_per_kb * (estimated_vbytes + op_return_bytes) / 1024.0
    estimated_fee = round(estimated_fee)
    return estimated_fee


def get_estimated_vbytes(network, inputs, outputs, change_script_type):
    overhead = COIN_DEFAULTS.get(network, {}).get(OVERHEAD_SIZE, 4 + 4 + 1 + 1)
    estimated_vbytes = overhead

    input_sizes = COIN_DEFAULTS.get(network, {}).get(INPUT_SIZE, DEFAULT_INPUT_SIZES)
    output_sizes = COIN_DEFAULTS.get(network, {}).get(OUTPUT_SIZE, DEFAULT_OUTPUT_SIZES)

    for i in inputs:
        estimated_vbytes += input_sizes.get(i['script_type'], DEFAULT_INPUT_SIZES[i['script_type']])
    for o in outputs:
        estimated_vbytes += output_sizes.get('p2pkh', DEFAULT_OUTPUT_SIZES['p2pkh'])

    estimated_vbytes += output_sizes.get(change_script_type, DEFAULT_OUTPUT_SIZES[change_script_type])

    return estimated_vbytes


def get_fee_per_kb(network, desired_conf_time):
    if network not in COIN_DEFAULTS and FEE_PER_KB not in COIN_DEFAULTS.get(network):
        raise Exception('Missing fee/kb for {}.'.format(network))

    if network != 'BTC':
        return COIN_DEFAULTS[network][FEE_PER_KB]

    cached_fee = get_cached_bitcoin_fees()
    if cached_fee is None:
        return COIN_DEFAULTS[network][FEE_PER_KB]

    return cached_fee.get(desired_conf_time, {}).get('fee')

# dust limit is min size utxo that should be created or consumed
# if it costs more to send the utxo than its worth, it's considered dust
def get_dust_limit(network, change_script_type):
    if network not in COIN_DEFAULTS and OUTPUT_SIZE not in COIN_DEFAULTS.get(network):
        raise Exception('Missing output size for {}.'.format(network))

    # what to do here... pass script_type in to create_unsigned_utxo_transaction?
    input_size = COIN_DEFAULTS[network][INPUT_SIZE]['p2pkh']
    output_size = COIN_DEFAULTS[network][OUTPUT_SIZE][change_script_type]
    min_relay_fee = COIN_DEFAULTS[network][MIN_RELAY_FEE]
    return round((input_size + output_size) * min_relay_fee / 1024.0)

