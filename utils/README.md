
# Utilities

This directory contains a few useful scripts for Watchtower development

## Register Xpubs

This script takes a list of Xpubs and registers them to Watchtower.  This is useful in case the data in the database ever needs to be corrected, for example if a bug is found in the block ingesters that results in missed transactions or incorrect balances.

### Requirements
* Python 3.6.5

* Install dependencies

```
pip3 install -r requirements.txt
```

### Usage

Copy `sample.env` to `.env` and update as needed

CLI:  

```
python3 register_xpub.py <filename>
```

Example:  

```
python3 register_xpub.py test-xpubs.json
```

### Input file format

test-xpubs.json

```
[
  {
    "xpub": "xpub6DTmfzfE6AT4qr7eYjuF1vYGwfHwMXp3gNoKxjHJgs8rDshzrgUy2xxxAaTVifZzK5eVzf7qUoAHkzFu6A3pXFCtJbRCrZWZCA3emTwaxxx",
    "network": "ETH",
    "script_type": "eth"
  },
  
  ...

  {
    "xpub": "xpub6CLjSqn6sX74YjB6s19vYY3MdP7t3xmB3RQA31Zpx3MVUayYxxxj1APzUYzNMCiyiP2ibAG5Vo3Mf7bFAv1NffyVNrrYu1EgAw41oywNxxx",
    "network": "BTC",
    "script_type": "p2pkh"
  }
]
```

### Output report format


Filename

```
inputfilename-report-timestamp.cvs
```

Contents

```
Index,Timestamp,Network,Xpub,Register Successful,Balance Before,Balance After
0,Sat May  4 08:46:46 2019,BTC,xpub6DTmfzfE6AT4qr7eYjuF1vYGwfHwMXp3gNoKxjHJgs8rDshzrgUy2xxxAaTVifZzK5eVzf7qUoAHkzFu6A3pXFCtJbRCrZWZCA3emTwaxxx,true,0,0
1,Sat May  4 08:46:55 2019,BCH,xpub6CLjSqn6sX74YjB6s19vYY3MdP7t3xmB3RQA31Zpx3MVUayYxxxj1APzUYzNMCiyiP2ibAG5Vo3Mf7bFAv1NffyVNrrYu1EgAw41oywNxxx,true,9971664,9971664

```
