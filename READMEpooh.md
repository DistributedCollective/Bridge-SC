# Sovryn Token Bridge and Converter
1. git clone https://gitlab.com/atixlabs/sovryn-token-bridge-converter.git
2. Update *.key files:
sovryn-token-bridge/bridge/infura.key
sovryn-token-bridge/bridge/mnemonic.key
token-converter/infura.key
token-converter/mnemonic.key
3. Update truffle-config.js files -the file differ (with rsktestnet node):
sovryn-token-bridge/bridge/truffle-config.js
token-converter/truffle-config.js

4.0 - Fund the deployer account[0] with RBTC and ETHKovan 
4. Deploy bridge:
cd sovryn-token-bridge/bridge/
npm install

// First time or if: "Error on oz deployment" during 7_deploy_bridge_v0.js deployment
On 1st terminal: npm run ganache
On 2nd terminal: npm run migrate
// First time or if: "Error on oz deployment" during 7_deploy_bridge_v0.js deployment

truffle migrate --reset --network rsktestnet
truffle migrate --reset --network kovan

5. Only for testing, create ERC20 tokens (DAI, WBTC) on Kovan:
cd sovryn-token-bridge/bridge/
npx truffle exec --network kovan ./scripts/test/deploySovrynTestTokens.js

6. setup the Bridge:
cd sovryn-token-bridge/bridge/

+ Allow tokens:
npx truffle exec ./scripts/allowToken.js --network kovan <DAI address of stage5>
npx truffle exec ./scripts/allowToken.js --network kovan <WBTC address of stage5>

+ Update percentage value: (example: 200 == 2%)
npx truffle exec ./scripts/setFeePercentage.js --network kovan 200
npx truffle exec ./scripts/setFeePercentage.js --network rsktestnet 200

+ Set min allowed. Should be in wei units.
In this example: 
1000000000000000 wei == 100000 satoshi == 0.001 BTC
npx truffle exec ./scripts/setMinTokenAmount.js --network kovan 1000000000000000

+ Add default federator (account[0] that deploy the SC) private key: 
sovryn-token-bridge/federator/config/federator.key

+ add more federators if needed. add the private keys to federator.key file:
*** <federator address> Should be lower case ***
npx truffle exec ./scripts/addMemberToFederation.js --network kovan <federator address>
npx truffle exec ./scripts/addMemberToFederation.js --network rsktestnet <federator address>
sovryn-token-bridge/federator/config/federator.key

copy configs to Docker configs -
 update manually host if needed for mainnet-testnet:
cd sovryn-token-bridge-converter/configs/
 kovan.json
 rsktestnet.json
 federator.key

+ Only for Tet UI:
ui/index.html - update bridge SC address in configs

7. Deploy converter:
cd token-converter/bridge/
npm install
truffle migrate --reset --network rsktestnet

8. setup the Converter:
cd token-converter/bridge/

+ set conversion rate ( example 1000 equals 10%)
Remix (setConversionFee(1000)) OR truffle:
truffle console --network rsktestnet
converter = await Converter.deployed()
converter.setConversionFee(1000)

+ Whitelist tokens:
Remix (addTokenToWhitelist(<token-addr>)) OR truffle:
truffle console --network rsktestnet
converter = await Converter.deployed()
converter.addTokenToWhitelist(<RSK-main-token-addr OR side-token-addr>)

+ Set Bridge Contract
Remix (setBridgeContract(<RSK-bridge-addr>)) OR truffle:
truffle console --network rsktestnet
converter = await Converter.deployed()
converter.(setBridgeContract(<RSK-bridge-addr>))

9. Test receiveTokensAt:
+ Use this js to convert address to bytes.
Example: 
truffle console --network rsktestnet
converter = await Converter.deployed()
const userData = web3.eth.abi.encodeParameter("address", accounts[3]);
console.log(userData)

+ Send receiveTokensAt to converter. This create a sell order of rERC20 tokens. When the sell orders will be taken
the rBTC will be send to the address encoded in userdata parameter.
Example: this can be send from any account (after approvre as usual)
receiveTokensAt(<ETH-ERC20-addr>, <amount>, <converter-addr>, bytes(RSK-addr-to-receive-rBTC-))

## ATIX ##
==========

# Sovryn Token Bridge and Converter

## Scripts
All the script from `sovryn-token-bridge/bridge/scripts` directory use the contract addresses from the build contract directory json files.

1. Allow tokens
2. Configure Bridge fee percentage
3. Set the minimum token amount allowed crossing
4. Add a member to federation
5. Deploy Sovryn test tokes: 
   1. Dai Stablecoin, DAI
   2. Wrapped Ether, WETH
   3. Wrapped BTC, WBTC
   4. RenBTC, renBTC
   5. Tether USD, USDT


