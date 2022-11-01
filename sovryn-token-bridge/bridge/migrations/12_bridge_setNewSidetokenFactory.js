//const { scripts, ConfigManager } = require('@openzeppelin/cli');
const SideTokenFactory = artifacts.require('SideTokenFactory');
const BridgeProxy = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");


module.exports = async function(deployer, networkName, accounts) {
    if (networkName !== 'rsktestnet') {
        // This migration is only needed for rsktestnet
        return;
    }
    const multiSig = await MultiSigWallet.deployed();
    const bridgeProxy = await BridgeProxy.deployed();
    const bridgeImpl = await BridgeImpl.deployed();
    await deployer.deploy(SideTokenFactory);
    const sideTokenFactory = await SideTokenFactory.deployed();
    console.log("New SideTokenFactory Address", sideTokenFactory.address)

    console.log("Changing sidetoken factory")
    const data = await bridgeImpl.contract.methods.changeSideTokenFactory(sideTokenFactory.address).encodeABI();
    let tx = await multiSig.submitTransaction(bridgeProxy.address, 0, data, { from: accounts[0] });
    console.log("TX", tx.tx);
    console.log("Setting primary")
    tx = await sideTokenFactory.transferPrimary(bridgeProxy.address);
    console.log("TX", tx.tx);
};