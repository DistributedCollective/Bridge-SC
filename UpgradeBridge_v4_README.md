ETH-RSK Upgrade to Bridge_v4 
=============================================
Follow stages in order, to make sure no transaction get stucked on the bridge while upgrading
=============================================

##### 
##### Stage 1
##### 
V4 Deployment: Bridge_v4.sol Federation.sol Erc777Converter.sol  
Deploy mock AllowTokens, this should be used ONLY in pause Bridge_v3 stage: AllowTokens.sol  

# Run migration on local
$ rm migrations/*
$ cp All_Migrations/* migrations/
$ npm run ganache (window1)
$ npm run migrate (window2)
$ ctrl-C on window1

# Run deployment on chain
$ rm migrations/*
$ cp Upgrade_Migrations_v4/* migrations/
+ Comment/Uncomment the addresses on migrations files according to chain
$ truffle migrate --reset --network <ropsten OR mainnet>




WIP ........

RSK Mainnet
===========
1+ cd into rskmainnet deploy:
        RSK Mainnet: MAIN-Restore-RSK-ETH
NA

1.1+ create branch for v2 deployment:
RSK-V2-Deploy
NA

1.2+ create branch for v3 upgrade:
RSK-V3-Upgrade-latest
NA

2+ Change multisig required to 1
npx truffle exec ./scripts/changeRequiredSigners.js --network rskmainnet 1
NA

2.1+ Add account1 as owner: 
npx truffle exec ./scripts/addOwner.js --network rskmainnet 0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2
NA

3+ put migration files in migration folder:
        as in upgrade-rsk-ropsten:
        1
        18
        19_1
        19
        20_1
        20
        21
NA

3.1+ Copy contracts/*.sol files from master
NA

3.2+ Make sure optimizer is true in trufle-config.js, and evmversion: istanbul
and false in .openzeppelin./project.json 
and evmversion: istanbul
NA

4+ Copy abis as in upgrade-rsk-ropsten
NA

5+ Copy scripts as in upgrade-rsk-ropsten
Aligned all scripts at master and on testnet 
NA
 
6+ truffle migrate --reset --network rskmainnet
DONE

7+ Set initialSymbolPrefixSetup For rskmainnet: isSuffix = true, symbolPrefix = bs
npx truffle exec ./scripts/setPrefix.js --network rskmainnet true bs
DONE

8+ Update origin/master     federator-env/mainnet-BSC-RSK/
        rskmainnet.json
        config.js
        .openzeppelin/dev-30.json
        .openzeppelin/mainnet.json
	abis/
DONE

9+ Once the bridge is up and tokens are tranffered forst time from BSC to RSK:
setFeeAndMin for side tokens

10+ Check on Remix

=============================================
BSC Mainnet 
=============================================
1+ cd into mainnet deploy:
        ETH Mainnet: MAIN-ETH-RSK

1.1+ create branch for v2 deployment:
ETH-V2-Deploy
NA

1.2+ create branch for v3 upgrade:
ETH-V3-Upgrade-latest
NA

2+ Change multisig required to 1
npx truffle exec ./scripts/changeRequiredSigners.js --network mainnet 1
NA

2.1+ Add account1 as owner:
npx truffle exec ./scripts/addOwner.js --network mainnet 0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2
NA

3+ put migration files in migration folder:
	as in upgrade-rsk-ropsten:
        1
	18
	19_1
	19
	20_1
	20
	21
NA

3.1+ Copy contracts/*.sol files from master
NA

3.2+ Make sure optimizer is enabled, and evmversion: istanbul
in trufle-config.js
and in .openzeppelin./project.json
NA

4+ Copy abis as in upgrade-rsk-ropsten
NA

5+ Copy scripts as in upgrade-rsk-ropsten
Aligned all scripts at master and on testnet
NA

6+ truffle migrate --reset --network bmainnet
DONE

7+ Set Native Token Symbol
	npx truffle exec ./scripts/setNativeTokenSymbol.js --network bmainnet BNB
DONE

8+ Create WBNBToken
	npx truffle exec ./scripts/deployBNBToken.js --network bmainnet
DONE WBNBToken = 0xB6C313a427fa911A4C9a119e80Feea0fe20E69F0

8.1+ set WBNB address with the address of deployed bnb token on stage 8
        npx truffle exec ./scripts/setWETHAddress.js --network bmainnet <WBNBToken>
DONE

9+ Allow ETH Token
	npx truffle exec ./scripts/allowToken.js --network bmainnet <WBNBToken>
DONE

10+ Set fee of 0.001ETH and min of 0.1ET for ETH transferH
	npx truffle exec ./scripts/setFeeAndMinPerToken.js --network bmainnet <WBNBToken> 10000000000000000 100000000000000000
DONE

11+ Set initialSymbolPrefixSetup For rskmainnet: isSuffix = false, symbolPrefix = b
        npx truffle exec ./scripts/setPrefix.js --network bmainnet false b
DONE

12+ allow pegged ETH token on BSC: 0x2170ed0880ac9a755fd29b2688956bd959f933f8
        npx truffle exec ./scripts/allowToken.js --network bmainnet 0x2170ed0880ac9a755fd29b2688956bd959f933f8
DONE

12.1+ setFeeAndMin for ETH pegged token: 0x2170ed0880ac9a755fd29b2688956bd959f933f8
        npx truffle exec ./scripts/setFeeAndMinPerToken.js --network bmainnet 0x2170ed0880ac9a755fd29b2688956bd959f933f8  1000000000000000 10000000000000000
DONE

13+ Update origin/master     federator-env/mainnet-BSC-RSK/
	bmainnet.json
	config.js 
        .openzeppelin/dev-30.json
        .openzeppelin/bmainnet.json
	abis/


14+ Check on Remix



======================================================================================================
ETH-RSK Brdige Upgrade
======================================================================================================
RSK Mainnet Upgarde
=============================================
1+ cd into rskmainnet deploy:
        RSK Mainnet: MAIN-Restore-RSK-ETH
DONE NA

1.1+ create branch for v2 deployment:
RSK-V2-Deploy
DONE NA

1.2+ create branch for v3 upgrade:
RSK-V3-Upgrade-latest
DONE NA

2+ Change multisig required to 1
npx truffle exec ./scripts/changeRequiredSigners.js --network rskmainnet 1
DONE NA

2.1+ Add account1 as owner: 
npx truffle exec ./scripts/addOwner.js --network rskmainnet 0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2
DONE NA

3+ put migration files in migration folder:
        as in upgrade-rsk-ropsten:
        1
        18
        19_1
        19
        20_1
        20
        21
DONE NA

3.1+ Copy contracts/*.sol files from master
DONE NA

3.2+ Make sure optimizer is true in trufle-config.js, and evmversion: istanbul
and false in .openzeppelin./project.json 
and evmversion: istanbul
DONE NA

4+ Copy abis as in upgrade-rsk-ropsten
DONE NA

5+ Copy scripts as in upgrade-rsk-ropsten
Aligned all scripts at master and on testnet 
DONE NA
 
6+ truffle migrate --reset --network rskmainnet
DONE DONE

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