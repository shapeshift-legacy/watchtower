### REST API

Unified API across assets (blockchains and tokens)

* Base URL:

```
https://{WATCHTOWER_URL}/api/v1
```

* `/` - info pages  (only workings when running watchtower locally)

* POST `/xpubs`

        Request Payload:
        {
            "data": [
                {
                "network": "BTC",
                "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v", // this is a ShapeShift test XPub
                "script_type": "p2pkh" // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                }
           ]
        }

        Response:
        {
            "success": true,
            "data": [
                {
                "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                "network": "BTC",
                "script_type": "p2sh-p2wpkh",
                "registered_at": "2019-09-12T07:26:10.632Z",
                "updated_at": "2019-09-12T07:26:25.762Z",
                "sync_status": "COMPLETE",
                "tx_count": 32
                }
            ]
        }

* POST `/register`

        Request Payload:
        {
            "data": [
                {
                "network": "BTC",
                "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v", // this is a ShapeShift test XPub
                "script_type": "p2pkh" // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                }
           ]
        }

        Query Parameters:
        {
            "async": "false",      // Optional: "true", "false" - If true, keep the connection open until sync is complete
            "hard_refresh": false, // Optional: "true", "false" - If true, delete previous XPub data before sync
        }

        Response:
        {
            "success": true,
            "data": [
                {
                "network": "BTC",
                "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                "script_type": "p2pkh" // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                }
            ]
        }

* POST `/unregister`

        Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "network": "BTC",
                    "script_type": "p2pkh"
                },
                ...
            ]
        }

        Response:
        {
            "success: true,
            "data": {
                "records_deleted": 1
            }
        }

* POST `/xpubs`

        Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6BiVtCpG9fQPxnP...",
                    "network": "BTC",
                    "script_type": "p2pkh"
                },
                ...
            ]
        }

        Response:
        {
            "success: true,
            "data": {
                "xpub": "xpub6BiVtCpG9fQPxnP...",
                "network": "BTC",
                "script_type": "p2pkh",
                "registered_at": "2019-08-21T16:57:33.472Z",
                "updated_at": "2019-08-21T18:21:58.668Z",
                "sync_status": "COMPLETE",
                "tx_count": 76
            }
        }

* POST `/send`

        Request Payload:
        {
            "network": "BTC",
            "rawtx": "01000000017b1eabe0209b1fe794124..."
        }

* POST `/receive`

        Request Payload:
        {
            "network": "BTC",
            "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
            "script_type": "p2pkh", // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
            "count": 3  // Optional. Defaults to 1
        }

        Response:
        {
            "success": true,
            "data": [
                {
                    "address": "1KJuqq65RC4...",
                    "relpath": "0/4"
                }
            ]
        }

* POST `/transactions`

        Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                    "network": "BTC",
                    "script_type": "p2pkh", // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                    "token": "SALT",  // Optional. If provided, network must be ETH.
                    "contract_address": "0xfeasdf...",  // Optional. Overrides "token".
                },
                ...
            ]
        }

        Response:
        {
            "success": true,
            "pagination": {
                "page": 1,
                "total_objects": 12,
                "total_pages": 2
            },
            "data": [
                {
                    "txid": "984d3a436...",
                    "status": "confirmed",
                    "type": "receive",
                    "amount": 832385,
                    "date": "2019-05-22T17:55:52Z",
                    "confirmations": 2876,
                    "network": "BTC",
                    "symbol": "BTC",
                    "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v"
                },
                ...
            ]
        }

* POST `/balance`

        Request Payload:
        {
            "data": {
                "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                "network": "BTC",
                "script_type": "p2pkh", // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                "token": "SALT"  // optional
            },
            "supportedTokens": {
                "FOX": "0xc770EEfAd204B5180dF6a14Ee197D99d808ee52d",
                "GNT": "0xa74476443119A942dE498590Fe1f2454d7D4aC0d",
                "..."
            }
        }

        Response:
        {
            "success": true,
            "data": [
                {
                    "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                    "network": "BTC",
                    "script_type": "p2pkh", // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                    "symbol": null,
                    "contract_address": null,
                    "balance": 849635
                }
            ]
        }

