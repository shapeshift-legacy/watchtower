package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	log "github.com/sirupsen/logrus"
	"golang.org/x/sync/errgroup"

	statsd "github.com/DataDog/datadog-go/statsd"
)

var (
	every                      = time.Second * 30 // how often to compare block_heights
	cqAPIKey                   = "WT_MONITOR"
	env                        string
	watchtowerBaseURL          string
	cosmosBlockExplorerBaseURL string
	fioBlockExplorerBaseURL    string
	xrpBlockExplorerBaseURL    string
	bnbBlockExplorerBaseURL    string
	thorBlockExplorerBaseURL   string
	dstatsd                    *statsd.Client
)

var networks = map[string]bool{"RUNE": true, "ATOM": true, "BTC": true, "BCH": true, "DGB": true, "LTC": true, "DOGE": true, "DASH": true, "ETH": true, "FIO": true, "XRP": true, "BNB": true}

func init() {
	environment := os.Getenv("ENVIRONMENT")

	data, err := ioutil.ReadFile(fmt.Sprintf("./config/%s.json", environment))
	if err != nil {
		log.Fatal("Could not read config file:", fmt.Sprintf("./config/%s.json", environment))
	}

	var config map[string]interface{}

	err = json.Unmarshal(data, &config)

	if err != nil {
		log.Fatal("Could not parse config file")
	}

	for k, v := range config {
		if os.Getenv(k) != "" {
			continue
		}

		switch val := v.(type) {
		case int, string, float64, bool:
			os.Setenv(k, fmt.Sprintf("%v", val))
		default:
			log.Fatal("Could not interpolate keyval: ", fmt.Sprintf("%v: %v\n", k, val))
		}

	}
}

func main() {
	var err error
	var respStr string

	env = os.Getenv("ENV")
	if env == "" {
		log.Fatal("Failure: No ENV set")
	}

	if env == "local" {
		log.Print("local agent selected")
		respStr = "dd-agent:8125" // Local datadog metrics require a local agent
		//port = ":8125"
	} else {
		log.Print("megacluster agent selected")
		respStr = "datadog-statsd.infra.svc.cluster.local:8125"
	}

	dstatsd, err = statsd.New(respStr)
	if err != nil {
		error := fmt.Errorf("Request %q, failed with error: %q", respStr, err)
		log.Error(error.Error())
	} else {
		dstatsd.Namespace = "wtk_monitor."
	}

	watchtowerBaseURL = os.Getenv("MONITOR_WATCHTOWER_BASE_URL")
	if watchtowerBaseURL == "" {
		log.Fatal("Failure: No MONITOR_WATCHTOWER_BASE_URL set")
	}

	cosmosBlockExplorerBaseURL = os.Getenv("COSMOS_GAIACLI_URL")
	if cosmosBlockExplorerBaseURL == "" {
		log.Fatal("Failure: No COSMOS_GAIACLI_URL set")
	}

	fioBlockExplorerBaseURL = os.Getenv("FIO_REMOTE_URL")
	if fioBlockExplorerBaseURL == "" {
		log.Fatal("Failure: No FIO_REMOTE_URL set")
	}

	xrpBlockExplorerBaseURL = os.Getenv("RIPPLE_BLOCK_EXPLORER_URL")
	if xrpBlockExplorerBaseURL == "" {
		log.Fatal("Failure: No RIPPLE_BLOCK_EXPLORER_URL set")
	}

	bnbBlockExplorerBaseURL = os.Getenv("BINANCE_BNBNODE_URL")
	if bnbBlockExplorerBaseURL == "" {
		log.Fatal("Failure: No BINANCE_BNBNODE_URL set")
	}

	thorBlockExplorerBaseURL = os.Getenv("THORCHAIN_GAIACLI_URL")
	if bnbBlockExplorerBaseURL == "" {
		log.Fatal("Failure: No THORCHAIN_GAIACLI_URL set")
	}

	log.SetFormatter(&log.JSONFormatter{})

	ticks := time.Tick(every)
	for range ticks {
		checkHeights()
	}
}

