const Federation = artifacts.require("Federation");
const Bridge = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const proxyAdminAbi = require('../../abis/ProxyAdmin.json');

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const federation = await deployer.deploy(Federation, [accounts[0]], 1);

            const multiSig = await MultiSigWallet.deployed();
            const bridge = await Bridge.deployed();

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

            await federation.setBridge(bridge.address);
            await federation.transferOwnership(multiSig.address);

            const changeFederationData = bridge.contract.methods.changeFederation(federation.address).encodeABI();
            await multiSig.submitTransaction(bridge.address, 0, changeFederationData, { from: accounts[0] });
        });
};
