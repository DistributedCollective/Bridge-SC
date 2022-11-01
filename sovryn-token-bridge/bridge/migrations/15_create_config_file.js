//We are actually gona use Bridge_v1 but truffle only knows the address of the proxy by using Bridge_v0
const Bridge = artifacts.require("Bridge_v0");
const Federation = artifacts.require('Federation');
const AllowTokens = artifacts.require("AllowTokens");
const MultiSigWallet = artifacts.require("MultiSigWallet");

const fs = require('fs');

module.exports = function(deployer, networkName, accounts) {
    deployer
    .then(async () => {
        if (networkName === 'soliditycoverage') {
            return;
        }
        const bridge = await Bridge.deployed();
        const federation = await Federation.deployed();
        const multiSig = await MultiSigWallet.deployed();
        const allowTokens = await AllowTokens.deployed();
        const currentProvider = deployer.networks[networkName];
        const config = {
            bridge: bridge.address.toLowerCase(),
            federation: federation.address.toLowerCase(),
            multiSig: multiSig.address.toLowerCase(),
            allowTokens: allowTokens.address.toLowerCase()
        };
        if (currentProvider.host) {
            let host = currentProvider.host.indexOf('http') == 0 ? '': 'http://';
            host += currentProvider.host + ((currentProvider.port) ? `:${currentProvider.port}` : '');
            config.host = host;
        } else {
            config.host = '';
        }
        config.fromBlock = await web3.eth.getBlockNumber();
        fs.writeFileSync(`../federator/config/${networkName}.json`, JSON.stringify(config, null, 4));
    });
};
