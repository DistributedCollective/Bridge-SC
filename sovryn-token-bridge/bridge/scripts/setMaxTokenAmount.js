const AllowTokens = artifacts.require("AllowTokens");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v1 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const maxTokenAmount = process.argv[6];
        if (!maxTokenAmount) {
            console.error('You need to pass the max token amount allowed');
            callback();
            return;
        }
        //const maximumTokenAmount = Number.parseInt(maxTokenAmount);
        const net = process.argv[5];
        console.log("net is:"+ net);

        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (net == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 
        
        const maximumTokenAmount = web3.utils.toWei(maxTokenAmount);
        
        //const deployer = (await web3.eth.getAccounts())[0];
        const deployer = (await web3.eth.getAccounts())[3];
        console.log("deployer is " + deployer);

        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v1 = new web3.eth.Contract(Bridge_v1.abi, bridgeAddress);

        const allowTokensAddress = await bridge_v1.methods.allowTokens().call();
        const allowTokens = await AllowTokens.at(allowTokensAddress);
        console.log(`Configuring AllowTokens contract ${allowTokens.address}`);

        const multiSigAddress = await allowTokens.contract.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        const setMaxTokensAllowedData =
            allowTokens.contract.methods.setMaxTokensAllowed(maximumTokenAmount).encodeABI();

        console.log(`Setting max tokens allowed in ${maximumTokenAmount}`)
        const result = await multiSig.methods.submitTransaction(allowTokens.address, 0, setMaxTokensAllowedData).send({ from: deployer , gasPrice: gasPriceNow});
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
