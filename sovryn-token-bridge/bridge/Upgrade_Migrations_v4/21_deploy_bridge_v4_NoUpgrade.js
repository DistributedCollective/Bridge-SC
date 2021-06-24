const BridgeImpl = artifacts.require("Bridge");
const Utils = artifacts.require("Utils");

module.exports = async function(deployer, networkName, accounts) {
    await deployer.deploy(Utils);
    await deployer.link(Utils, BridgeImpl);
    const bridgeI = await deployer.deploy(BridgeImpl);
    //await bridgeI.deployed();
    const bridgeAddr = bridgeI.address;

    console.log("bridgeAddr: " + bridgeAddr);
};