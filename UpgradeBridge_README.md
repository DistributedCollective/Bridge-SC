=============================================
RSK Mainnet Upgarde
=============================================
1+ cd into rskmainnet deploy:
        RSK Mainnet: MAIN-Restore-RSK-ETH
DONE

1.1+ create branch for v2 deployment:
RSK-V2-Deploy
DONE

1.2+ create branch for v3 upgrade:
RSK-V3-Upgrade-latest
DONE

2+ Change multisig required to 1
npx truffle exec ./scripts/changeRequiredSigners.js --network rskmainnet 1
DONE

2.1+ Add account1 as owner: 
npx truffle exec ./scripts/addOwner.js --network rskmainnet 0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2
DONE

3+ put migration files in migration folder:
        as in upgrade-rsk-ropsten:
        1
        18
        19_1
        19
        20_1
        20
        21
DONE

3.1+ Copy contracts/*.sol files from master
DONE

3.2+ Make sure optimizer is true in trufle-config.js, and evmversion: istanbul
and false in .openzeppelin./project.json 
and evmversion: istanbul
DONE

4+ Copy abis as in upgrade-rsk-ropsten
DONE

5+ Copy scripts as in upgrade-rsk-ropsten
Aligned all scripts at master and on testnet 
DONE
 
6+ truffle migrate --reset --network rskmainnet
DONE

7+ Set initialSymbolPrefixSetup For rskmainnet: isSuffix = true, symbolPrefix = es
npx truffle exec ./scripts/setPrefix.js --network rskmainnet true es
DONE

8+ Update origin/master     federator-env/mainnet-ETH-RSK/
        rskmainnet.json
        config.js
        .openzeppelin/dev-30.json
        .openzeppelin/mainnet.json
	abis/
DONE

9+ Check on Remix

=============================================
ETH Mainnet Upgarde
=============================================
1+ cd into mainnet deploy:
        ETH Mainnet: MAIN-ETH-RSK

1.1+ create branch for v2 deployment:
ETH-V2-Deploy
DONE

1.2+ create branch for v3 upgrade:
ETH-V3-Upgrade-latest
DONE

2+ Change multisig required to 1
npx truffle exec ./scripts/changeRequiredSigners.js --network mainnet 1
DONE

2.1+ Add account1 as owner:
npx truffle exec ./scripts/addOwner.js --network mainnet 0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2
DONE

3+ put migration files in migration folder:
	as in upgrade-rsk-ropsten:
        1
	18
	19_1
	19
	20_1
	20
	21
DONE

3.1+ Copy contracts/*.sol files from master
DONE

3.2+ Make sure optimizer is enabled, and evmversion: istanbul
in trufle-confid.js
and in .openzeppelin./project.json
DONE

4+ Copy abis as in upgrade-rsk-ropsten
DONE

5+ Copy scripts as in upgrade-rsk-ropsten
Aligned all scripts at master and on testnet
DONE

6+ truffle migrate --reset --network mainnet
DONE

7+ Set Native Token Symbol
	npx truffle exec ./scripts/setNativeTokenSymbol.js --network mainnet ETH
DONE

8+ Create ETH Token
	npx truffle exec ./scripts/deployETHToken.js --network mainnet
DONE

9+ Allow ETH Token
	npx truffle exec ./scripts/allowToken.js --network mainnet <ETHToken>
DONE

10+ Set fee of 0.001ETH and min of 0.1ET for ETH transferH
	npx truffle exec ./scripts/setFeeAndMinPerToken.js --network mainnet <ETHToken> 1000000000000000 100000000000000000

11+ Set initialSymbolPrefixSetup
No Need -Default is for mainnet: isSuffix = false, symbolPrefix = e

12+ Update origin/master     federator-env/mainnet-ETH-RSK/
	mainnet.json
	config.js 
        .openzeppelin/dev-30.json
        .openzeppelin/mainnet.json
	abis/
DONE

13+ Check on Remix