func checkHeights() {
	// We don't want to false positive any alerts so try to fetch height data several times
	var (
		cq, wt map[string]int
		err    error
	)

	// coinquery
	cq, err = coinqueryBlockHeights()
	if err != nil {
		log.Error(errors.New("Unable to fetch block_heights from coinquery " + err.Error()))
	}

	// watchtower
	wt, err = watchtowerBlockHeights()
	if err != nil {
		log.Error(errors.New("Unable to fetch block_heights from watchtower " + err.Error()))
	}

	validate(cq, wt)
}

// Check whether cq and wt block_heights have diverged past accepted thresholds
// Log any discrepancies so that datadog can aggregate the results
func validate(cq, wt map[string]int) {
	for n, enabled := range networks {
		if enabled == false {
			continue
		}

		if dstatsd != nil {
			err := dstatsd.Gauge(n, float64(cq[n]-wt[n]), []string{"environment:" + env}, 1)
			if err != nil {
				error := fmt.Errorf("statsd Gauge failed with error: %q", err)
				log.Fatal(error.Error())
			}
		}
	}
}

// Ask watchtower for the blockheight of each coin we care about
func watchtowerBlockHeights() (map[string]int, error) {
	body, err := httpGET(watchtowerBaseURL + "metrics/latest_block")
	if err != nil {
		return nil, err
	}

	var latest struct {
		Blocks map[string]int `json:"data"`
	}
	if err = json.Unmarshal(body, &latest); err != nil {
		return nil, err
	}

	return latest.Blocks, nil
}

// Ask coinquery for the blockheight for each coin we care about
func coinqueryBlockHeights() (map[string]int, error) {
	type entry struct {
		key   string
		value int
	}

	blockHeights := make(map[string]int)
	results := make(chan entry, len(networks))

	var g errgroup.Group
	for network, enabled := range networks {
		if enabled == false {
			continue
		}

		network := network // https://golang.org/doc/faq#closures_and_goroutines
		g.Go(func() error {
			switch network {
			case "ETH":
				ethHeight, err := coinqueryEthHeight()
				if err != nil {
					return err
				}
				results <- entry{key: "ETH", value: ethHeight}
				return nil
			case "ATOM":
				cosmosHeight, err := cosmosBlockExplorerHeight()
				if err != nil {
					return err
				}
				results <- entry{key: "ATOM", value: cosmosHeight}
				return nil
			case "FIO":
				fioHeight, err := fioBlockExplorerHeight()
				if err != nil {
					return err
				}
				results <- entry{key: "FIO", value: fioHeight}
				return nil
			case "XRP":
				xrpHeight, err := xrpBlockExplorerHeight()
				if err != nil {
					return err
				}
				results <- entry{key: "XRP", value: xrpHeight}
				return nil
			case "BNB":
				bnbHeight, err := bnbBlockExplorerHeight()
				if err != nil {
					return err
				}
				results <- entry{key: "BNB", value: bnbHeight}
				return nil
			case "RUNE":
				thorHeight, err := thorBlockExplorerHeight()
				if err != nil {
					return err
				}
				results <- entry{key: "RUNE", value: thorHeight}
				return nil
			default:
				utxoHeight, err := coinqueryUtxoHeight(network)
				if err != nil {
					return err
				}
				results <- entry{key: network, value: utxoHeight}
				return nil
			}
		})
	}

	go func() {
		g.Wait()
		close(results)
	}()

	for entry := range results {
		blockHeights[entry.key] = entry.value
	}

	// Return the first error if any fetching routine generated an error
	if err := g.Wait(); err != nil {
		return blockHeights, err
	}

	return blockHeights, nil
}

func thorBlockExplorerHeight() (int, error) {
	url := fmt.Sprintf("%s/blocks/latest", thorBlockExplorerBaseURL)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var info struct {
		Block struct {
			Header struct {
				Height int64 `json:"height,string"`
			} `json:"header"`
		} `json:"block"`
	}
	if err = json.Unmarshal(body, &info); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	return int(info.Block.Header.Height), nil
}