## Allow tokens
New tokens must be allowed in the AllowTokens contract which resides in the original token network. As an example, DAI should be allowed in ETH and DOC in RSK.

To allow a token go to directory `sovryn-token-bridge/bridge` and run:
 - `npx truffle exec ./scripts/allowToken.js --network <networkName> <tokenAddress>`

## How to get the side tokens from the original tokens
- After the first token cross the bridge creates the side token on the side chain. You can use `npx truffle exec --network kovan ./scripts/test/createRskSideTokens.js <cant>` to make a cross of `<cant>` of each token to the same address.
- call `bridge.mappedTokens(original token address)` using the bridge from the side chain.
- As an example, if you want to get the rDAI token address call `mappedTokens` on the rsk network passing as argument the DAI token address.

## Bridge token amounts limitations
The Bridge contracts have a set of rules, for all tokens, that determine how many tokens a user can cross. Those rules are:
- maxTokensAllowed = 10000 ether; Maximum number of tokens allowed crossing.
- minTokensAllowed = 1 ether; Minimum number of tokens allowed crossing.
- dailyLimit = 100000 ether; Limit by day of token allowed crossing.

It is worth noting that the Bridge contract format the amount of token before validating the rules. This format is applied to tokens with a different amount of decimals from 18.

Having said that, the default value (1 ether) prevents user to cross less a fractional amount of tokens.

You can use the script `setMinTokenAmount.js` to set the minimum amount:
  `npx truffle exec ./scripts/setMinTokenAmount.js --network <networkName> amount`

## Deploy

### Deploy Sovryn test tokens
1. Run `npx truffle exec ./scripts/test/deploySovrynTestTokens.js --network kovan`

### Deploy contracts and configure them
#### Bridge
2. Deploy Bridge on RSK and Ethereum. See [Bridge README](./sovryn-token-bridge/bridge/README.md)
3. Deploy Converter contract on RSK. See [Converter README](./token-converter/README.md)
4. As a result, files in the `federator/config` folder are created with the addresses of the main contracts
   1. `kovan.json` for Kovan network containing the following object:
```` 
      {
         "bridge": "0x00a872a468cbaa989ba3cb88021fcd51bb79536d",
         "federation": "0xeb1e055d1a56950b1a3d7ac015f02bea9c6f0f7e",
         "multiSig": "0x34d968bdd6bd360c3252420eeb47d3f78b15a00c",
         "allowTokens": "0x5b4397ed5422bd77810899712bf2201a52f38c7c",
         "host": "",
         "fromBlock": 23755870
      }      
``````
   2. `rsktestnet.json` for RskTestnet network containing the following object:
```` 
      {
         "bridge": "0xd024f2fa6399af2a93dd5356bad3bc2750de4b79",
         "federation": "0x85162d3c790bfd6e4b7c781eb3b9f5623ab0bf91",
         "multiSig": "0x472a3ff0c17f26bff5c19ddd622d46e5accb3b61",
         "allowTokens": "0x758e9f47baef7260fa522bde1e3e0ebc80d6a1ba",
         "host": "",
         "fromBlock": 1656712
      }
``````
1. From directory Bridge run:
   1. Update percentage value:
      1. `npx truffle exec ./scripts/setFeePercentage.js --network <rskNetwork> <percentageValue>`
      2. `npx truffle exec ./scripts/setFeePercentage.js --network <ethNetwork> <percentageValue>`
   2. Allow tokens on their main network. As an example, DAI should be allowed in ETH and DOC in RSK:
      1. `npx truffle exec ./scripts/allowToken.js --network <networkName> <tokenAddress>`
   3. Add federation nodes' addresses. The address to add is the one corresponding to the privateKey configured in `federator/config/federator.key`:
      1. By default the owner who deployed is added as a member. To keep adding members excute the following scripts       
         To remove a member from the federation use:
         `npx truffle exec ./scripts/removeMemberFromFederation.js --network <rsktestnet/kovan> <oldMemberAddress>`
      2. `npx truffle exec ./scripts/addMemberToFederation.js --network <rskNetwork> <newMemberAddress>`
      3. `npx truffle exec ./scripts/addMemberToFederation.js --network <ethNetwork> <newMemberAddress>`
      4. It is worth noting that the number of allowed members in the Federation contract must be equals to the numbers of nodes running. Otherwise, the transactions will not be approved because it is needed a simple majority (half plus one of the votes).
