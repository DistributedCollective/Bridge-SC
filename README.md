# Sovryn Token Bridge and Converter

## Deploy

### Deploy Sovryn test tokens
1. Run `npx truffle exec ./scripts/deploySovrynTestTokens.js --network kovan`

2. Deploy Bridge on RSK and Ethereum. See [Briedge README](./sovryn-token-bridge/bridge/README.md)
3. Deploy Converter contract on RSK. See [Converter README](./token-converter/README.md)
4. From directory Bridge run:
   1. Update percentage value:
      1. `npx truffle exec ./scripts/setFeePercentage.js --network <rskNetwork> <percentageValue>`
      2. `npx truffle exec ./scripts/setFeePercentage.js --network <ethNetwork> <percentageValue>`
   2. Allow tokens on their main network. As an example, DAI should be allowed in ETH and DOC in RSK:
      1. `npx truffle exec ./scripts/allowToken.js --network <networkName> <tokenAddress>`
   3. Add federation nodes' addresses. The address to add is the one correspondig to the privateKey configured in `federator/config/federator.key`:
      1. `npx truffle exec ./scripts/addMemberToFederation.js --network <rskNetwork> <newMemberAddress>`
      2. `npx truffle exec ./scripts/addMemberToFederation.js --network <ethNetwork> <newMemberAddress>`
      3. It is worth noting that the number of allowed members in the Federation contract must be equals to the numbers of nodes running. Otherwise, the transactions will not be approved because it is needed simple majority (half plus one of the votes).
5. Ensure the Federator account has balance on both networks.
6. Copy Bridge configs to ops/environment/configs directory, where environment is staging|uat|production.
   1. config.js
   2. mainchain JSON file. It was generated by the deploy script in `/federator/config/` directory using the networkName as the file name.
   3. sidechain JSON file. It was generated by the deploy script in `/federator/config/` directory using the networkName as the file name.
   4. federator.key
   5. db directory
   6. log-config.json
7. Change Contract addresses in ui/index.html. You can search "CONFIGS" in the file to found the place where they are configured. The RSK addresses must be in lowercase.
8. Copy the above files to server running `./ops.sh --config-server environment`.
9.  Edit `ops/docker/docker-compose-base.yml` file with the pertinent docker images.
10. Push `ops/docker/docker-compose-base.yml` to a release branch.
11. Run deploy pipe from gitlab.
