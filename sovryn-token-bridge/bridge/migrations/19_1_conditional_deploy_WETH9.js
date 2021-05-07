
const WETH = artifacts.require('WETH9');
const Bridge = artifacts.require("Bridge");
const MultiSigWallet = artifacts.require("MultiSigWallet");

function shouldDeployToken(network) {
   return true
    // return !network.toLowerCase().includes('mainnet') &&
   // !network.toLowerCase().includes('kovan') &&
   // !network.toLowerCase().includes('testnet');
}

module.exports = function(deployer, networkName, accounts) {
    deployer
    .then(async () => {

        if(shouldDeployToken(networkName)) {
            const wETH = await deployer.deploy(WETH);
            //const multiSig = await MultiSigWallet.deployed();
            //const bridge = await Bridge.deployed();
            //const setWETHAddressData = bridge.contract.methods.setWETHAddress(wETH.address).encodeABI();
            //await multiSig.submitTransaction(bridge.address, 0, setWETHAddressData, { from: accounts[0] });
        }
    });
}