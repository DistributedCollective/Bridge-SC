const Bridge = artifacts.require("Bridge_v0");
const SideTokenFactory = artifacts.require('SideTokenFactory');

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async ()=> {
            if (networkName === 'rsktestnet') {
                // This migration got messed up on rsktestnet so it's redone in migration 12
                return;
            }
            const sideTokenFactory = await SideTokenFactory.deployed();
            const bridge = await Bridge.deployed();
            console.log("Bridge Address", bridge.address)
            await sideTokenFactory.transferPrimary(bridge.address);
        });
}