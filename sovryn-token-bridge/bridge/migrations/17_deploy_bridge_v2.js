//const { scripts, ConfigManager } = require('@openzeppelin/cli');
const BridgeProxy = artifacts.require("Bridge_v1");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Utils = artifacts.require("Utils");
const Auth = artifacts.require("Auth");
const proxyAdminAbi = require('../../abis/ProxyAdmin.json');
const bridgeAbi = require('../../abis/Bridge.json');

async function _upgradeBridge(bridge, auth, networkName, accounts) {
    const multiSig = await MultiSigWallet.deployed();
    const bridgeProxy = await BridgeProxy.deployed();

    if (networkName === 'soliditycoverage') {
        return bridge;
    }
    let jsonName = networkName;
    const chainId = await web3.eth.net.getId();
    if((chainId >= 30 && chainId <=33) || chainId == 5777) {
        jsonName = `dev-${chainId}`;
    }
    const networkConfig = require(`../.openzeppelin/${jsonName}.json`);

    const proxyAdminAddress = networkConfig.proxyAdmin.address;
    const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

    const upgradeBridgeData = proxyAdmin.methods.upgrade(bridgeProxy.address, bridge._address).encodeABI();
    await multiSig.submitTransaction(proxyAdmin.options.address, 0, upgradeBridgeData, { from: accounts[0] });

    const setAuthData = bridge.methods.setAuth(auth.address).encodeABI();
    await multiSig.submitTransaction(proxyAdmin.options.address, 0, setAuthData, { from: accounts[0] });
}

module.exports = async function(deployer, networkName, accounts) {
    await deployer.link(Utils, BridgeImpl);
    const bridgeAddr = (await deployer.deploy(BridgeImpl)).address;
    const bridge = new web3.eth.Contract(bridgeAbi, bridgeAddr);
    const auth = await deployer.deploy(Auth);
    await _upgradeBridge(bridge, auth, networkName, accounts);
};
