/*
 * Upgrade the bridge contract.
 * Run like this: npx truffle exec scripts/upgradeBridge_v5.js  --network rsktestnet scripts/Upgrade_v5_Configs/UpgradeTestnet_BscBridge_Rsktestnet_Config.json
 */
const fs = require('fs');
const bridgeAbi = require("../../abis/Bridge.json");
const proxyAdminAbi = require("../../abis/ProxyAdmin.json");
const multisigAbi = require("../../abis/MultiSigWallet.json");
const allowTokensAbi = require("../../abis/AllowTokens.json");
const federationAbi = require("../../abis/Federation.json");
const erc777ConverterAbi = require("../../abis/Erc777Converter.json");
const netType = process.argv[5];

module.exports = async callback => {
    try {
        const config = readConfig();
        console.log('Config:', config);
        
        await upgradeBridge(config);
    } catch (e) {
        callback(e);
        return;
    }
    callback();
}

function readConfig() {
    const configJsonPath = process.argv[6];
    if(!configJsonPath) {
        throw new Error('specify path to config.json, eg. `npx truffle exec scripts/upgradeBridge_v4.js  --network ropsten scripts/Upgrade_Configs/UpgradeTestnet_EthBridge_Rsktestnet_Config.json`');
    }
    if(!fs.existsSync(configJsonPath)) {
        throw new Error(`file ${configJsonPath} does not exists`);
    }
    return JSON.parse(fs.readFileSync(configJsonPath));
}

async function upgradeBridge({
    bridgeProxyAddress,
    newBridgeAddress,
    deployerAddress,
    ownerAddress,
    multiSigAddress,
    proxyAdminAddress,
    allowTokensAddress,
    federationAddress,
    erc777ConverterAddress,
    pauseAllowTokensAddress
}) {
    if(!bridgeProxyAddress || !newBridgeAddress || !deployerAddress || !ownerAddress || !multiSigAddress ||
        !proxyAdminAddress || !allowTokensAddress || !federationAddress || !erc777ConverterAddress ||
        !pauseAllowTokensAddress
      ) {
        throw new Error(
            'the following config values must be given: bridgeProxyAddress, newBridgeAddress, deployerAddress, ownerAddress, ' +
            'multiSigAddress, proxyAdminAddress, allowTokensAddress, federationAddress, erc777ConverterAddress, pauseAllowTokensAddress'
        );
    }

    let gasPrice = await web3.eth.getGasPrice();
    const net = process.argv[5];
    console.log("net is:"+ net);

    if (net == "mainnet") {
        gasPrice = 2*gasPrice;
    }

    console.log(`Gas price is: ${gasPrice}`);
    console.log(`Deployer is: ${deployerAddress}`);
    console.log(`Owner is: ${ownerAddress}`);
    console.log(`MultiSig address is: ${multiSigAddress}`);
    console.log(`AllowTokens address is: ${allowTokensAddress}`);
    console.log(`Pause Bridge with Unset AllowTkens is: ${pauseAllowTokensAddress}`)
    console.log(`Federation address is: ${federationAddress}`);
    console.log('Bridge proxy is:', bridgeProxyAddress);
    console.log('Proxy admin is:', proxyAdminAddress);
    console.log('New bridge address is:', newBridgeAddress);
    console.log('erc777Converter address is:', erc777ConverterAddress);

    const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress);
    const allowTokens = new web3.eth.Contract(allowTokensAbi, allowTokensAddress);
    const pauseAllowTokens = new web3.eth.Contract(allowTokensAbi, pauseAllowTokensAddress);
    const federation = new web3.eth.Contract(federationAbi, federationAddress);
    const erc777Converter = new web3.eth.Contract(erc777ConverterAbi, erc777ConverterAddress);
    const bridgeProxy = new web3.eth.Contract(bridgeAbi, bridgeProxyAddress);
    const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

    console.log('Owner is multisig owner?', await multiSig.methods.isOwner(ownerAddress).call());
    console.log('Bridge owner:', await bridgeProxy.methods.owner().call());
    console.log('Current Bridge implementation:', await proxyAdmin.methods.getProxyImplementation(bridgeProxyAddress).call());
    console.log('Bridge proxy admin:', await proxyAdmin.methods.getProxyAdmin(bridgeProxyAddress).call());

    const startUpgradeData = bridgeProxy.methods.startUpgrade().encodeABI();
    const pauseAllowTokensData = bridgeProxy.methods.changeAllowTokens(pauseAllowTokensAddress).encodeABI();
    const pauseData = bridgeProxy.methods.pause().encodeABI();
    const changeFederationData = bridgeProxy.methods.changeFederation(federationAddress).encodeABI();
    const changeAllowTokensData = bridgeProxy.methods.changeAllowTokens(allowTokensAddress).encodeABI();
    //const setBridgeFederationData = federation.methods.setBridge(bridgeProxyAddress).encodeABI();
    const setErc777ConverterData = bridgeProxy.methods.setErc777Converter(erc777ConverterAddress).encodeABI();
    //const setBridgeErc777ConverterData = erc777Converter.methods.setBridgeContract(bridgeProxyAddress).encodeABI();
    const unPauseData = bridgeProxy.methods.unpause().encodeABI();
    const upgradeData = proxyAdmin.methods.upgrade(bridgeProxyAddress, newBridgeAddress).encodeABI();
    const endUpgradeData = bridgeProxy.methods.endUpgrade().encodeABI();
    const unpauseAllowTokensData = bridgeProxy.methods.changeAllowTokens(allowTokensAddress).encodeABI();

    const txXpts = { from: deployerAddress, gas: 300000, gasPrice: gasPrice };
    const txOpts = { from: ownerAddress, gas: 300000, gasPrice: gasPrice };
