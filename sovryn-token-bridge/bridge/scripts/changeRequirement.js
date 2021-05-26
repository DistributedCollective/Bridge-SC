const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = async callback => {
    try {
        const newRequired = process.argv[6];
        if (!newRequired)
            console.error('You need to pass multi Sig new Required amount');
        console.log(`The newRequired will be ${newRequired}`);

        const net = process.argv[5];
        console.log("net is:"+ net);

        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (net == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 

        const deployer = (await web3.eth.getAccounts())[0];
        const multiSig = await MultiSigWallet.deployed();
        console.log(`MultiSig address: ${multiSig.address}`);
        const multiSigAddress = multiSig.address;
        //const multiSigAddress = await federation.contract.methods.owner().call();
        //const multiSigi = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        //console.log(multiSigi.address);
        console.log('Changing required of multi sig')
        const newRequiredData = multiSig.contract.methods.changeRequirement(newRequired).encodeABI();
        console.log(newRequiredData);
        const result = await multiSig.contract.methods.submitTransaction(multiSigAddress, 0, newRequiredData).send({ from: deployer, gas: 300000, gasPrice: gasPriceNow  });
        console.log(`New required set to ${newRequired}`)
        console.log(result)
    } catch (e) {
        callback(e);
    }
    callback();
}
