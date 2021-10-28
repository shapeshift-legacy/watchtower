#!/usr/bin/env python
"""
Rabbit Logger is a script that connects to the local RabbitMQ server and and 
prints each message published to exchange `<exchange>`.  For Watchtower, this
is typically `exchange.watchtower.txs` or `exchange.watchtower.blocks`

```
`python3 utils/rabbit-logger.py <exchange>`
```
"""

import pika
import pprint
import json
import time
import sys
import os
import environ

# get environment variables
env = environ.Env()
try:
    env.read_env('./.env')
except Exception as e:
    print('Error reading environment variables, {}'.format(e))
    exit()

pp = pprint.PrettyPrinter(indent=4)

# RabbitMQ configuration
EXCHANGE = sys.argv[1]
QUEUE = 'queue.logger-' + EXCHANGE

heartbeat_interval = 10
credentials = pika.PlainCredentials(env('RABBIT_USER'), env('RABBIT_PASS'))
parameters = pika.ConnectionParameters(
    env('RABBIT_HOST'),
    env('RABBIT_PORT'),
    env('RABBIT_VHOST'),
    credentials,
    heartbeat_interval=heartbeat_interval
)

# Connect to RabbitMQ
connection = None
while connection is None:
    try:
        print("Connecting to rabbitmq \n host: {} \n exchange: {} \n queue: {}".format(env('RABBIT_HOST'), EXCHANGE, QUEUE))
        connection = pika.BlockingConnection(parameters)
    except Exception as e:
        print("Connection failed, {} \n trying again ...".format(e))
        time.sleep(5)

channel = connection.channel()
channel.queue_declare(queue=QUEUE)
channel.queue_bind(exchange=EXCHANGE, queue=QUEUE)

# Log any messages received
def callback(ch, deliver, properties, body):
    print(" [x] Message Received:")
    message_formatted = json.loads(body)
    pp.pprint(message_formatted)
    ch.basic_ack(deliver.delivery_tag)

#pika 1.0.0
#channel.basic_consume(on_message_callback=callback, queue=QUEUE)
#pika 0.13.0
channel.basic_consume(callback, queue=QUEUE)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()
