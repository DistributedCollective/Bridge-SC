const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v1 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const feePercentageArg = process.argv[6];
        if (!feePercentageArg)
            console.error('You need to pass the fee percentage');
        const feePercentage = Number.parseInt(feePercentageArg);
        if(feePercentage > 10000)
            console.log('Fee percentage must be less than 10000');

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
        const bridge_v1 = new web3.eth.Contract(Bridge_v1.abi, bridgeAddress);

        //const deployer = (await web3.eth.getAccounts())[0];
        const deployer = (await web3.eth.getAccounts())[3];
        console.log("deployer is " + deployer);
        
        console.log(`Configuring fee percentage ${feePercentage/100}% from address ${deployer}`);
        console.log('Bridge address', bridgeAddress);
        const setFeeMethodData = bridge_v1.methods.setFeePercentage(feePercentage).encodeABI();

        const multisigAddress = await bridge_v1.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multisigAddress);
        
        console.log('MultiSig address', multisigAddress);
        const result = await multiSig.methods.submitTransaction(bridge_v0.address, 0, setFeeMethodData).send({ from: deployer , gasPrice: gasPriceNow});

        console.log('Fee percentage was changed');
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