///////////////////
// Upgrade Stages
///////////////////

// Non multiSig calls
/////////////////////

// Stage 0
// Should be executed only after former federation state was copied with storeFederationState.js

// //Set bridge address on federation
// //0.1
//     console.log('set Bridge address on Federation')
//     const setBridgeFederationResult = await federation.methods.setBridge(bridgeProxyAddress).send(
//         txXpts
//     //     {
//     //     from: deployerAddress,
//     // }
//     );
//     console.log('Result:', setBridgeFederationResult);
// // Finish initStage on federation
// // 0.2
//     console.log('Finish initStage on federation')
//     const finishInitStageFederationResult = await federation.methods.endDeploymentSetup().send(
//         txXpts
//     //     {
//     //     from: deployerAddress,
//     // }
//     );
//     console.log('Result:', finishInitStageFederationResult);
// //Transfer federation ownership to multisig
// //0.3
//     console.log('Transfer federation ownership to multisig')
//     const transferFederationToMultiSigResult = await federation.methods.transferOwnership(multiSigAddress).send(
//         txXpts
//     //     {
//     //     from: deployerAddress,
//     // }
//     );
//     console.log('Result:', transferFederationToMultiSigResult);

// //Set bridge address on erc777Converter
// //0.4
//     console.log('set Bridge address on erc777Converter')
//     const setBridgeErc777ConverterResult = await erc777Converter.methods.setBridgeContract(bridgeProxyAddress).send(
//         txXpts
//     //     {
//     //     from: deployerAddress,
//     // }
//     );
//     console.log('Result:', setBridgeErc777ConverterResult);

// //Transfer erc777Converter ownership to multisig
// //0.5
//     console.log('Transfer erc777Converter ownership to multisig')
//     const transferERC777ConverterToMultiSigResult = await erc777Converter.methods.transferOwnership(multiSigAddress).send(
//         txXpts
//     //     {
//     //     from: deployerAddress,
//     // }
//     );
//     console.log('Result:', transferERC777ConverterToMultiSigResult);

//Transfer allowTokens ownership to multisig
//0.6
    console.log('Transfer allowTokens ownership to multisig')
    const transerAllowTokensToMultiSigResult = await allowTokens.methods.transferOwnership(multiSigAddress).send(
        txXpts
    //     {
    //     from: deployerAddress,
    // }
    );
    console.log('Result:', transerAllowTokensToMultiSigResult);

// MultiSig calls
/////////////////////

// Stage A
// Should be executed for both main-chain and side-chain
// StartUpgrade
// set AllowTokens (only for upgrading v3 to v4, starting from v4 we don't need pauseAllowTokensData step)

//1
    // console.log('Calling startUpgrade with multisig')
    // console.log(startUpgradeData)
    // const startUpgradeResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, startUpgradeData).send(txOpts);
    // console.log('Result:', startUpgradeResult);
//  //2
//    if( netType== "mainnet" ||  netType== "ropsten" ) {
//         console.log('Pause the bridge Calling changeAllowTokens with multisig')
//         console.log(pauseAllowTokensData)
//         const pauseAllowtokensResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, pauseAllowTokensData).send(txOpts);
//         console.log('Result:', pauseAllowtokensResult);
//    }

// Stage B
// Should be executed for both main-chain and side-chain
// After 40 minutes, after all blocks till the stageA execution block were processed 

//3 
// PauseBridge  - to disable _acceptTransfer
    // console.log('Calling pause with multisig')
    // console.log(pauseData)
    // const pauseResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, pauseData).send(txOpts);
    // console.log('Result:', pauseResult);
    
// Stage C
// Should be executed for both main-chain and side-chain    
// Upgrade brigde
// Change federation address on the Bridge
// Set erc777Converter address on the Bridge

//4
    // console.log('Calling upgrade with multisig')
    // console.log(upgradeData);
    // const upgradeResult = await multiSig.methods.submitTransaction(proxyAdminAddress, 0, upgradeData).send(txOpts);
    // console.log('Result:', upgradeResult);
// //5
//     console.log('change Federation address on the bridge')
//     console.log(changeFederationData);
//     const changeFedAddressResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, changeFederationData).send(txOpts);
//     console.log('Result:', changeFedAddressResult);
// //6
//     console.log('set erc777Converter address on the bridge')
//     console.log(setErc777ConverterData);
//     const setErc777ConverterResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, setErc777ConverterData).send(txOpts);
//     console.log('Result:', setErc777ConverterResult);

// //7
    console.log('change AllowTokens address on the bridge')
    console.log(changeAllowTokensData);
    const changeAllowTokensAddressResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, changeAllowTokensData).send(txOpts);
    console.log('Result:', changeAllowTokensAddressResult);

// Stage D  
// Should be executed for both main-chain and side-chain    
// EndUpgrade
// Set original AllowTokens (only for upgrading v3 to v4, starting from v4 we don't need this set AlloTokens)
// UnPause

//7
    // console.log('Calling endUpgrade with multisig')
    // console.log(endUpgradeData);
    // const endUpgradeResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, endUpgradeData).send(txOpts);
    // console.log('Result:', endUpgradeResult);
// //8
//     if( netType== "mainnet" ||  netType== "ropsten" ) {
//          console.log('UnPause the bridge Calling changeAllowTokens with multisig')
//          console.log(unpauseAllowTokensData);
//          const unpauseAllowtokensResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, unpauseAllowTokensData).send(txOpts);
//          console.log('Result:', unpauseAllowtokensResult);
//     }
//9    
    // console.log('Calling unpause with multisig')
    // console.log(unPauseData);
    // const unPauseResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, unPauseData).send(txOpts);
    // console.log('Result:', unPauseResult);

    console.log('All done.')
}