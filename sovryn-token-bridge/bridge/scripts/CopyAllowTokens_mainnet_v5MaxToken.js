const fs = require('fs');
const AbisObject = require("./BridgeMainnetAddresses_v5MaxToken").abisObject;
const AbisObjectV5 = require("./BridgeMainnetAddresses_v5MaxToken").abisObjectV5;

const BscBSCV5Config = require("./BridgeMainnetAddresses_v5MaxToken").bscBSCV5Config;
const RskBSCV5Config = require("./BridgeMainnetAddresses_v5MaxToken").rskBSCV5Config;
const EthETHV5Config = require("./BridgeMainnetAddresses_v5MaxToken").ethETHV5Config;
const RskETHV5Config = require("./BridgeMainnetAddresses_v5MaxToken").rskETHV5Config;

const BscBSCConfig = require("./BridgeMainnetAddresses_v5MaxToken").bscBSCConfig;
const RskBSCConfig = require("./BridgeMainnetAddresses_v5MaxToken").rskBSCConfig;
const EthETHConfig = require("./BridgeMainnetAddresses_v5MaxToken").ethETHConfig;
const RskETHConfig = require("./BridgeMainnetAddresses_v5MaxToken").rskETHConfig;
const BmainnetStableCoins = require("./BridgeMainnetAddresses_v5MaxToken").bmainnetStableCoins;
const MainnetStableCoins = require("./BridgeMainnetAddresses_v5MaxToken").mainnetStableCoins;
const RskbscmainnetStableCoins = require("./BridgeMainnetAddresses_v5MaxToken").rskbscmainnetStableCoins;
const RskethmainnetStableCoins = require("./BridgeMainnetAddresses_v5MaxToken").rskethmainnetStableCoins;
const RskmainnetTokens = require("./BridgeMainnetAddresses_v5MaxToken").rskmainnetTokens;
const BmainnetETHToken = require("./BridgeMainnetAddresses_v5MaxToken").bmainnetETHToken;
const RskbscmainnetETHToken = require("./BridgeMainnetAddresses_v5MaxToken").rskbscmainnetETHToken;
const RskethmainnetETHToken = require("./BridgeMainnetAddresses_v5MaxToken").rskmainnetTokensETH;
const BmainnetBNB = require("./BridgeMainnetAddresses_v5MaxToken").bmainnetBNB;
const RskmainnetRBTC = require("./BridgeMainnetAddresses_v5MaxToken").rskmainnetRBTC;
const RskbscmainnetBNB = require("./BridgeMainnetAddresses_v5MaxToken").rskbscmainnetBNB;
const BscbscbmainnetRBTC = require("./BridgeMainnetAddresses_v5MaxToken").bscbscbmainnetRBTC;
const MainnetSOV = require("./BridgeMainnetAddresses_v5MaxToken").mainnetSOV;
const BmainnetSOV = require("./BridgeMainnetAddresses_v5MaxToken").bmainnetSOV;
const MainnetETH = require("./BridgeMainnetAddresses_v5MaxToken").mainnetETH;


//const deployer= "0x12D90403733b6DD1f88240C773a6613331e60bCF";
const deployer= "0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2";

