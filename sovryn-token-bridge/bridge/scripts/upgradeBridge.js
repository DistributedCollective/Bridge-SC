/*
 *
 * NOTE!! this script doesn't actually need to be used, since everything should be done by Truffle migrations!!
 *
 * Upgrade the bridge contract.
 * Run like this: truffle exec scripts/upgradeBridge.js ./myConfig.json
 */
const fs = require('fs');
const bridgeAbi = require("../../abis/Bridge.json");
const proxyAdminAbi = require("../../abis/ProxyAdmin.json");
const multisigAbi = require("../../abis/MultiSigWallet.json");
const allowTokensAbi = require("../../abis/AllowTokens.json");
const federationAbi = require("../../abis/Federation.json");
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
        throw new Error('specify path to config.json, eg. `npx truffle exec scripts/upgradeBridge.js --network ropsten scripts/ropstenDEVConfig.json`');
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
    multiSigAddress,
    proxyAdminAddress,
    allowTokensAddress,
    federationAddress,
    pauseAllowTokensAddress
}) {
    if(!bridgeProxyAddress || !newBridgeAddress || !deployerAddress || !multiSigAddress || !proxyAdminAddress || !allowTokensAddress || !federationAddress || !pauseAllowTokensAddress) {
        throw new Error(
            'the following config values must be given: bridgeProxyAddress, newBridgeAddress, deployerAddress, ' +
            'multiSigAddress, proxyAdminAddress, allowTokensAddress, federationAddress, pauseAllowTokensAddress'
        );
    }

    let gasPrice = await web3.eth.getGasPrice();
    console.log(`Gas price is: ${gasPrice}`);
    console.log(`Deployer is: ${deployerAddress}`);
    console.log(`MultiSig address is: ${multiSigAddress}`);
    console.log(`AllowTokens address is: ${allowTokensAddress}`);
    console.log(`Pause Bridge with fresh AllowTkens is: ${pauseAllowTokensAddress}`)
    console.log(`Federation address is: ${federationAddress}`);
    console.log('Bridge proxy is:', bridgeProxyAddress);
    console.log('Proxy admin is:', proxyAdminAddress);
    console.log('New bridge address is:', newBridgeAddress);

    const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress);
    const allowTokens = new web3.eth.Contract(allowTokensAbi, allowTokensAddress);
    const pauseAllowTokens = new web3.eth.Contract(allowTokensAbi, pauseAllowTokensAddress);
    const federation = new web3.eth.Contract(federationAbi, federationAddress);
    const bridgeProxy = new web3.eth.Contract(bridgeAbi, bridgeProxyAddress);
    const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

    console.log('Deployer is multisig owner?', await multiSig.methods.isOwner(deployerAddress).call());
    console.log('Bridge owner:', await bridgeProxy.methods.owner().call());
    console.log('Current Bridge implementation:', await proxyAdmin.methods.getProxyImplementation(bridgeProxyAddress).call());
    console.log('Bridge proxy admin:', await proxyAdmin.methods.getProxyAdmin(bridgeProxyAddress).call());

    const startUpgradeData = bridgeProxy.methods.startUpgrade().encodeABI();
    const pauseData = bridgeProxy.methods.pause().encodeABI();
    const unPauseData = bridgeProxy.methods.unpause().encodeABI();
    const pauseAllowTokensData = bridgeProxy.methods.changeAllowTokens(pauseAllowTokensAddress).encodeABI();
    const upgradeData = proxyAdmin.methods.upgrade(bridgeProxyAddress, newBridgeAddress).encodeABI();
    const endUpgradeData = bridgeProxy.methods.endUpgrade().encodeABI();
    const unpauseAllowTokens = bridgeProxy.methods.changeAllowTokens(allowTokensAddress).encodeABI();

    const txOpts = { from: deployerAddress, gas: 300000, gasPrice: gasPrice };
///////////////////
// Upgrade Stages
///////////////////

// Stage A
// Should be executed for both main-chain and side-chain
// StartUpgrade
// set AllowTokens (only for upgrading v3 to v4, starting from v4 we don't need this set AlloTokens)
    console.log('Calling startUpgrade with multisig')
    const startUpgradeResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, startUpgradeData).send(txOpts);
    console.log('Result:', startUpgradeResult);

    console.log('Pause the bridge Calling changeAllowTokens with multisig')
    const pauseAllowtokensResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, pauseAllowTokensData).send(txOpts);
    console.log('Result:', pauseAllowtokensResult);

// Stage B
// Should be executed for both main-chain and side-chain
// After 20-30 minutes, after all blocks till the stageA execution block were processed 
// PauseBridge  - to disable _acceptTransfer
    // console.log('Calling pause with multisig')
    // const pauseResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, pauseData).send(txOpts);
    // console.log('Result:', pauseResult);
    
// Stage C
// Should be executed for both main-chain and side-chain    
// Upgrade brigde
// EndUpgrade
// Set original AllowTokens (only for upgrading v3 to v4, starting from v4 we don't need this set AlloTokens)
// UnPause
    // console.log('Calling upgrade with multisig')
    // const upgradeResult = await multiSig.methods.submitTransaction(proxyAdminAddress, 0, upgradeData).send(txOpts);
    // console.log('Result:', upgradeResult);

    // console.log('Calling endUpgrade with multisig')
    // const endUpgradeResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, endUpgradeData).send(txOpts);
    // console.log('Result:', endUpgradeResult);

    // console.log('UnPause the bridge Calling changeAllowTokens with multisig')
    // const unpauseAllowtokensResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, unpauseAllowTokens).send(txOpts);
    // console.log('Result:', unpauseAllowtokensResult);
    
    // console.log('Calling pause with multisig')
    // const unPauseResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, unPauseData).send(txOpts);
    // console.log('Result:', pauseResult);

    console.log('All done.')
}