func cosmosBlockExplorerHeight() (int, error) {
	url := fmt.Sprintf("%s/blocks/latest", cosmosBlockExplorerBaseURL)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var info struct {
		Block struct {
			Header struct {
				Height int64 `json:"height,string"`
			} `json:"header"`
		} `json:"block"`
	}
	if err = json.Unmarshal(body, &info); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	return int(info.Block.Header.Height), nil
}

func fioBlockExplorerHeight() (int, error) {
	url := fmt.Sprintf("%s/v1/chain/get_info", fioBlockExplorerBaseURL)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var latest struct {
		BlockNum int `json:"fork_db_head_block_num"`
	}
	if err = json.Unmarshal(body, &latest); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	return latest.BlockNum, nil
}

func xrpBlockExplorerHeight() (int, error) {

	url := fmt.Sprintf("%s/v2/ledgers", xrpBlockExplorerBaseURL)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var info struct {
		Ledger struct {
			Height int `json:"ledger_index"`
		} `json:"ledger"`
	}
	if err = json.Unmarshal(body, &info); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	return info.Ledger.Height, nil
}

func bnbBlockExplorerHeight() (int, error) {

	url := fmt.Sprintf("%s/status", bnbBlockExplorerBaseURL)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var info struct {
		Result struct {
			Syncinfo struct {
				Height int64 `json:"latest_block_height,string"`
			} `json:"sync_info"`
		} `json:"result"`
	}
	if err = json.Unmarshal(body, &info); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	return int(info.Result.Syncinfo.Height), nil
}

func coinqueryUtxoHeight(network string) (int, error) {
	// get latest block hash
	url := fmt.Sprintf("%s/%s/status?q=getLastBlockHash&apikey=%s", os.Getenv("COINQUERY_URL"), strings.ToLower(network), cqAPIKey)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var latest struct {
		BlockHash string `json:"lastblockhash"`
	}
	if err = json.Unmarshal(body, &latest); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	// get latest block
	url = fmt.Sprintf("%s/%s/block/%s?apikey=%s", os.Getenv("COINQUERY_URL"), strings.ToLower(network), latest.BlockHash, cqAPIKey)
	body, err = httpGET(url)
	if err != nil {
		return -1, err
	}

	var block struct {
		Height int `json:"height"`
	}
	if err = json.Unmarshal(body, &block); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	return block.Height, nil
}

func coinqueryEthHeight() (int, error) {
	url := fmt.Sprintf("%s?module=proxy&action=eth_blockNumber&apikey=%s", os.Getenv("COINQUERY_ETH_URL"), cqAPIKey)
	body, err := httpGET(url)
	if err != nil {
		return -1, err
	}

	var latest struct {
		Height string `json:"result"`
	}
	if err = json.Unmarshal(body, &latest); err != nil {
		return -1, fmt.Errorf("Request %q, failed to unmarshal body: %q, with error: %q", url, string(body), err)
	}

	// eth returns height as hex so we need to parse it to int
	height, err := strconv.ParseInt(strings.TrimPrefix(latest.Height, "0x"), 16, 64)
	if err != nil {
		return -1, err
	}

	return int(height), nil
}

// convenience method around all the gets this program does
func httpGET(url string) ([]byte, error) {
	var body []byte
	return body, retry(3, 2, func() error {
		resp, err := http.Get(url)
		if err != nil {
			return fmt.Errorf("Request: %q, failed with error: %q", url, err.Error())
		}
		defer resp.Body.Close()

		body, err = ioutil.ReadAll(resp.Body)
		if err != nil {
			return fmt.Errorf("Request: %q, failed with error: %q, and body: %q", url, err.Error(), string(body))
		}

		return nil
	})
}

func retry(attempts int, sleep int64, fn func() error) error {
	if err := fn(); err != nil {
		if attempts--; attempts > 0 {
			time.Sleep(time.Duration(sleep) * time.Second)

			return retry(attempts, sleep, fn)
		}

		return err
	}

	return nil
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
