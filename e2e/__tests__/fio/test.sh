set -e


echo "TEST REGISTER"
curl --silent --show-error --fail -X POST -d "@/__tests__/fio/xpub.json" "$WATCHTOWER_URL/register"
echo -e "\n"

echo "TEST BALANCE"
curl --silent --show-error --fail -X POST -d "@/__tests__/fio/xpub.json" "$WATCHTOWER_URL/balance"
echo -e "\n"

echo "TEST TRANSACTIONS"
curl --silent --show-error --fail -X POST -d "@/__tests__/fio/xpub.json" "$WATCHTOWER_URL/transactions"
echo -e "\n"

echo "TEST RECEIVE"
curl --silent --show-error --fail -X POST -d "@/__tests__/fio/receive.json" "$WATCHTOWER_URL/receive"
echo -e "\n"

echo "TEST SEND"
curl --silent --show-error --fail -X POST -d "@/__tests__/fio/send.json" "$WATCHTOWER_URL/send"
echo -e "\n"
