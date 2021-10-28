package main

import (
	"fmt"
	"os"
	"encoding/base64"
	"encoding/json"
    "github.com/binance-chain/go-sdk/types"
	"github.com/binance-chain/go-sdk/types/tx"
)

func main() {

	codec := types.NewCodec()
	args := os.Args[1:]

	txs := make([][]byte, len(args))
	for i := range txs {
		decoded, err := base64.StdEncoding.DecodeString(args[i])
		if err != nil {
			fmt.Println("error:", err)
		}
		txs[i] = decoded
    }

	parsedTxs := make([]tx.StdTx, len(txs))
    for i := range txs {
        err := codec.UnmarshalBinaryLengthPrefixed(txs[i], &parsedTxs[i])
        if err != nil {
			fmt.Println("Error - codec unmarshal")
			fmt.Println(err)
            return
        }
    }

    bz, err := json.Marshal(parsedTxs)

    if err != nil {
	   fmt.Println("Error - json marshal")
	   fmt.Println(err)
       return
    }

    fmt.Println(string(bz))
}