* POST `/balance/multihistory`

        Query Parameters:
        {
            "interval": "daily",    // Required: "weekly", "daily", "hourly", "minutely", "30min", "15min", "10min", "5min", or "1min"
            "start": 1537463623,    // Optional: UNIX time in seconds or ISO-8601 date/datetime format. Defaults to (end - (limit * interval)).
            "end": "2018-06-12",    // Optional: UNIX time in seconds or ISO-8601 date/datetime format. Defaults to current time.
            "limit": 1000,          // Optional: Number of data points to return if both "start" and "end" are not provided. Defaults to 1000.
            "ordering": "asc"       // Optional: Time sort ordering. Possible values are "asc" and "desc". Defaults to "asc".
        }

        Request Payload:
        {
            "data": [
                {
                    "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                    "network": "BTC",
                    "script_type": "p2pkh" // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                },
                ...
            ]
        }

        Response:
        {
            "combinedResults": [
                {
                    "success": true,
                    "params": {
                        "interval": "daily",
                        "start": "2016-09-13 20:11:04+00:00",
                        "end": "2019-06-10 20:11:04+00:00",
                        "limit": 1000,
                        "ordering": "asc"
                    },
                    "query_execution_time": null,
                    "data": [
                        [
                            "2016-09-13T00:00:00Z",
                            0
                        ],
                        ...
                        [
                            "2019-06-10T00:00:00Z",
                            849635
                        ]
                    ],
                    "network": "BTC",
                    "token": null,
                        "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v"
                }
            ]
        }

* POST `/tools/create_unsigned_transaction`

        Request Payload:
        {
            "network": "BTC",
            "inputs": [
                {
                    "xpub": "xpub6DQUmPVSBcw2iFEFNKjryn9XBb6qoTuezuYPi4deyELvgd6oCkFX4HwVsQGUXs4Ki9AKFJYuJhYiQGCAT73s6YYfeCsmhZ7dTkRzcR9dN7v",
                    "script_type": "p2pkh", // "p2pkh", (UTXO coins), "p2wsh", "p2wpkh", "p2sh-p2wpkh" (Bitcoin only), "eth" (Ethereum only)
                    "account_address_n": [2147483692, 2147483648, 2147483648]
                }
            ],
            "token": "SALT",                    // Optional. If provided, network must be ETH.
            "contract_address": "0xfeasdf...",  // Optional. If provided, will override "token".
            "include_txs": true,                // Optional. Defaults to false
            "include_hex": true,                // Optional. Defaults to false
            "recipients": [
                {
                    "address": "12DrP8aGcXHBkdKEnWVa7t3TJ1FvAzm6Nh",
                    "send_max": false,          // Optional. If provided, "amount" is ignored.
                    "amount": 10000,            // Units in Satoshis (or Wei for Ethereum)
                    "data": "0x",               // Optional for ETH/tokens. Ignored for utxo coins.
                    "script_type": "p2pkh"
                }
            ],
            // fee selection (supported for BTC only):
            // if effort is present, it will be used, otherwise desired_conf_time
            "effort": "5",                      // 1-5, 5 = fastest, 1 = cheapest
            "desired_conf_time: "halfHour"      // fastest, halfHour, 1hour, 6hour, 24hour
        }

        Response:
        {
	    "success": true,
	    "data":
	        {
	        "inputs": [
	            {
	                "txid": "3f0bf5c2f83e33b9c47976db1214c13a696b026e08783e5b7fa4c236413aecf9",
	                "vout": 0,
	                "address": "1JhrpqRzm4gStsTvskfrMxUBYfTV41Ydsi",
	                "script_type": "p2pkh",
	                "amount": "1249",
	                "confirmations": 3986,
	                "address_n": [
	                    2147483692,
	                    2147483648,
	                    2147483648,
	                    0,
	                    5
	                ]
	            },
               ...
	        ],
	        "outputs": [
	            {
	                "address": "12DrP8aGcXHBkdKEnWVa7t3TJ1FvAzm6Nh",
	                "amount": "10000",
	                "is_change": false
	            },
	            {
	                "address": "14pPdkz3coSRJXGuS6mWmK8yut4RWfTTF4",
	                "amount": "802111",
	                "is_change": true,
	                "index": 7,
	                "relpath": "1/7",
	                "script_type": "p2pkh",
	                "address_n": [
	                    2147483692,
	                    2147483648,
	                    2147483648,
	                    1,
	                    7
	                ]
	            }
	        ],
	        "fee": 37524,
	        "feePerKB": 69632
	        }
	    }


- GET `/network_fees`

```
Response:

{
  "success": true,
  "data": {
    "BTC": {
      "network": "BTC",
      "fee": {
        "fastest": {
          "maxMinutes": 35,
          "fee": 201728,
          "minMinutes": 0
        },
        "halfHour": {
          "maxMinutes": 35,
          "fee": 201728,
          "minMinutes": 0
        },
        "1hour": {
          "maxMinutes": 50,
          "fee": 193536,
          "minMinutes": 0
        },
        "6hour": {
          "maxMinutes": 300,
          "fee": 21504,
          "minMinutes": 20
        },
        "24hour": {
          "maxMinutes": 480,
          "fee": 1024,
          "minMinutes": 20
        }
      },
      "units": "sats/kb"
    },
    "BCH": {
      "network": "BCH",
      "fee": 1000,
      "units": "sats/kb"
    },
    "LTC": {
      "network": "LTC",
      "fee": 100000,
      "units": "sats/kb"
    },
    "DOGE": {
      "network": "DOGE",
      "fee": 500000000,
      "units": "sats/kb"
    },
    "DASH": {
      "network": "DASH",
      "fee": 5000,
      "units": "sats/kb"
    },
    "DGB": {
      "network": "DGB",
      "fee": 5000,
      "units": "sats/kb"
    },
    "ETH": {
      "network": "ETH",
      "fee": "unknown",
      "units": "sats/kb"
    }
  }
}
```

- GET `/transaction`

```
     Example Request Query:
         /transaction?txid=f45cc0854e37f5a280824157428e88f260f03704d8dbd2d1fd86c669cf2de7f1

     Example Response:
         {
             "success": true,
             "tx": [
                 {
                     "id": 14,
                     "txid": "f45cc0854e37f5a280824157428e88f260f03704d8dbd2d1fd86c669cf2de7f1",
                     "block_height": 632791,
                     "block_hash": "000000000000000000077ee87a5915c31afa88756bcc10b4fdf21987ddf7681c",
                     "raw": "",
                     "status": "confirmed",
                     "is_erc20_fee": false,
                     "erc20_token_id": null,
                     "is_dex_trade": false,
                     "success": true
                 }
             ]
         }
```

### RabbitMQ

For every registered XPub, Watchtower publishes messages for these events:

- TX pending in mempool
- TX mined (first confirmation)

Watchtower also publishes a message everytime a block is mined.


```
    Example message payload:
    {
      "txid": "41c4f5cb072b9b0bbf...",
      "status": "confirmed",
      "type": "receive",
      "amount": 2000000,
      "date": "2019-02-21T23:25:22Z",
      "confirmations": 1,
      "network": "LTC",
      "xpub":   "xpub6C9BxaohKRWnE2..."
    }
```

Special cases:

1. Axiom user A <-> Axiom user B transactions:  publish two messages, one for Xpub A and one for Xpub B
2. ERC-20 tokens: publish one message for the token transfer, and a second message for the gas spent in the transaction
