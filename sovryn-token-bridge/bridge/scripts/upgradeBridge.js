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
    const configJsonPath = process.argv[5];
    if(!configJsonPath) {
        throw new Error('specify path to config.json, eg. `truffle exec scripts/upgradeBridge.js ./myConfig.json`');
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
}) {
    if(!bridgeProxyAddress || !newBridgeAddress || !deployerAddress || !multiSigAddress || !proxyAdminAddress) {
        throw new Error(
            'the following config values must be given: bridgeProxyAddress, newBridgeAddress, deployerAddress, ' +
            'multiSigAddress, proxyAdminAddress'
        );
    }

    let gasPrice = await web3.eth.getGasPrice();
    console.log(`Gas price is: ${gasPrice}`);
    console.log(`Deployer is: ${deployerAddress}`);
    console.log(`MultiSig address is: ${multiSigAddress}`);
    console.log('Bridge proxy is:', bridgeProxyAddress);
    console.log('Proxy admin is:', proxyAdminAddress);
    console.log('New bridge address is:', newBridgeAddress);

    const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress);
    const bridgeProxy = new web3.eth.Contract(bridgeAbi, bridgeProxyAddress);
    const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

    console.log('Deployer is multisig owner?', await multiSig.methods.isOwner(deployerAddress).call());
    console.log('Bridge owner:', await bridgeProxy.methods.owner().call());
    console.log('Current Bridge implementation:', await proxyAdmin.methods.getProxyImplementation(bridgeProxyAddress).call());
    console.log('Bridge proxy admin:', await proxyAdmin.methods.getProxyAdmin(bridgeProxyAddress).call());

    const startUpgradeData = bridgeProxy.methods.startUpgrade().encodeABI();
    const upgradeData = proxyAdmin.methods.upgrade(bridgeProxyAddress, newBridgeAddress).encodeABI();
    const endUpgradeData = bridgeProxy.methods.endUpgrade().encodeABI();

    const txOpts = { from: deployerAddress, gas: 300000, gasPrice: gasPrice };

    console.log('Calling startUpgrade with multisig')
    const startUpgradeResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, startUpgradeData).send(txOpts);
    console.log('Result:', startUpgradeResult);

    console.log('Calling upgrade with multisig')
    const upgradeResult = await multiSig.methods.submitTransaction(proxyAdminAddress, 0, upgradeData).send(txOpts);
    console.log('Result:', upgradeResult);

    console.log('Calling endUpgrade with multisig')
    const endUpgradeResult = await multiSig.methods.submitTransaction(bridgeProxyAddress, 0, endUpgradeData).send(txOpts);
    console.log('Result:', endUpgradeResult);

    console.log('All done.')
}