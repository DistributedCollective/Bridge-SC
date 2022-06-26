const fs = require('fs');
const AbisObject = require("./BridgeMainnetAddresses_v5MaxToken").abisObject;

const BscBSCV5Config = require("./BridgeMainnetAddresses_v5MaxToken").bscBSCV5Config;
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
const BmainnetBNB = require("./BridgeMainnetAddresses_v5MaxToken").bmainnetBNB;
const RskmainnetRBTC = require("./BridgeMainnetAddresses_v5MaxToken").rskmainnetRBTC;
const RskbscmainnetBNB = require("./BridgeMainnetAddresses_v5MaxToken").rskbscmainnetBNB;
const BscbscbmainnetRBTC = require("./BridgeMainnetAddresses_v5MaxToken").bscbscbmainnetRBTC;
const MainnetSOV = require("./BridgeMainnetAddresses_v5MaxToken").mainnetSOV;
const BmainnetSOV = require("./BridgeMainnetAddresses_v5MaxToken").bmainnetSOV;


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
            'net: mainnet, bmainnet, rskmainnet, ropsten, bmainnet, rskmainnet\n' +
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
                RskmainnetTokens.SOV_RskMainnet[31].address,
            ];
        };
        if(netType == "bmainnet") {
            if(tokenType == "stable") {
                tokens = [
                    BmainnetStableCoins.DAI_BMainnet[97].address,
                    BmainnetStableCoins.USDT_BMainnet[97].address,
                    BmainnetStableCoins.USDC_BMainnet[97].address,
                    BmainnetStableCoins.BUSD_BMainnet[97].address,
                ];
                decimals = [
                    BmainnetStableCoins.DAI_BMainnet[97].decimals,
                    BmainnetStableCoins.USDT_BMainnet[97].decimals,
                    BmainnetStableCoins.USDC_BMainnet[97].decimals,
                    BmainnetStableCoins.BUSD_BMainnet[97].decimals,
                ];
            }
            else if(tokenType == "eth") {
                tokens = [
                    BmainnetETHToken.ETH_BMainnet[97].address
                ];
                decimals = [
                    BmainnetETHToken.ETH_BMainnet[97].decimals
                ];
            }
            else if(tokenType == "bnb") {
                tokens = [
                    BmainnetBNB.BNB_BMainnet[97].address
                ];
                decimals = [
                    BmainnetBNB.BNB_BMainnet[97].decimals
                ];
            }
            else if(tokenType == "rbtc") {
                tokens = [
                    BscbscbmainnetRBTC.RBTC_BscBSCMainnet[97].address
                ];
                decimals = [
                    BscbscbmainnetRBTC.RBTC_BscBSCMainnet[97].decimals
                ];
            }
            else if(tokenType == "sov") {
                tokens = [
                    BmainnetSOV.SOV_BMainnet[97].address
                ];
                decimals = [
                    BmainnetSOV.SOV_BMainnet[97].decimals
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
                    MainnetStableCoins.DAI_Mainnet[3].address,
                    MainnetStableCoins.USDT_Mainnet[3].address,
                    MainnetStableCoins.USDC_Mainnet[3].address,
                ];
                decimals = [
                    MainnetStableCoins.DAI_Mainnet[3].decimals,
                    MainnetStableCoins.USDT_Mainnet[3].decimals,
                    MainnetStableCoins.USDC_Mainnet[3].decimals,
                ];
            }
            else if(tokenType == "sov") {
                tokens = [
                    MainnetSOV.SOV_Mainnet[3].address
                ];
                decimals = [
                    MainnetSOV.SOV_Mainnet[3].decimals
                ];
            };
            bridgeAddress = EthETHConfig.bridge;
            federationAddress = EthETHConfig.federation;
            multiSigAddress= EthETHConfig.multiSig;
            allowTokensAddress= EthETHConfig.allowTokens;
            erc777ConverterAddress= EthETHConfig.erc777Converter;

        }
        else if(netType == "rskmainnet"){
            if(tokenType == "sov") {
                tokens = [
                    RskmainnetTokens.SOV_RskMainnet[31].address.toLowerCase()
                ];
                decimals = [
                    RskmainnetTokens.SOV_RskMainnet[31].decimals
                ];

            };
            if(tokenType == "rbtc") {
                tokens = [
                    RskmainnetRBTC.RBTC_RskMainnet[31].address.toLowerCase()
                ];
                decimals = [
                    RskmainnetRBTC.RBTC_RskMainnet[31].decimals
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
                        RskbscmainnetStableCoins.DAI_RskBSCMainnet[31].address.toLowerCase(),
                        RskbscmainnetStableCoins.USDT_RskBSCMainnet[31].address.toLowerCase(),
                        RskbscmainnetStableCoins.USDC_RskBSCMainnet[31].address.toLowerCase(),
                        RskbscmainnetStableCoins.BUSD_RskBSCMainnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskbscmainnetStableCoins.DAI_RskBSCMainnet[31].decimals,
                        RskbscmainnetStableCoins.USDT_RskBSCMainnet[31].decimals,
                        RskbscmainnetStableCoins.USDC_RskBSCMainnet[31].decimals,
                        RskbscmainnetStableCoins.BUSD_RskBSCMainnet[31].decimals,
                    ];
                }
                else if(tokenType == "eth") {
                    tokens = [
                        RskbscmainnetETHToken.ETH_RskBSCMainnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskbscmainnetETHToken.ETH_RskBSCMainnet[31].decimals
                    ];

                }
                else if(tokenType == "bnb") {
                    tokens = [
                        RskbscmainnetBNB.BNB_RskBSCMainnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskbscmainnetBNB.BNB_RskBSCMainnet[31].decimals
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
                        RskethmainnetStableCoins.DAI_RskETHMainnet[31].address.toLowerCase(),
                        RskethmainnetStableCoins.USDT_RskETHMainnet[31].address.toLowerCase(),
                        RskethmainnetStableCoins.USDC_RskETHMainnet[31].address.toLowerCase()
                    ];
                    decimals = [
                        RskethmainnetStableCoins.DAI_RskETHMainnet[31].decimals,
                        RskethmainnetStableCoins.USDT_RskETHMainnet[31].decimals,
                        RskethmainnetStableCoins.USDC_RskETHMainnet[31].decimals
                    ];
                };
            };
        };

        console.log("bridgeAddress: "+ bridgeAddress);
        console.log("federationAddress: "+ federationAddress);
        console.log("multiSigAddress: "+ multiSigAddress);
        console.log("allowTokensAddress: "+ allowTokensAddress);
        console.log("erc777ConverterAddress: "+ erc777ConverterAddress);
        const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress, {from: deployer});
        const bridge =  new web3.eth.Contract(bridgeAbi, bridgeAddress, {from: deployer});
        const allowTokens =  new web3.eth.Contract(AllowTokensAbi, allowTokensAddress, {from: deployer});
        const federation =  new web3.eth.Contract(federationAbi, federationAddress, {from: deployer});
        const erc777Converter =  new web3.eth.Contract(erc777ConverterAbi, erc777ConverterAddress, {from: deployer});

        let functionData;
        let adjustedFee;
        let adjustedMin;

        let exeFunctionsPromises = tokens.map(async (token, index) => {
        // Bridge control
            if(enableMethod == "pause") {
                smartContract = "bridge";
                functionData = bridge.methods
                .pause()
                .encodeABI();
            }
            else if(enableMethod == "changeAllowTokens") {
                smartContract = "bridge";
                functionData = bridge.methods
                .changeAllowTokens(input0)
                .encodeABI();
            }
            else if(enableMethod == "setNativeTokenSymbol") {
                smartContract = "bridge";
                functionData = bridge.methods
                .setNativeTokenSymbol(input0)
                .encodeABI();
            }
            else if(enableMethod == "initialSymbolPrefixSetup") {
                smartContract = "bridge";
                functionData = bridge.methods
                .initialSymbolPrefixSetup(input0, input1)
                .encodeABI();
            }
            else if(enableMethod == "setWETHAddress") {
                smartContract = "bridge";
                functionData = bridge.methods
                .setWETHAddress(input0)
                .encodeABI();
            }
            else if(enableMethod == "setRevokeTransaction") {
                smartContract = "bridge";
                functionData = bridge.methods
                .setRevokeTransaction(input0)
                .encodeABI();
            }
            else if(enableMethod == "setBridgeReceiverStatus") {
                smartContract = "bridge";
                functionData = bridge.methods
                .setBridgeReceiverStatus(input0, input1)
                .encodeABI();
            }
        // MultiSig control
            if(enableMethod == "changeRequirement") {
                smartContract = "multiSig";
                functionData = multiSig.methods
                .changeRequirement(input0)
                .encodeABI();
            }
            else if(enableMethod == "removeOwner") {
                smartContract = "multiSig";
                functionData = multiSig.methods
                .removeOwner(input0)
                .encodeABI();
            }
            else if(enableMethod == "addOwner") {
                smartContract = "multiSig";
                functionData = multiSig.methods
                .addOwner(input0)
                .encodeABI();
            }
        // AllowTokens control
            else if(enableMethod == "addAllowedToken") {
                smartContract = "allowTokens";
                functionData = allowTokens.methods
                .addAllowedToken(token)
                .encodeABI();
            }
            else if(enableMethod == "removeAllowedToken") {
                smartContract = "allowTokens";
                functionData = allowTokens.methods
                .removeAllowedToken(token)
                .encodeABI();
            }
            else if(enableMethod == "setFeeAndMinPerToken") {
                smartContract = "allowTokens";
                adjustedFee = input1/(10**(18-decimals[index]));
                adjustedMin = input2/(10**(18-decimals[index]));
                console.log("adjustedFee, adjustedMin "+ adjustedFee  + " , " + adjustedMin); 
                if(decimals[index]== 18){
                    adjustedFee =input1;
                    adjustedMin = input2;
                }
                functionData = allowTokens.methods
                .setFeeAndMinPerToken(token, adjustedFee, adjustedMin)
                .encodeABI();
            }
            else if(enableMethod == "setMaxPerToken") {
                smartContract = "allowTokens";
                adjustedMax = input1/(10**(18-decimals[index]));
                console.log("adjustedMax "+ adjustedMax); 
                if(decimals[index]== 18){
                    adjustedMax =input1;
                }
                functionData = allowTokens.methods
                .setMaxPerToken(token, adjustedMax)
                .encodeABI();
            }
            else if(enableMethod == "setMaxTokensAllowed") {
                smartContract = "allowTokens";
                functionData = allowTokens.methods
                .setMaxTokensAllowed(input0)
                .encodeABI();
            }
            else if(enableMethod == "changeDailyLimit") {
                smartContract = "allowTokens";
                functionData = allowTokens.methods
                .changeDailyLimit(input0)
                .encodeABI();
            }
        // Federation control
            else if(enableMethod == "removeMember") {
                smartContract = "federation";
                functionData = federation.methods
                .removeMember(input0)
                .encodeABI();
            }
            else if(enableMethod == "addMember") {
                smartContract = "federation";
                functionData = federation.methods
                .addMember(input0)
                .encodeABI();
            }
            else if(enableMethod == "setRevokeTransactionAndVote") {
                smartContract = "federation";
                functionData = federation.methods
                .setRevokeTransactionAndVote(input0)
                .encodeABI();
            }
        // erc777Converter control
            // else if(enableMethod == "removeMember") {
            //     smartContract = "federation";
            //     functionData = federation.methods
            //     .removeMember(input0)
            //     .encodeABI();
            // }
            // else if(enableMethod == "addMember") {
            //     smartContract = "federation";
            //     functionData = federation.methods
            //     .addMember(input0)
            //     .encodeABI();
            // }          
        console.log(`${functionData}`);
        let result;
        if(smartContract == "bridge") {
            result = await multiSig.methods
            .submitTransaction(bridgeAddress, 0, functionData)
            .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        }
        else if(smartContract == "multiSig") {
            result = await multiSig.methods
            .submitTransaction(multiSigAddress, 0, functionData)
            .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        }
        else if(smartContract == "allowTokens") {
            result = await multiSig.methods
            .submitTransaction(allowTokensAddress, 0, functionData)
            .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        }
        else if(smartContract == "federation") {
            result = await multiSig.methods
            .submitTransaction(federationAddress, 0, functionData)
            .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        };



        // if(enableMethod == "changeRequirement") {
        //     result = await multiSig.methods
        //       .submitTransaction(multiSigAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "removeOwner") {
        //     result = await multiSig.methods
        //       .submitTransaction(multiSigAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "addOwner") {
        //     result = await multiSig.methods
        //       .submitTransaction(multiSigAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "addAllowedToken") {
        //     result = await multiSig.methods
        //       .submitTransaction(allowTokensAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "removeAllowedToken") {
        //     result = await multiSig.methods
        //       .submitTransaction(allowTokensAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "setFeeAndMinPerToken"){
        //     result = await multiSig.methods
        //       .submitTransaction(allowTokensAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "removeMember"){
        //     result = await multiSig.methods
        //       .submitTransaction(federationAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
        // else if(enableMethod == "addMember"){
        //     result = await multiSig.methods
        //       .submitTransaction(federationAddress, 0, functionData)
        //       .send({ from: deployer ,gas: 300000, gasPrice: gasPriceNow });
        // }
              console.log(result);
        });

     await Promise.all(exeFunctionsPromises);
    } catch (e) {
      callback(e);
    }
    callback();
    console.log('All done.')
};    