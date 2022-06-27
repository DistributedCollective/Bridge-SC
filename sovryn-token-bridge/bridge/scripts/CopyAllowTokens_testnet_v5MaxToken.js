const fs = require('fs');
const AbisObject = require("./BridgeTestnetAddresses_v5MaxToken").abisObject;
const AbisObjectV5 = require("./BridgeTestnetAddresses_v5MaxToken").abisObjectV5;

const BscBSCV5Config = require("./BridgeTestnetAddresses_v5MaxToken").bscBSCV5Config;
const BscBSCConfig = require("./BridgeTestnetAddresses_v5MaxToken").bscBSCConfig;
const RskBSCConfig = require("./BridgeTestnetAddresses_v5MaxToken").rskBSCConfig;
const EthETHConfig = require("./BridgeTestnetAddresses_v5MaxToken").ethETHConfig;
const RskETHConfig = require("./BridgeTestnetAddresses_v5MaxToken").rskETHConfig;
const BtestnetStableCoins = require("./BridgeTestnetAddresses_v5MaxToken").btestnetStableCoins;
const TestnetStableCoins = require("./BridgeTestnetAddresses_v5MaxToken").testnetStableCoins;
const RskbsctestnetStableCoins = require("./BridgeTestnetAddresses_v5MaxToken").rskbsctestnetStableCoins;
const RskethtestnetStableCoins = require("./BridgeTestnetAddresses_v5MaxToken").rskethtestnetStableCoins;
const RsktestnetTokens = require("./BridgeTestnetAddresses_v5MaxToken").rsktestnetTokens;
const BtestnetETHToken = require("./BridgeTestnetAddresses_v5MaxToken").btestnetETHToken;
const RskbsctestnetETHToken = require("./BridgeTestnetAddresses_v5MaxToken").rskbsctestnetETHToken;
const BtestnetBNB = require("./BridgeTestnetAddresses_v5MaxToken").btestnetBNB;
const RsktestnetRBTC = require("./BridgeTestnetAddresses_v5MaxToken").rsktestnetRBTC;
const RskbsctestnetBNB = require("./BridgeTestnetAddresses_v5MaxToken").rskbsctestnetBNB;
const BscbscbtestnetRBTC = require("./BridgeTestnetAddresses_v5MaxToken").bscbscbtestnetRBTC;
const TestnetSOV = require("./BridgeTestnetAddresses_v5MaxToken").testnetSOV;
const BtestnetSOV = require("./BridgeTestnetAddresses_v5MaxToken").btestnetSOV;


const deployer= "0x12D90403733b6DD1f88240C773a6613331e60bCF";

