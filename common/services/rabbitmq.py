import pika
import os
import time
import logging
import uuid

from threading import Lock

# RabbitMQ configuration
EXCHANGE_TXS = 'exchange.watchtower.txs'
EXCHANGE_BLOCKS = 'exchange.watchtower.blocks'
EXCHANGE_NOTIFICATIONS = 'exchange.platform.notifications'
EXCHANGE_UNCHAINED = 'exchange.unchained'
QUEUE_WATCHTOWER_TX_BACKFILL = 'queue.watchtower.tx.backfill'
MAX_RETRIES = int(os.getenv('RABBIT_MAX_RETRIES', 5))
TIMEOUT = int(os.getenv('RABBIT_RETRY_TIMEOUT', 3))

logger = logging.getLogger('watchtower.rabbitmq')
mutex = Lock()


class RabbitConnection:
    _host = None
    _port = None
    _user = None
    _password = None
    _connection = None
    _channel = None

    def __init__(self, host=None, port=None, user=None, password=None):
        self._host = os.environ.get('RABBIT_HOST') if host is None else host
        self._port = os.environ.get('RABBIT_PORT') if port is None else port
        self._user = os.environ.get('RABBIT_USER') if user is None else user
        self._password = os.environ.get('RABBIT_PASS') if password is None else password


        retries = 0
        while self._connection is None or not self._connection.is_open:
            try:
                # establish connection and declare exchanges
                self._establish_connection()
                self._channel = self._connection.channel()
                self._channel.exchange_declare(exchange=EXCHANGE_TXS, exchange_type='fanout')
                self._channel.exchange_declare(exchange=EXCHANGE_BLOCKS, exchange_type='fanout')
                self._channel.exchange_declare(exchange=EXCHANGE_NOTIFICATIONS, exchange_type='fanout')
                self._channel.exchange_declare(exchange=EXCHANGE_UNCHAINED, exchange_type='topic', durable=True)
                self._channel.queue_declare(queue=QUEUE_WATCHTOWER_TX_BACKFILL, durable=True)

            except Exception as e:
                # Give up if we are over the max number of retries
                if retries > MAX_RETRIES:
                    logger.error("Max RabbitMQ retries exceeded. No connection was established, %s", e)
                    self._connection = None
                    self._channel = None
                    return

                retries += 1

                logger.info("Unable to connect to rabbitMQ, Retrying...")
                time.sleep(TIMEOUT)

    def _establish_connection(self):
        mutex.acquire()
        logging.getLogger('pika').setLevel(logging.WARNING)

        try:
            vhost = os.environ.get('RABBIT_VHOST')
            heartbeat_interval = 10
            credentials = pika.PlainCredentials(self._user, self._password)
            parameters = pika.ConnectionParameters(
                self._host,
                self._port,
                vhost,
                credentials,
                heartbeat_interval=heartbeat_interval
            )

            # attempt to gracefully close any dangling connection
            try:
                if self._connection:
                    self._connection.close()
            except Exception:
                pass

            self._connection = pika.BlockingConnection(parameters)
        finally:
            mutex.release()

    def get_channel(self):
        return self._channel

    def publish(self, exchange=None, routing_key=None, message_type=None, body=None):
        mutex.acquire()

        headers = {
            "levelOneRetryCount": 0,
            "levelTwoRetryCount": 0,
            "saveAudit": False
        }
        properties = pika.BasicProperties(type=message_type, correlation_id=str(uuid.uuid4()), headers=headers)


        try:
            if self._connection is None or self._channel is None:
                logger.info("No rabbit connection available, Dropping message... %s", body)
                return

            # attempt to reopen connection if closed
            if not self._connection.is_open:
                try:
                    self._establish_connection()
                except Exception as e:
                    logger.error("Rabbit connection was closed, Dropping message... %s, %s", body, e)
                    return

            # attempt to reopen channel if closed
            if not self._channel.is_open:
                try:
                    self._channel = self._connection.channel()
                    self._channel.exchange_declare(exchange=exchange, exchange_type='fanout')
                except Exception as e:
                    logger.error("Rabbit channel was closed, Dropping message... %s, %s", body, e)
                    return

            try:
                self._channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    properties=properties,
                    body=body
                )
                self._connection.close()
            except Exception as e:
                logger.exception('Error publishing to exchange %s, routing_key %s', exchange, routing_key)
                logger.error("Failed to publish message to rabbit... %s, %s", body, e)
                return
        finally:
            mutex.release()

    def consume(self, consumer_callback=None, queue=None, no_ack=False, exclusive=False, consumer_tag=None, 
                arguments=None):
        mutex.acquire()

        try:
            if self._connection is None or self._channel is None:
                logger.info("No rabbit connection available, Unable to consume messages on queue... %s", queue)
                return

            # attempt to reopen connection if closed
            if not self._connection.is_open:
                try:
                    self._establish_connection()
                except Exception as e:
                    logger.error("Rabbit connection was closed, Unable to consume messages on queue... %s, %s", queue, e)
                    return

            # attempt to reopen channel if closed
            if not self._channel.is_open:
                try:
                    self._channel = self._connection.channel()
                    self._channel.queue_declare(queue=queue)
                except Exception as e:
                    logger.error("Rabbit channel was closed, Unable to consume messages on queue... %s, %s", queue, e)
                    return

            try:

                self._channel.basic_consume(consumer_callback, queue=queue)
                self._channel.start_consuming()
            except Exception as e:
                logger.exception('Unable consume messages on queue %s', queue)
                logger.error('Error consuming messages on queue %s, %s', queue, e)
                return
        finally:
            mutex.release()

