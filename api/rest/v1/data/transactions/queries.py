UTXO_TRANSACTIONS_SQL = """
            SELECT account.xpub,
                   account.script_type,
                   account.network,
                   tx.id,
                   tx.txid,
                   tx.block_height,
                   tx.block_hash,
                   tx.block_time,
                   tx.success,
                   COALESCE((chainheight.height + 1) - tx.block_height, 0) AS confirmations,
                   CASE WHEN tx.block_height IS NULL OR tx.block_time IS NULL THEN 'pending'
                        ELSE 'confirmed'
                   END AS status,
                   false AS is_erc20_fee,
                   tx.thor_memo AS thor_memo,
                   tx.fee AS fee,
                   SUM(bal.amount) AS amount
            FROM tracker_account account
                   JOIN tracker_chainheight chainheight ON account.network = chainheight.network
                   JOIN tracker_transaction tx ON account.id = tx.account_id
                   JOIN tracker_balancechange bal ON tx.id = bal.transaction_id
            WHERE account.xpub = %s
              AND account.script_type = %s
              AND account.network = %s
              AND ( (tx.thor_memo IS NOT NULL AND %s = true) OR (%s = false) )
            GROUP BY account.xpub, account.script_type, account.network, tx.id, tx.txid, tx.block_height, tx.block_hash, tx.block_time, chainheight.height, is_erc20_token_transfer, erc20_token_id, is_erc20_fee
        """

ETH_TRANSACTIONS_SQL = """
            SELECT account.xpub,
                   account.script_type,
                   account.network,
                   tx.id,
                   tx.txid,
                   tx.block_height,
                   tx.block_hash,
                   tx.block_time,
                   tx.success,
                   COALESCE((%s + 1) - tx.block_height, 0) AS confirmations,
                   CASE WHEN tx.block_height IS NULL THEN 'pending'
                        ELSE 'confirmed'
                   END AS status,
                   tx.is_erc20_fee AS is_erc20_fee,
                   tx.thor_memo AS thor_memo,
                   tx.fee AS fee,
                   SUM(bal.amount) AS amount
            FROM tracker_account account
                   JOIN tracker_transaction tx ON account.id = tx.account_id
                   JOIN tracker_balancechange bal ON tx.id = bal.transaction_id
            WHERE account.xpub = %s
              AND account.script_type = %s
              AND account.network = 'ETH'
              AND NOT tx.is_erc20_token_transfer
              AND ( tx.is_dex_trade = %s OR %s = false )
              AND ( (tx.thor_memo IS NOT NULL AND %s = true) OR (%s = false) )
            GROUP BY account.xpub, account.script_type, account.network, tx.id, tx.txid, tx.block_height, tx.block_hash, tx.block_time, is_erc20_token_transfer, erc20_token_id, is_erc20_fee
        """

ERC20_TRANSACTIONS_SQL = """
            SELECT account.xpub,
                   account.script_type,
                   erc20.symbol AS network,
                   tx.id,
                   tx.txid,
                   tx.block_height,
                   tx.block_hash,
                   tx.block_time,
                   tx.success,
                   COALESCE((%s + 1) - tx.block_height, 0) AS confirmations,
                   CASE WHEN tx.block_height IS NULL THEN 'pending'
                        ELSE 'confirmed'
                   END AS status,
                   tx.is_erc20_fee AS is_erc20_fee,
                   tx.thor_memo AS thor_memo,
                   tx.fee AS fee,
                   SUM(bal.amount) AS amount
            FROM tracker_account account
                   JOIN tracker_transaction tx ON account.id = tx.account_id
                   JOIN tracker_erc20token erc20 ON tx.erc20_token_id = erc20.id
                   JOIN tracker_balancechange bal ON tx.id = bal.transaction_id
            WHERE account.xpub = %s
              AND account.script_type = %s
              AND account.network = 'ETH'
              AND tx.is_erc20_token_transfer
              AND ( tx.is_dex_trade = %s OR %s = false )
              AND ( (tx.thor_memo IS NOT NULL AND %s = true) OR (%s = false) )
        """

TX_BY_TXID_SQL = """
              SELECT tx.id,
                     tx.txid,
                     tx.block_height,
                     tx.block_hash,
                     tx.raw,
                     CASE WHEN tx.block_height IS NULL THEN 'unconfirmed'
                            ELSE 'confirmed'
                     END AS status,
                     tx.is_erc20_fee,
                     tx.erc20_token_id,
                     tx.is_dex_trade,
                     tx.success
              FROM tracker_transaction tx
              WHERE txid = %s
       """

ERC20_CONTRACT_ADDRESS_SQL = " AND erc20.contract_address = %s"
ERC20_SYMBOL_SQL = " AND erc20.symbol = %s"
ERC20_GROUP_BY_SQL = """ GROUP BY account.xpub, account.script_type, erc20.symbol, tx.id, tx.txid, tx.block_height,
                           tx.block_hash, tx.block_time, is_erc20_token_transfer, erc20_token_id, is_erc20_fee """

UNION_ALL_SQL = " UNION ALL "
COUNT_SQL = "SELECT COUNT(1) FROM ({}) AS total"

ORDER_BY_SQL = " ORDER BY block_time DESC, id ASC"

LIMIT_OFFSET_SQL = " LIMIT %s OFFSET %s"

TOKENS_WITH_TX = """
            select distinct erc20.symbol, erc20.contract_address
            from tracker_account account
            join tracker_transaction transaction on account.id = transaction.account_id
            join tracker_erc20token erc20 on transaction.erc20_token_id = erc20.id
            where account.network = 'ETH'
              and account.xpub = ANY(%s)
        """

PENDING_TXS = """
        SELECT  tx.id,
                tx.txid,
                tx.block_height
        from tracker_transaction tx
                JOIN tracker_account on tx.account_id = tracker_account.id
                WHERE tracker_account.network = %s
                AND tx.block_height < 1
"""