module.exports = async callback => {
    try {

        const netType = process.argv[5];
        const bridgeType = process.argv[6];
        const tokenType = process.argv[7];
        const enableMethod = process.argv[8];
        const input0 = process.argv[9];
        const input1 = process.argv[10];
        const input2 = process.argv[11];

console.log(netType + " " +bridgeType );
        
        if( bridgeType == "h" || bridgeType == "help" ) {
            throw new Error('npx truffle exec ./scripts/BridgeControl.js --network <net> <bridgeType> <tokenType> <enableMethod> <input0> <input1> <input2>\n' + 
            'net: mainnet, bmainnet, rskmainnet, ropsten, btestnet, rsktestnet\n' +
            'bridgeType: bsc, eth\n'+
            'tokenType: "", sov, stable, eth, bnb, rbtc\n'+
            'enableMethod: name of the function to call\n'+
            'input0: first input to function\n'+
            'input1: second input to function\n'+
            'input2: third input to function\n' +
            'enableMethod list:\n' +
            'Bridge: pause changeAllowTokens setNativeTokenSymbol initialSymbolPrefixSetup setWETHAddress setRevokeTransaction setBridgeReceiverStatus\n' +
            'MultiSig: changeRequirement removeOwner addOwner\n' +
            'AllowTokens: addAllowedToken removeAllowedToken setFeeAndMinPerToken setMaxTokensAllowed changeDailyLimit setMaxPerToken\n' +
            'Federation: removeMember addMember setRevokeTransactionAndVote\n\n' +
            'Example: \n' + 
            'npx truffle exec ./scripts/BridgeControl.js --network rskmainnet bsc bnb "setFeeAndMinPerToken" "" 10000000000000000 100000000000000000\n' +
            'npx truffle exec ./scripts/BridgeControl.js --network rskmainnet bsc "" "removeOwner" "0xdc83580abf622ec75f69b56ddf945dd6cdbf53d2" "" ""');   
        }
     
        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (netType == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 

        const bridgeAbi = AbisObject.bridgeABI;
        const federationAbi = AbisObject.federationABI;
        const multisigAbi = AbisObject.multiSigABI;
        const AllowTokensAbi = AbisObject.allowTokensABI;
        const erc777ConverterAbi = AbisObject.erc777ConverterABI;

        const AllowTokensV5Abi = AbisObjectV5.allowTokensV5ABI;

        let bridgeAddress;
        let federationAddress;
        let multiSigAddress;
        let allowTokensAddress;
        let erc777ConverterAddress;
        
        let allowTokensV5Address;

        let tokens;
        let decimals;

        let smartContract;
        if(tokenType == "") {
            tokens = [
                RskmainnetTokens.SOV_RskMainnet[30].address,
            ];
        };
        if(netType == "bmainnet") {
            if(tokenType == "stable") {
                tokens = [
                    BmainnetStableCoins.DAI_BMainnet[56].address,
                    BmainnetStableCoins.USDT_BMainnet[56].address,
                    BmainnetStableCoins.USDC_BMainnet[56].address,
                    BmainnetStableCoins.BUSD_BMainnet[56].address,
                ];
                decimals = [
                    BmainnetStableCoins.DAI_BMainnet[56].decimals,
                    BmainnetStableCoins.USDT_BMainnet[56].decimals,
                    BmainnetStableCoins.USDC_BMainnet[56].decimals,
                    BmainnetStableCoins.BUSD_BMainnet[56].decimals,
                ];
            }
            else if(tokenType == "eth") {
                tokens = [
                    BmainnetETHToken.ETH_BMainnet[56].address
                ];
                decimals = [
                    BmainnetETHToken.ETH_BMainnet[56].decimals
                ];
            }
            else if(tokenType == "bnb") {
                tokens = [
                    BmainnetBNB.BNB_BMainnet[56].address
                ];
                decimals = [
                    BmainnetBNB.BNB_BMainnet[56].decimals
                ];
            }
            else if(tokenType == "rbtc") {
                tokens = [
                    BscbscbmainnetRBTC.RBTC_BscBSCMainnet[56].address
                ];
                decimals = [
                    BscbscbmainnetRBTC.RBTC_BscBSCMainnet[56].decimals
                ];
            }
            else if(tokenType == "sov") {
                tokens = [
                    BmainnetSOV.SOV_BMainnet[56].address
                ];
                decimals = [
                    BmainnetSOV.SOV_BMainnet[56].decimals
                ];
            };

            bridgeAddress = BscBSCConfig.bridge;
            federationAddress = BscBSCConfig.federation;
            multiSigAddress= BscBSCConfig.multiSig;
            allowTokensAddress= BscBSCConfig.allowTokens;
            erc777ConverterAddress= BscBSCConfig.erc777Converter;

            allowTokensV5Address= BscBSCV5Config.allowTokens;
        }
        else if(netType == "mainnet") {
            if(tokenType == "stable") {
                tokens = [
                    MainnetStableCoins.DAI_Mainnet[1].address,
                    MainnetStableCoins.USDT_Mainnet[1].address,
                    MainnetStableCoins.USDC_Mainnet[1].address,
                ];
                decimals = [
                    MainnetStableCoins.DAI_Mainnet[1].decimals,
                    MainnetStableCoins.USDT_Mainnet[1].decimals,
                    MainnetStableCoins.USDC_Mainnet[1].decimals,
                ];
            }
            else if(tokenType == "sov") {
                tokens = [
                    MainnetSOV.SOV_Mainnet[1].address
                ];
                decimals = [
                    MainnetSOV.SOV_Mainnet[1].decimals
                ];
            }
            else if(tokenType == "eth") {
                tokens = [
                    MainnetETH.ETH_Mainnet[1].address
                ];
                decimals = [
                    MainnetETH.ETH_Mainnet[1].decimals
                ];
            };
            bridgeAddress = EthETHConfig.bridge;
            federationAddress = EthETHConfig.federation;
            multiSigAddress= EthETHConfig.multiSig;
            allowTokensAddress= EthETHConfig.allowTokens;
            erc777ConverterAddress= EthETHConfig.erc777Converter;
            allowTokensV5Address= EthETHV5Config.allowTokens;

        }
        else if(netType == "rskmainnet"){
            if(tokenType == "sov") {
                tokens = [
                    RskmainnetTokens.SOV_RskMainnet[30].address.toLowerCase()
                ];
                decimals = [
                    RskmainnetTokens.SOV_RskMainnet[30].decimals
                ];

            };
            if(tokenType == "rbtc") {
                tokens = [
                    RskmainnetRBTC.RBTC_RskMainnet[30].address.toLowerCase()
                ];
                decimals = [
                    RskmainnetRBTC.RBTC_RskMainnet[30].decimals
                ];
            };
            if(bridgeType == "BSC"){
                console.log(netType + " " +bridgeType );

                bridgeAddress = RskBSCConfig.bridge;
                federationAddress = RskBSCConfig.federation;
                multiSigAddress= RskBSCConfig.multiSig;
                allowTokensAddress= RskBSCConfig.allowTokens;
                erc777ConverterAddress= RskBSCConfig.erc777Converter;
                allowTokensV5Address= RskBSCV5Config.allowTokens;

                if(tokenType == "stable") {
                    tokens = [
                        RskbscmainnetStableCoins.DAI_RskBSCMainnet[30].address.toLowerCase(),
                        RskbscmainnetStableCoins.USDT_RskBSCMainnet[30].address.toLowerCase(),
                        RskbscmainnetStableCoins.USDC_RskBSCMainnet[30].address.toLowerCase(),
                        RskbscmainnetStableCoins.BUSD_RskBSCMainnet[30].address.toLowerCase()
                    ];
                    decimals = [
                        RskbscmainnetStableCoins.DAI_RskBSCMainnet[30].decimals,
                        RskbscmainnetStableCoins.USDT_RskBSCMainnet[30].decimals,
                        RskbscmainnetStableCoins.USDC_RskBSCMainnet[30].decimals,
                        RskbscmainnetStableCoins.BUSD_RskBSCMainnet[30].decimals,
                    ];
                }
                else if(tokenType == "eth") {
                    tokens = [
                        RskbscmainnetETHToken.ETH_RskBSCMainnet[30].address.toLowerCase()
                    ];
                    decimals = [
                        RskbscmainnetETHToken.ETH_RskBSCMainnet[30].decimals
                    ];

                }
                else if(tokenType == "bnb") {
                    tokens = [
                        RskbscmainnetBNB.BNB_RskBSCMainnet[30].address.toLowerCase()
                    ];
                    decimals = [
                        RskbscmainnetBNB.BNB_RskBSCMainnet[30].decimals
                    ];
                };
    
            }
            else if(bridgeType == "ETH") {
                bridgeAddress = RskETHConfig.bridge;
                federationAddress = RskETHConfig.federation;
                multiSigAddress= RskETHConfig.multiSig;
                allowTokensAddress= RskETHConfig.allowTokens;
                erc777ConverterAddress= RskETHConfig.erc777Converter;
                allowTokensV5Address= RskETHV5Config.allowTokens;

                if(tokenType == "stable") {
                    tokens = [
                        RskethmainnetStableCoins.DAI_RskETHMainnet[30].address.toLowerCase(),
                        RskethmainnetStableCoins.USDT_RskETHMainnet[30].address.toLowerCase(),
                        RskethmainnetStableCoins.USDC_RskETHMainnet[30].address.toLowerCase()
                    ];
                    decimals = [
                        RskethmainnetStableCoins.DAI_RskETHMainnet[30].decimals,
                        RskethmainnetStableCoins.USDT_RskETHMainnet[30].decimals,
                        RskethmainnetStableCoins.USDC_RskETHMainnet[30].decimals
                    ];
                }
                else if(tokenType == "eth") {
                    tokens = [
                        RskethmainnetETHToken.ETH_RskMainnet[30].address.toLowerCase()
                    ];
                    decimals = [
                        RskethmainnetETHToken.ETH_RskMainnet[30].decimals
                    ];

                };
            };
        };

        console.log("bridgeAddress: "+ bridgeAddress);
        console.log("federationAddress: "+ federationAddress);
        console.log("multiSigAddress: "+ multiSigAddress);
        console.log("allowTokensAddress: "+ allowTokensAddress);
        console.log("allowTokensV5Address: "+ allowTokensV5Address);
        console.log("erc777ConverterAddress: "+ erc777ConverterAddress);
        const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress, {from: deployer});
        const bridge =  new web3.eth.Contract(bridgeAbi, bridgeAddress, {from: deployer});
        const allowTokens =  new web3.eth.Contract(AllowTokensAbi, allowTokensAddress, {from: deployer});
        const federation =  new web3.eth.Contract(federationAbi, federationAddress, {from: deployer});
        const erc777Converter =  new web3.eth.Contract(erc777ConverterAbi, erc777ConverterAddress, {from: deployer});

        const allowTokensV5 =  new web3.eth.Contract(AllowTokensV5Abi, allowTokensV5Address, {from: deployer});

        let functionData;
        let adjustedFee;
        let adjustedMin;

        // let MaxAllowed = await allowTokensV5.methods.getMaxTokensAllowed().call();
        // let MinAllowed = await allowTokensV5.methods.getMinTokensAllowed().call();
        // let dailyLimit = await allowTokensV5.methods.dailyLimit().call();

        // console.log("MaxAllowed: " + MaxAllowed + " MinAllowed: " + MinAllowed + " dailyLimit: " + dailyLimit);

        // let resultG = await allowTokens.methods.setMaxTokensAllowed(MaxAllowed).send({
        //     from: deployer});
        // console.log(resultG);
        // resultG = await allowTokens.methods.setMinTokensAllowed(MinAllowed).send({
        //     from: deployer});
        // console.log(resultG);
        // resultG = await allowTokens.methods.changeDailyLimit(dailyLimit).send({
        //     from: deployer});
        // console.log(resultG);        

        const exeFunctionsPromises = tokens.map(async (token, index) => {
                let Tfee = await allowTokensV5.methods.getFeePerToken(token).call();
                let Tmin = await allowTokensV5.methods.getMinPerToken(token).call();
                console.log(tokenType + " " + token + " Fee: " + Tfee + " Min: " + Tmin);        
            
                const result = await allowTokens.methods.setFeeAndMinPerToken(token, Tfee, Tmin).send({
                from: deployer});
                const result1 = await allowTokens.methods.addAllowedToken(token).send({
                    from: deployer});

                console.log(result);
                console.log(result1);

        });

      await Promise.all(exeFunctionsPromises);
    } catch (e) {
      callback(e);
    }
    callback();
    console.log('All done.')
};    