#!/bin/env python3

import json
import requests
import sys
import time
import csv
import pika
import pprint
import os
from dotenv import load_dotenv

ETH = 'ETH'

usage = """
Usage:
    python3 register_xpub.py <filename>
Example:
    python3 register_xpub.py test_xpubs.json """

# get environment variables
try:
    load_dotenv()
except Exception as e:
    print('Error reading environment variables, {}'.format(e))
    exit()

# RabbitMQ configuration
EXCHANGE = 'exchange.platform.notifications'
QUEUE = 'queue.register-xpubs'
pp = pprint.PrettyPrinter(indent=4)

# global variables - bleh
xpub_iterator = 0
xpubs = []
xpub = {}
starting_balance = 0
success = 'false'


class WatchtowerErrorResponse(ValueError):
    pass


def connect_rabbit():
    print('Connecting to rabbit message queue...')
    heartbeat_interval = 10
    credentials = pika.PlainCredentials(os.getenv('RABBIT_USER'), os.getenv('RABBIT_PASS'))
    parameters = pika.ConnectionParameters(
        os.getenv('RABBIT_HOST'),
        os.getenv('RABBIT_PORT'),
        os.getenv('RABBIT_VHOST'),
        credentials,
        heartbeat_interval=heartbeat_interval
    )

    print('Connecting to rabbitmq \n host: {} \n exchange: {} \n queue: {}'.format(os.getenv('RABBIT_HOST'), EXCHANGE,
                                                                                   QUEUE))
    try:
        connection = pika.BlockingConnection(parameters)
    except Exception as e:
        print('Connection failed, {}'.format(e))
        exit()

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE)

    return channel, connection


def get_balance(xpub, wt_url_base):
    wt_api_balance = '/api/v1/balance'
    headers = {'Content-Type': 'application/json'}
    payload = {
        "data": [{
            "network": xpub['network'],
            "xpub": xpub['xpub'],
            "script_type": xpub['script_type']
        }]
    }

    wt_url = '{}{}'.format(wt_url_base, wt_api_balance)
    try:
        response = requests.post(wt_url, headers=headers, json=payload)
    except Exception:
        raise WatchtowerErrorResponse('Could not connect to Watchtower')

    if response.status_code is not 200:
        raise WatchtowerErrorResponse('Non-200 response from Watchtower: {}'.format(response))

    # get the response object
    res = json.loads(response.content.decode('utf-8'))

    if res is None:
        raise WatchtowerErrorResponse('Empty response object')
    if 'error' in res:
        raise WatchtowerErrorResponse('Unexpected error response {}'.format(res))
    if not res['data']:
        return 0

    # if network is Ethereum, parse out the ETH balance, ignore token balances
    if xpub['network'] is ETH:
        for balance_obj in res['data']:
            if balance_obj['network'] == ETH:
                return balance_obj['balance']

    # else this is a utxo coin with valid response
    return res['data'][0]['balance']


def register_xpub(xpub, wt_url_base):
    # Watchtower endpoint to register an xpub
    #   async=false : synchronous request
    #   hard_refresh=true : delete old data before re-syncing xpub
    register_async = 'true'
    register_hard_refresh = 'true'

    wt_api_register = '/api/v1/register?async={}&hard_refresh={}'.format(register_async, register_hard_refresh)
    headers = {'Content-Type': 'application/json'}
    payload = {
        "data": [{
            "network": xpub['network'],
            "xpub": xpub['xpub'],
            "script_type": xpub['script_type']
        }]
    }

    wt_url = '{}{}'.format(wt_url_base, wt_api_register)
    try:
        response = requests.post(wt_url, headers=headers, json=payload)
    except Exception:
        raise WatchtowerErrorResponse('Could not connect to Watchtower')

    if response.status_code is not 200:
        raise WatchtowerErrorResponse('Non-200 response from Watchtower: {}'.format(response))

    # get the response object
    res = json.loads(response.content.decode('utf-8'))

    if res is None:
        raise WatchtowerErrorResponse('Empty response object')
    if 'error' in res:
        raise WatchtowerErrorResponse('Unexpected error response {}'.format(res))
    if not res['data']:
        raise WatchtowerErrorResponse('Unexpected error response {}'.format(res))

    return res


def get_wt(wt_url, headers, payload):
    try:
        response = requests.post(wt_url, headers=headers, json=payload)

    except Exception:
        raise WatchtowerErrorResponse('Could not connect to Watchtower')

    if response.status_code is not 200:
        raise WatchtowerErrorResponse('Non-200 response from Watchtower: {}'.format(response))

    # get the response object
    res = json.loads(response.content.decode('utf-8'))

    if res is None:
        raise WatchtowerErrorResponse('Empty response object')
    if 'error' in res:
        raise WatchtowerErrorResponse('Unexpected error response {}'.format(res))
    if not res['data']:
        raise WatchtowerErrorResponse('Unexpected error response {}'.format(res))

    return res


def read_xpubs(xpubs_file):
    xpubs_json = json.load(open(xpubs_file))
    return xpubs_json


