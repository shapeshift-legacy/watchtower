from tracker.models import Account, Address, BalanceChange, ERC20Token, Transaction
from common.services.rabbitmq import RabbitConnection, QUEUE_WATCHTOWER_TX_BACKFILL
from common.services.redis import redisClient
from datetime import datetime, timezone
import os
from time import sleep


import json
import logging

logger = logging.getLogger("watchtower.ingester.unchained")
host = os.environ.get("UNCHAINED_RABBIT_HOST")
port = os.environ.get("UNCHAINED_RABBIT_PORT")
user = os.environ.get("UNCHAINED_RABBIT_USER")
password = os.environ.get("UNCHAINED_RABBIT_PASS")
MAX_RETRY_ATTEMPTS = 10


class UnchainedEventIngester:
    def __init__(self):
        pass

    def process_one(self, ch, method, properties, body):
        body_json = json.loads(body)
        attempts = 0
        while attempts < MAX_RETRY_ATTEMPTS:
            try:
                e = None
                # Add ERC20 token data. Update if record exists, insert if no such record exists.
                if body_json["is_erc_20_token_transfer"]:
                    token = ERC20Token.get_or_none(
                        body_json["erc_20_token"]["contract_address"]
                    )
                    e = token if token else ERC20Token.objects.create(
                            contract_address=body_json["erc_20_token"]["contract_address"].lower(),
                            name=body_json["erc_20_token"]["name"],
                            symbol=body_json["erc_20_token"]["symbol"],
                            precision=body_json["erc_20_token"]["precision"],
                        )

                # Write transaction record to db
                t = Transaction.objects.create(
                    account_id=body_json["account_id"],
                    block_hash=body_json["block_hash"],
                    block_height=body_json["block_height"],
                    block_time=datetime.fromtimestamp(
                        body_json["block_time"], timezone.utc
                    ),
                    erc20_token_id=e.id if e else None,
                    fee=body_json.get("fee"),
                    is_dex_trade=body_json["is_dex_trade"],
                    is_erc20_fee=body_json["is_erc_20_fee"],
                    is_erc20_token_transfer=body_json["is_erc_20_token_transfer"],
                    raw="",
                    success=body_json["success"],
                    thor_memo=body_json.get("thor_memo"),
                    txid=body_json["txid"],
                )

                # Write corresponding balance change record to db
                BalanceChange.objects.create(
                    account_id=body_json["account_id"],
                    address_id=body_json["address_id"],
                    transaction_id=t.id,
                    amount=body_json["balance_change"],
                )

                break

            except Exception as e:
                sleep(100 * 2 ** attempts)
                attempts += 1
                logger.exception(
                    "Error processing unchained event (attempt {} of {}): {}".format(
                        attempts, MAX_RETRY_ATTEMPTS, body_json
                    )
                )

        if attempts == MAX_RETRY_ATTEMPTS:
            # Rejecting will forward message to deadletter queue
            ch.basic_reject(delivery_tag=method.delivery_tag)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    def process_events(self):
        RabbitConnection(host, port, user, password).consume(
            consumer_callback=self.process_one,
            queue=QUEUE_WATCHTOWER_TX_BACKFILL,
            no_ack=False,
        )
