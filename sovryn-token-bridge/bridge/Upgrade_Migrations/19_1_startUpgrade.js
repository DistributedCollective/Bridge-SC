const Bridge = artifacts.require("Bridge_v0");
const Bridge_v2 = artifacts.require("Bridge_v2");
const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const multiSig = await MultiSigWallet.deployed();
            const bridge = await Bridge.deployed();
            const bridge_v2 = new web3.eth.Contract(Bridge_v2.abi, bridge.address);
            
            const startUpgradeData = bridge_v2.methods.startUpgrade().encodeABI();
            await multiSig.submitTransaction(bridge.address, 0, startUpgradeData, { from: accounts[0] });
        });
};
