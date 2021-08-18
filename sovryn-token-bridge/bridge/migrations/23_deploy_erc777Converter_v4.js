const Erc777Converter = artifacts.require("Erc777Converter");
const Bridge = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const erc777Converter = await deployer.deploy(Erc777Converter);

            const multiSig = await MultiSigWallet.deployed();
            const bridge = await Bridge.deployed();

            const bridgeImpl = new web3.eth.Contract(BridgeImpl.abi, bridge.address);
            let data = bridgeImpl.methods.setErc777Converter(erc777Converter.address).encodeABI();
            await multiSig.submitTransaction(bridge.address, 0, data, { from: accounts[0] });

        });
};
