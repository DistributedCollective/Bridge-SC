const Federation = artifacts.require("Federation");
const Bridge = artifacts.require("Bridge_v0");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const feds = [
    "0xD8bc75a79f6d63fE6E1307139d3BfDc0Bd090e35",
    "0x5fC4D8b1F96A916683954272721Cfe96ED5a3953"
    ];
module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const federation = await deployer.deploy(Federation, [feds[0]], 1);

            const multiSig = await MultiSigWallet.deployed();
            const bridge = await Bridge.deployed();

            await federation.setBridge(bridge.address);
            await federation.transferOwnership(multiSig.address);

            const changeFederationData = bridge.contract.methods.changeFederation(federation.address).encodeABI();
            await multiSig.submitTransaction(bridge.address, 0, changeFederationData, { from: accounts[0] });
        });
};
