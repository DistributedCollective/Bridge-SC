//const { scripts, ConfigManager } = require('@openzeppelin/cli');
const BridgeProxy = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Utils = artifacts.require("Utils");
const proxyAdminAbi = require('../../abis/ProxyAdmin.json');
const bridgeAbi = require('../../abis/Bridge.json');
const multisigAbi = require('../../abis/MultiSigWallet.json');

async function _upgradeBridge(bridge, networkName, accounts) {
    
    deployer = accounts[0];
    const multiSigAddress = "0x314d9163dd122368b3c6329b081d2400a9f238d1";
    const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress, {from: deployer});

    //const multiSig = await MultiSigWallet.deployed();
    //const bridgeProxy = await BridgeProxy.deployed();
    const bridgeProxy_address = "0x4Ff0E83e443467a1723FC2F0B74C91f31CEacB83";

    if (networkName === 'soliditycoverage') {
        return bridge;
    }
    let jsonName = networkName;
    const chainId = await web3.eth.net.getId();
    if((chainId >= 30 && chainId <=33) || chainId == 5777 || chainId == 56 || chainId == 97) {
        jsonName = `dev-${chainId}`;
    }
    const networkConfig = require(`../.openzeppelin/${jsonName}.json`);

    const proxyAdminAddress = networkConfig.proxyAdmin.address;
    const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

    const upgradeBridgeData = proxyAdmin.methods.upgrade(bridgeProxy_address, bridge._address).encodeABI();
    //await multiSig.submitTransaction(proxyAdmin.options.address, 0, upgradeBridgeData, { from: accounts[0] });
    await multiSig.methods.submitTransaction(proxyAdmin.options.address, 0, upgradeBridgeData).send({ from: accounts[0] ,gas: 300000});
    
}

module.exports = async function(deployer, networkName, accounts) {
    await deployer.deploy(Utils);
    await deployer.link(Utils, BridgeImpl);
    const bridgeI = await deployer.deploy(BridgeImpl);
    //await bridgeI.deployed();
    const bridgeAddr = bridgeI.address;

    
    
    //await deployer.link(Utils, BridgeImpl);
    //const bridgeAddr = (await deployer.deploy(BridgeImpl)).address;
    const bridge = new web3.eth.Contract(bridgeAbi, bridgeAddr);
    await _upgradeBridge(bridge, networkName, accounts);
};
/*
const BridgeProxy = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Utils = artifacts.require("Utils");
const proxyAdminAbi = require('../../abis/ProxyAdmin.json');


module.exports = function(deployer, networkName, accounts) {
    return deployer.deploy(Utils)
    .then( () => {
        return deployer.link(Utils, BridgeImpl);
    }).then( () => {
        return deployer.deploy(BridgeImpl);
    }).then(async (bridge) => {
        const multiSig = await MultiSigWallet.deployed();
        const bridgeProxy = await BridgeProxy.deployed();
        // const { network, txParams } = await ConfigManager.initNetworkConfiguration({ network: networkName, from: accounts[0] });

        // await ozDeploy({ network, txParams }, 'BridgeImpl', 'Bridge');
        if (networkName === 'soliditycoverage') {
            return bridge;
        }
        let jsonName = networkName;
        const chainId = await web3.eth.net.getId();
        if((chainId >= 30 && chainId <=33) || chainId == 5777 || chainId == 56 || chainId == 97) {
            jsonName = `dev-${chainId}`;
        }
        const networkConfig = require(`../.openzeppelin/${jsonName}.json`);

        const proxyAdminAddress = networkConfig.proxyAdmin.address;
        const proxyAdmin = new web3.eth.Contract(proxyAdminAbi, proxyAdminAddress);

        const data = proxyAdmin.methods.upgrade(bridgeProxy.address, bridge.address).encodeABI();
        await multiSig.submitTransaction(proxyAdmin.options.address, 0, data, { from: accounts[0] });
      });
};
*/