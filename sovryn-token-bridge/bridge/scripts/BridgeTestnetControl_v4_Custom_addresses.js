const fs = require('fs');
// const bridgeAbi = require("../../abis/Bridge.json");
// const federationAbi = require("../../abis/Federation.json");
// const multisigAbi = require("../../abis/MultiSigWallet.json");
// const AllowTokensAbi = require("../../abis/AllowTokens.json");
const AbisObject = require("./BridgeTestnetNEWAddresses").abisObject;
const BscBSCConfig = require("./BridgeTestnetNEWAddresses").bscBSCConfig;
const RskBSCConfig = require("./BridgeTestnetNEWAddresses").rskBSCConfig;
const EthETHConfig = require("./BridgeTestnetNEWAddresses").ethETHConfig;
const RskETHConfig = require("./BridgeTestnetNEWAddresses").rskETHConfig;
const BtestnetStableCoins = require("./BridgeTestnetNEWAddresses").btestnetStableCoins;
const TestnetStableCoins = require("./BridgeTestnetNEWAddresses").testnetStableCoins;
const RskbsctestnetStableCoins = require("./BridgeTestnetNEWAddresses").rskbsctestnetStableCoins;
const RskethtestnetStableCoins = require("./BridgeTestnetNEWAddresses").rskethtestnetStableCoins;
const RsktestnetTokens = require("./BridgeTestnetNEWAddresses").rsktestnetTokens;
const BtestnetETHToken = require("./BridgeTestnetNEWAddresses").btestnetETHToken;
const RskbsctestnetETHToken = require("./BridgeTestnetNEWAddresses").rskbsctestnetETHToken;
const BtestnetBNB = require("./BridgeTestnetNEWAddresses").btestnetBNB;
const RskbsctestnetBNB = require("./BridgeTestnetNEWAddresses").rskbsctestnetBNB;
const TestnetSOV = require("./BridgeTestnetNEWAddresses").testnetSOV;
const BtestnetSOV = require("./BridgeTestnetNEWAddresses").btestnetSOV;


const deployer= "0x12D90403733b6DD1f88240C773a6613331e60bCF";
const erc777Converteraddr = "0x1322A861272d4d2F5d90C37eFFf2D3Ff4C7C0ba4";

// 23_deploy_erc777Converter_v3.js
// ===============================

//    Deploying 'Erc777Converter'
//    ---------------------------
//    > transaction hash:    0x9ac63edb5c90332a43d153382c948683be85f7912c9e79d6f6acf419d7a85c8c
//    > Blocks: 2            Seconds: 36
//    > contract address:    0x1322A861272d4d2F5d90C37eFFf2D3Ff4C7C0ba4


module.exports = async callback => {
    try {

        const netType = process.argv[5];
        const bridgeType = process.argv[6];
        const tokenType = process.argv[7];
        const enableMethod = process.argv[8];
        const input0 = process.argv[9];
        const input1 = process.argv[10];
        const input2 = process.argv[11];

        
        if( bridgeType == "h") {
            throw new Error('npx truffle exec ./scripts/BridgeControl.js --network <net> <bridgeType> <tokenType> <enableMethod> <input0> <input1> <input2>\n' + 
            'net: testnet, btestnet, rsktestnet, ropsten, btestnet, rsktestnet\n' +
            'bridgeType: bsc, eth\n'+
            'tokenType: "", sov, stable, eth, bnb\n'+
            'enableMethod: name of the function to call\n'+
            'input0: first input to function\n'+
            'input1: second input to function\n'+
            'input2: third input to function\n' +
            'enableMethod list:\n' +
            'Bridge: pause changeAllowTokens setNativeTokenSymbol initialSymbolPrefixSetup setWETHAddress\n' +
            'MultiSig: changeRequirement removeOwner addOwner\n' +
            'AllowTokens: addAllowedToken removeAllowedToken setFeeAndMinPerToken setMaxTokensAllowed changeDailyLimit\n' +
            'Federation: removeMember addMember\n\n' +
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
        
        let bridgeAddress;
        let federationAddress;
        let multiSigAddress;
        let allowTokensAddress;
        
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
            if(bridgeType == "bsc"){
                bridgeAddress = RskBSCConfig.bridge;
                federationAddress = RskBSCConfig.federation;
                multiSigAddress= RskBSCConfig.multiSig;
                allowTokensAddress= RskBSCConfig.allowTokens;
    
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
        
        const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress, {from: deployer});
        const bridge =  new web3.eth.Contract(bridgeAbi, bridgeAddress, {from: deployer});
        const allowTokens =  new web3.eth.Contract(AllowTokensAbi, allowTokensAddress, {from: deployer});
        const federation =  new web3.eth.Contract(federationAbi, federationAddress, {from: deployer});
        
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
            else if(enableMethod == "setErc777Converter") {
                smartContract = "bridge";
                functionData = bridge.methods
                .setErc777Converter(erc777Converteraddr)
                .encodeABI();
            }
            else if(enableMethod == "setRevokeTransaction") {
                smartContract = "bridge";
                functionData = bridge.methods
                .setRevokeTransaction(input0)
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
            else if(enableMethod == "addMemsetRevokeTransactionAndVoteber") {
                smartContract = "federation";
                functionData = federation.methods
                .setRevokeTransactionAndVote(input0)
                .encodeABI();
            }

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