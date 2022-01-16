find federator-env/mainnet-BSC-RSK/db/. -type f -not -name 'failingTxIds.txt' -delete
find federator-env/mainnet-ETH-RSK/db/. -type f -not -name 'failingTxIds.txt' -delete
find federator-env/testnet-BSC-RSK/db/. -type f -not -name 'failingTxIds.txt' -delete
find federator-env/testnet-ETH-RSK/db/. -type f -not -name 'failingTxIds.txt' -delete
rm -rf federator.log
git reset --hard origin/rinkeby-deploymnet
git pull
