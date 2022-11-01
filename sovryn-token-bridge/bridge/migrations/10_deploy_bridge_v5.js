//const { scripts, ConfigManager } = require('@openzeppelin/cli');
const BridgeProxy = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Utils = artifacts.require("Utils");
const proxyAdminAbi = require('../../abis/ProxyAdmin.json');
const bridgeAbi = require('../../abis/Bridge.json');

async function _upgradeBridge(bridge, networkName, accounts) {
    const multiSig = await MultiSigWallet.deployed();
    const bridgeProxy = await BridgeProxy.deployed();

    if (networkName === 'soliditycoverage') {
        return bridge;
    }
    let jsonName = networkName;
    const chainId = await web3.eth.net.getId();
    if((chainId >= 30 && chainId <=33) || chainId == 5777 || chainId == 56 || chainId == 97 || chainId === 11155111) {
        jsonName = `dev-${chainId}`;
    }
    const networkConfig = require(`../.openzeppelin/${jsonName}.json`);

    const proxyAdminAddress = networkConfig.proxyAdmin.address;
    const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

    const upgradeBridgeData = proxyAdmin.methods.upgrade(bridgeProxy.address, bridge._address).encodeABI();
    await multiSig.submitTransaction(proxyAdmin.options.address, 0, upgradeBridgeData, { from: accounts[0] });
}

module.exports = async function(deployer, networkName, accounts) {
    await deployer.deploy(Utils);
    await deployer.link(Utils, BridgeImpl);
    const bridgeI = await deployer.deploy(BridgeImpl);
    const bridgeAddr = bridgeI.address;

    
    const bridge = new web3.eth.Contract(bridgeAbi, bridgeAddr);

    console.log("Upgrading Bridge")
    await _upgradeBridge(bridge, networkName, accounts);
};