module.exports = async callback => {
    try {

        const netType = process.argv[5];
        const bridgeType = process.argv[6];
        const tokenType = process.argv[7];
        const enableMethod = process.argv[8];
        const input0 = process.argv[9];
        const input1 = process.argv[10];
        const input2 = process.argv[11];

        
        if( bridgeType == "h" || bridgeType == "help" ) {
            throw new Error('npx truffle exec ./scripts/BridgeControl.js --network <net> <bridgeType> <tokenType> <enableMethod> <input0> <input1> <input2>\n' + 
            'net: testnet, btestnet, rsktestnet, ropsten, btestnet, rsktestnet\n' +
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
            'npx truffle exec ./scripts/BridgeControl.js --network rsktestnet bsc bnb "setFeeAndMinPerToken" "" 10000000000000000 100000000000000000\n' +
            'npx truffle exec ./scripts/BridgeControl.js --network rsktestnet bsc "" "removeOwner" "0xdc83580abf622ec75f69b56ddf945dd6cdbf53d2" "" ""');   
        }
     
        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (netType == "testnet") {
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
                RsktestnetTokens.SOV_RskTestnet[31].address,
            ];
        };
        if(netType == "btestnet") {
            if(tokenType == "stable") {
                tokens = [
                    BtestnetStableCoins.DAI_BTestnet[97].address,
                    BtestnetStableCoins.USDT_BTestnet[97].address,
                    BtestnetStableCoins.USDC_BTestnet[97].address,
                    BtestnetStableCoins.BUSD_BTestnet[97].address,
                ];
                decimals = [
                    BtestnetStableCoins.DAI_BTestnet[97].decimals,
                    BtestnetStableCoins.USDT_BTestnet[97].decimals,
                    BtestnetStableCoins.USDC_BTestnet[97].decimals,
                    BtestnetStableCoins.BUSD_BTestnet[97].decimals,
                ];
            }
            else if(tokenType == "eth") {
                tokens = [
                    BtestnetETHToken.ETH_BTestnet[97].address
                ];
                decimals = [
                    BtestnetETHToken.ETH_BTestnet[97].decimals
                ];
            }
            else if(tokenType == "bnb") {
                tokens = [
                    BtestnetBNB.BNB_BTestnet[97].address
                ];
                decimals = [
                    BtestnetBNB.BNB_BTestnet[97].decimals
                ];
            }
            else if(tokenType == "rbtc") {
                tokens = [
                    BscbscbtestnetRBTC.RBTC_BscBSCTestnet[97].address
                ];
                decimals = [
                    BscbscbtestnetRBTC.RBTC_BscBSCTestnet[97].decimals
                ];
            }
            else if(tokenType == "sov") {
                tokens = [
                    BtestnetSOV.SOV_BTestnet[97].address
                ];
                decimals = [
                    BtestnetSOV.SOV_BTestnet[97].decimals
                ];
            };

            bridgeAddress = BscBSCConfig.bridge;
            federationAddress = BscBSCConfig.federation;
            multiSigAddress= BscBSCConfig.multiSig;
            allowTokensAddress= BscBSCConfig.allowTokens;
            erc777ConverterAddress= BscBSCConfig.erc777Converter;

            allowTokensV5Address= BscBSCV5Config.allowTokens;
        }
        else if(netType == "ropsten") {
            if(tokenType == "stable") {
                tokens = [
                    TestnetStableCoins.DAI_Testnet[3].address,
                    TestnetStableCoins.USDT_Testnet[3].address,
                    TestnetStableCoins.USDC_Testnet[3].address,
                ];
                decimals = [
                    TestnetStableCoins.DAI_Testnet[3].decimals,
                    TestnetStableCoins.USDT_Testnet[3].decimals,
                    TestnetStableCoins.USDC_Testnet[3].decimals,
                ];
            }
            else if(tokenType == "sov") {
                tokens = [
                    TestnetSOV.SOV_Testnet[3].address
                ];
                decimals = [
                    TestnetSOV.SOV_Testnet[3].decimals
                ];
            };
            bridgeAddress = EthETHConfig.bridge;
            federationAddress = EthETHConfig.federation;
            multiSigAddress= EthETHConfig.multiSig;
            allowTokensAddress= EthETHConfig.allowTokens;
            erc777ConverterAddress= EthETHConfig.erc777Converter;

        }
        else if(netType == "rsktestnet"){
            if(tokenType == "sov") {
                tokens = [
                    RsktestnetTokens.SOV_RskTestnet[31].address.toLowerCase()
                ];
                decimals = [
                    RsktestnetTokens.SOV_RskTestnet[31].decimals
                ];

            };
            if(tokenType == "rbtc") {
                tokens = [
                    RsktestnetRBTC.RBTC_RskTestnet[31].address.toLowerCase()
                ];
                decimals = [
                    RsktestnetRBTC.RBTC_RskTestnet[31].decimals
                ];
            };
            if(bridgeType == "bsc"){
                bridgeAddress = RskBSCConfig.bridge;
                federationAddress = RskBSCConfig.federation;
                multiSigAddress= RskBSCConfig.multiSig;
                allowTokensAddress= RskBSCConfig.allowTokens;
                erc777ConverterAddress= RskBSCConfig.erc777Converter;

                if(tokenType == "stable") {
                    tokens = [
                        RskbsctestnetStableCoins.DAI_RskBSCTestnet[31].address.toLowerCase(),
                        RskbsctestnetStableCoins.USDT_RskBSCTestnet[31].address.toLowerCase(),
                        RskbsctestnetStableCoins.USDC_RskBSCTestnet[31].address.toLowerCase(),
                        RskbsctestnetStableCoins.BUSD_RskBSCTestnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskbsctestnetStableCoins.DAI_RskBSCTestnet[31].decimals,
                        RskbsctestnetStableCoins.USDT_RskBSCTestnet[31].decimals,
                        RskbsctestnetStableCoins.USDC_RskBSCTestnet[31].decimals,
                        RskbsctestnetStableCoins.BUSD_RskBSCTestnet[31].decimals,
                    ];
                }
                else if(tokenType == "eth") {
                    tokens = [
                        RskbsctestnetETHToken.ETH_RskBSCTestnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskbsctestnetETHToken.ETH_RskBSCTestnet[31].decimals
                    ];

                }
                else if(tokenType == "bnb") {
                    tokens = [
                        RskbsctestnetBNB.BNB_RskBSCTestnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskbsctestnetBNB.BNB_RskBSCTestnet[31].decimals
                    ];
                };
    
            }
            else if(bridgeType == "eth") {
                bridgeAddress = RskETHConfig.bridge;
                federationAddress = RskETHConfig.federation;
                multiSigAddress= RskETHConfig.multiSig;
                allowTokensAddress= RskETHConfig.allowTokens;
                erc777ConverterAddress= RskETHConfig.erc777Converter;

                if(tokenType == "stable") {
                    tokens = [
                        RskethtestnetStableCoins.DAI_RskETHTestnet[31].address.toLowerCase(),
                        RskethtestnetStableCoins.USDT_RskETHTestnet[31].address.toLowerCase(),
                        RskethtestnetStableCoins.USDC_RskETHTestnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskethtestnetStableCoins.DAI_RskETHTestnet[31].decimals,
                        RskethtestnetStableCoins.USDT_RskETHTestnet[31].decimals,
                        RskethtestnetStableCoins.USDC_RskETHTestnet[31].decimals
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