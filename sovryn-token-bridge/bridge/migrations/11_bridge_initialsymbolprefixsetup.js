//const { scripts, ConfigManager } = require('@openzeppelin/cli');
const BridgeProxy = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");


module.exports = async function(deployer, networkName, accounts) {
    let prefixOrSuffix;
    let isSuffix;
    if (networkName === 'sepolia') {
        prefixOrSuffix = 'e';
        isSuffix = false;
    } else if(networkName === 'rsktestnet') {
        prefixOrSuffix = 'es';
        isSuffix = true;
    } else {
        throw new Error(`Unknown network ${networkName}`);
    }

    const multiSig = await MultiSigWallet.deployed();
    const bridgeProxy = await BridgeProxy.deployed();
    const bridgeImpl = await BridgeImpl.deployed();

    console.log("Doing initialSymbolPrefixSetup")
    const prefixSetupData = await bridgeImpl.contract.methods.initialSymbolPrefixSetup(isSuffix, prefixOrSuffix).encodeABI();
    const tx = await multiSig.submitTransaction(bridgeProxy.address, 0, prefixSetupData, { from: accounts[0] });
    console.log("TX", tx);
};