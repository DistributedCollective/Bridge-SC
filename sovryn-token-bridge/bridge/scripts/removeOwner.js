const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = async callback => {
    try {
        const rmOwnerAddress = process.argv[6];
        if (!rmOwnerAddress)
            console.error('You need to pass owner address');
        console.log(`The owner address ${rmOwnerAddress} will be removed`);

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

        const multiSig = await MultiSigWallet.deployed();
        console.log(`MultiSig address: ${multiSig.address}`);
        const multiSigAddress = multiSig.address;

        console.log('Removing owner from multisig')
        const removeOwnerData = multiSig.contract.methods.removeOwner(rmOwnerAddress).encodeABI();
        console.log(removeOwnerData);
        const result = await multiSig.contract.methods.submitTransaction(multiSigAddress, 0, removeOwnerData).send({ from: deployer, gas: 300000 , gasPrice: gasPriceNow});
        console.log('Owner was removed')
        console.log(result)
    } catch (e) {
        callback(e);
    }
    callback();
}
