const MultiSigWallet = artifacts.require("MultiSigWallet");
const AllowTokens = artifacts.require("AllowTokens");
const Bridge = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");


module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const multiSig = await MultiSigWallet.deployed();
            const bridge = await Bridge.deployed();
            const bridgeImpl = new web3.eth.Contract(BridgeImpl.abi, bridge.address);
            let data = bridgeImpl.methods.startUpgrade().encodeABI();
            await multiSig.submitTransaction(bridge.address, 0, data, { from: accounts[0] });

            
            
            return deployer.deploy(AllowTokens, multiSig.address);
        });
};