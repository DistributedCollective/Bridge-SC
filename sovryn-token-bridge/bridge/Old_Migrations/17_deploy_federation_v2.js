const Federation = artifacts.require("Federation_v2");
const Bridge = artifacts.require("Bridge_v0");
const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const federation = await deployer.deploy(Federation, [accounts[0]], 1);

            const multiSig = await MultiSigWallet.deployed();
            const bridge = await Bridge.deployed();

            await federation.setBridge(bridge.address);
            await federation.transferOwnership(multiSig.address);

            const changeFederationData = bridge.contract.methods.changeFederation(federation.address).encodeABI();
            await multiSig.submitTransaction(bridge.address, 0, changeFederationData, { from: accounts[0] });
        });
};
