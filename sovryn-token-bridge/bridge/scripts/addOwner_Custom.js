//const MultiSigWallet = artifacts.require("MultiSigWallet");
const multisigAbi = require("../../abis/MultiSigWallet.json");

module.exports = async callback => {
    try {
        const newOwnerAddress = process.argv[6];
        if (!newOwnerAddress)
            console.error('You need to pass new owner address');
        console.log(`The address ${newOwnerAddress} will be added as owner`);

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
        //const deployer = (await web3.eth.getAccounts())[3];
        console.log("deployer is " + deployer);

        const multiSigAddress = "0x314d9163Dd122368b3c6329b081d2400a9f238d1";
        const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress, {from: deployer});

        // const multiSig = await MultiSigWallet.deployed();
        // console.log(`MultiSig address: ${multiSig.address}`);
        // const multiSigAddress = multiSig.address;

        //const multiSigAddress = await federation.contract.methods.owner().call();
        //const multiSigi = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        //console.log(multiSigi.address);
        console.log('Adding new owner to multisig')
        const addOwnerData = multiSig.methods.addOwner(newOwnerAddress).encodeABI();
        
        console.log(addOwnerData);
        const result = await multiSig.methods.submitTransaction(multiSigAddress, 0, addOwnerData).send({ from: deployer, gas: 300000, gasPrice: gasPriceNow });
        console.log('New owner added')
        console.log(result)
    } catch (e) {
        callback(e);
    }
    callback();
}
