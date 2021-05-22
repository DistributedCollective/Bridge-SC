const AllowTokens = artifacts.require("AllowTokens");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v1 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const tokenToRemove = process.argv[6];
        if (!tokenToRemove)
            console.error('You need to pass the token address');
        console.log(`You will remove the token ${tokenToRemove}`);

        const net = process.argv[5];
        console.log("net is:"+ net);

        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (net == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 
        
        //const deployer = (await web3.eth.getAccounts())[0];
        const deployer = (await web3.eth.getAccounts())[3];
        console.log("deployer is " + deployer);

        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v1 = new web3.eth.Contract(Bridge_v1.abi, bridgeAddress);

        console.log(await bridge_v1.methods.allowTokens().call());
        const allowTokensAddress = await bridge_v1.methods.allowTokens().call();
        const allowTokens = await AllowTokens.at(allowTokensAddress);
        console.log(`Configuring AllowTokens contract ${allowTokens.address}`);

        const multiSigAddress = await allowTokens.contract.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        const tokenToRemoveData =
            allowTokens.contract.methods.removeAllowedToken(tokenToRemove).encodeABI();

        console.log(tokenToRemoveData);
        const result = await multiSig.methods.submitTransaction(allowTokens.address, 0, tokenToRemoveData).send({ from: deployer, gasPrice: gasPriceNow });
        console.log(result)

    } catch (e) {
        callback(e);
    }
    callback();
}