def register_xpubs_with_report(xpubs_file, wt_url_base, poll_sync_status, channel, connection):
    global xpubs
    global xpub
    global starting_balance
    global success
    use_rabbit = not poll_sync_status

    xpubs = read_xpubs(xpubs_file)
    xpubs_len = len(xpubs)
    starting_balance = 0
    ending_balance = 0
    current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())

    # make a csv file
    with open('{}_report_{}.csv'.format(xpubs_file.split('.json')[0], current_time), 'w', newline='') as file:
        writer = csv.writer(file, delimiter=',')
        writer.writerow(
            ['Index', 'Timestamp', 'Network', 'Xpub', 'Script Type', 'Register Successful', 'Balance Before',
             'Balance After'])

        xpub = xpubs[xpub_iterator]
        xpub['sync_status'] = ''

        # Log any messages received
        def on_message(ch, deliver, properties, body):
            global xpub_iterator
            global xpubs
            global xpub
            global starting_balance
            global success

            print('\n [x] Message Received:')
            message_formatted = json.loads(body)
            pp.pprint(message_formatted['data'])

            if message_formatted['data']['xpub'] != xpub['xpub']:
                print('xpub not from this list, skipping {}'.format(message_formatted['data']['xpub']))
                if use_rabbit:
                    ch.basic_ack(deliver.delivery_tag)
                return

            if message_formatted['data']['sync_status'] == 'syncing':
                print('xpub syncing {}'.format(message_formatted['data']['xpub']))
                if use_rabbit:
                    ch.basic_ack(deliver.delivery_tag)
                return

            print('Finished {} of {}'.format(xpub_iterator + 1, xpubs_len))
            if use_rabbit:
                ch.basic_ack(deliver.delivery_tag)

            try:
                ending_balance = get_balance(xpub, wt_url_base)
            except WatchtowerErrorResponse as e:
                ending_balance = 'error'
                print('Error retrieving balance: {}'.format(str(e)))

            # write xpub status to results file
            writer.writerow([xpub_iterator, time.asctime(), xpub['network'], xpub['xpub'], xpub['script_type'], success,
                             starting_balance, ending_balance])

            # get next xpub
            xpub_iterator = xpub_iterator + 1
            if xpub_iterator >= xpubs_len:
                print('\nFinished registering all XPubs!')
                if use_rabbit:
                    close_rabbit(channel, connection)
                else:
                    exit()

            # register next xpub
            xpub = xpubs[xpub_iterator]
            success = 'false'  # default

            try:
                starting_balance = get_balance(xpub, wt_url_base)
            except WatchtowerErrorResponse as e:
                starting_balance = 'error'
                print('Error retrieving balance: {}'.format(str(e)))

            try:
                res = register_xpub(xpub, wt_url_base)
                success = 'true'
            except WatchtowerErrorResponse as e:
                success = 'false'
                print('Error invalid reponse: {}'.format(str(e)))
            return

        # rabbit new message callback
        if use_rabbit:
            channel.basic_consume(on_message, queue=QUEUE)

        # register first xpub
        xpub = xpubs[xpub_iterator]
        success = 'false'  # default

        try:
            starting_balance = get_balance(xpub, wt_url_base)
        except WatchtowerErrorResponse as e:
            starting_balance = 'error'
            print('Error retrieving balance: {}'.format(str(e)))

        try:
            res = register_xpub(xpub, wt_url_base)
            success = 'true'
        except WatchtowerErrorResponse as e:
            success = 'false'
            print('Error invalid reponse: {}'.format(str(e)))

        if use_rabbit:
            try:
                channel.start_consuming()
            except KeyboardInterrupt:
                close_rabbit(channel, connection)

        else:
            while True:
                # poll sync status
                # when complete call on_message()
                try:
                    xpub = wait_for_sync_complete(xpub, wt_url_base)
                    message = {
                        "data": xpub
                    }
                    success = 'true'
                    on_message(ch=None, deliver=None, properties=None, body=json.dumps(message))
                except WatchtowerErrorResponse as e:
                    success = 'false'
                    print('Error invalid reponse: {}'.format(str(e)))
    return None


def wait_for_sync_complete(xpub, wt_url_base):
    wait_small = 2  # seconds
    wait_large = 10  # seconds
    max_wait = 10 * 60  # seconds
    total_wait = 0  # seconds

    wt_api_balance = '/api/v1/xpubs'
    headers = {'Content-Type': 'application/json'}
    payload = {
        "data": [{
            "network": xpub['network'],
            "xpub": xpub['xpub'],
            "script_type": xpub['script_type']
        }]
    }

    wt_url = '{}{}'.format(wt_url_base, wt_api_balance)
    print('\n [*] Syncing XPub:')
    pp.pprint(payload['data'][0])

    while (total_wait < max_wait):
        print(". ", end='')
        wait_secs = wait_small if total_wait < 10 else wait_large  # backoff
        time.sleep(wait_secs)
        total_wait = total_wait + wait_secs
        res = get_wt(wt_url, headers, payload)
        # print(res)
        if res['data'][0]['sync_status'] == 'COMPLETE':
            # xpub['sync_status'] = 'complete'
            return res['data'][0]  # xpub 

    xpub['sync_status'] = 'timeout-error'
    return xpub


def close_rabbit(channel, connection):
    print('Closing rabbit channel ...')
    channel.stop_consuming()
    print('Closing rabbit connection ...\n')
    connection.close()


# main
def main():
    if len(sys.argv) < 1:
        print('Error: Missing argument')
        print(usage)
        return

    xpubs_file = sys.argv[1]
    wt_url_base = os.getenv('WATCHTOWER_URL')
    print('Registering XPubs to watchtower: {}'.format(wt_url_base))

    try:
        if (os.getenv('POLL_SYNC_STATUS') == 'false'):
            channel, connection = connect_rabbit()
            register_xpubs_with_report(
                xpubs_file=xpubs_file,
                wt_url_base=wt_url_base,
                poll_sync_status=False,
                channel=channel,
                connection=connection
            )
        else:
            register_xpubs_with_report(
                xpubs_file=xpubs_file,
                wt_url_base=wt_url_base,
                poll_sync_status=True,
                channel=None,
                connection=None
            )
    except Exception as e:
        print('Error registering XPubs: {}'.format(e))


if __name__ == '__main__':
    main()
