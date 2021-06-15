const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v3 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const allowTokens = process.argv[6];
        if (!allowTokens)
            console.error('You need to pass allowTokens');
        
        const net = process.argv[5];
        console.log("net is:"+ net);

        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (net == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 
        
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v3 = new web3.eth.Contract(Bridge_v3.abi, bridgeAddress);

        const deployer = (await web3.eth.getAccounts())[3];

        console.log(`Set allowTokens ${allowTokens} by deployer ${deployer}`);

        console.log('Bridge address', bridgeAddress);
        const allowTokensData = bridge_v3.methods.changeAllowTokens(allowTokens).encodeABI();

        const multisigAddress = await bridge_v3.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multisigAddress);
        console.log('MultiSig address', multisigAddress);
        const result = await multiSig.methods.submitTransaction(bridge_v0.address, 0, allowTokensData).send({ from: deployer, gasPrice: gasPriceNow  });

        console.log('allowTokens was updated');
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
