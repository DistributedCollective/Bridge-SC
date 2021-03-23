
const MainToken = artifacts.require('MainToken');

function shouldDeployToken(network) {
    return !network.toLowerCase().includes('mainnet')&&
    !network.toLowerCase().includes('kovan') &&
    !network.toLowerCase().includes('testnet');
}

module.exports = function(deployer, networkName, accounts) {
    deployer
    .then(() => {
        if(shouldDeployToken(networkName)) {
            return deployer.deploy(MainToken, 'MAIN', 'MAIN', 18, web3.utils.toWei('1000'));
        }
    });
}