2. Ensure the Federator account has balance on both networks.
3. Copy Bridge configs to `ops/${ENVIRONMENT}/configs directory`, where `ENVIRONMENT` is `staging|uat|production`.
   1. config.js
   2. mainchain JSON file. It was generated by the deployment script in `/federator/config/` directory using the networkName as the file name.
   3. sidechain JSON file. It was generated by the deployment script in `/federator/config/` directory using the networkName as the file name.
   4. federator.key
   5. db directory
   6. log-config.json
4. Change Contract addresses in `ui/index.html`. You can search "CONFIGS" in the file to found the place where they are configured. The RSK addresses must be in lowercase.
5.  Setup server and copy the above files to server running `./ops.sh --config-server environment` from directory `ops`.
6.  Edit `ops/docker/docker-compose-base.yml` file with the pertinent docker images.
7.  Push `ops/docker/docker-compose-base.yml` to a release branch.
8.  Run deploy pipe from gitlab or run manually using `./ops.sh --deploy $environment`

#### Converter
1. To configure this contract a side token, passing throuwgh the Converter must be minted first
   1. Send renBTC or wBTC tokens to any address so the bridge can mint its side token. Wait for it.
   2. Check the minted side token using this script in the rsk console
      1. `npx truffle exec ./scripts/test/getSideTokenAddresses.js --network rsktestnet`
      2. This script will bring back a screen similar to this one:
      ┌─────────┬──────────────────────────────────────────────┬──────────────────────────────────────────────┐
      │ (index) │                   original                   │                  sideToken                   │
      ├─────────┼──────────────────────────────────────────────┼──────────────────────────────────────────────┤
      │    0    │ '0x832915943cc51c0620f32dfbaf8b9addb0db25e1' │ '0x0000000000000000000000000000000000000000' │
      │    1    │ '0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9' │ '0x45414a3072c577f0397f137458bf71a06e769354' │
      │    2    │ '0x755de969cbc0e7df97eac28933c6a2385c087ca1' │ '0x0000000000000000000000000000000000000000' │
      │    3    │ '0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a' │ '0x7dd5068e1967da72c751e5041864368800c14908' │
      │    4    │ '0xd871ce15efa071b06104dac4225540f5461d17de' │ '0x0000000000000000000000000000000000000000' │
      └─────────┴──────────────────────────────────────────────┴──────────────────────────────────────────────┘
      Where the original token and its equivalent are shown 
2. Set the conversion fee by opening the console in the rsk network and executing
   `converter = await Converter.deployed()`
   `converter.setConversionFee(1000)` (this is for 10%)
3. White list the tokens allowed to pass through the converter by copying the address of the sideToken
   `converter.addTokenToWhitelist("0x7dd5068e1967da72c751e5041864368800c14908")`
4. Set the Bridge Address in the Converter by copying the address in one of the generated files (Ex. `rsktestnet.json`)
   `converter.setBridgeContract("0xab5013298c85d0E024C566B3ae46033D1f447D4e")`
5. All the parameters for the Bridge are now configured
      
## Common Issues

### `receiveTokensAt` transaction fails.
It might be because:
1. The bridge proxy is pointing to an old bridge implementation. So, the function doesn't exist in the contract.
   1. Try to upgrade the contract using a script similar to the migration `sovryn-token-bridge/bridge/migrations/16_deploy_bridge_v2.js`.
2. See `receiveTokens` problems.

### `receiveTokens` transaction fails.
It might be because:
1. You forgot to make an approval transaction for the bridge address and the pertinent token amount.
2. The token is not allowed in the `AllowTokens` contract configured in the `Bridge`.
3. The `feePercentage` is not configured in the `Bridge`.

### Federation vote transaction fails
It might be because:
1. The mainchain or sidechain configs are wrong.
2. The federation contract has set a wrong bridge address. 
   1. Use `federation.setBridge` function. This can be executed only by the owner which is the MultiSigWallet.
3. The bridge contract has set a wrong federation address.
   1. Use `bridge.changeFederation` function. This can be executed only by the owner which is the MultiSigWallet.

## How to test it manually
1. Connect to a web3 console. You can use truffle console running: `npx truffle console --network $networkname`.
2. Copy and paste each command in the web3 console.
   Be aware this script was made with the addresses and abis of our deployment. Change these scro[ts as needed by putting the correct token addresses and contracts abis as well.
   - For RSK network see `sovryn-token-bridge/bridge/scripts/test/rskTest.js`.
      - Take sell order
   - For Kovan network see `sovryn-token-bridge/bridge/scripts/test/ethTest.js`.
      - cross tokens with converter as receiver. So it creates a sell order in the RSk converter contract
      - cross tokens to another address