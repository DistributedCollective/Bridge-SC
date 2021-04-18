const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = async callback => {
    try {
        const newOwnerAddress = process.argv[6];
        if (!newOwnerAddress)
            console.error('You need to pass new owner address');
        console.log(`The address ${newOwnerAddress} will be added as owner`);

        const deployer = (await web3.eth.getAccounts())[0];
        const multiSig = await MultiSigWallet.deployed();
        console.log(`MultiSig address: ${multiSig.address}`);
        const multiSigAddress = multiSig.address;
        //const multiSigAddress = await federation.contract.methods.owner().call();
        //const multiSigi = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        //console.log(multiSigi.address);
        console.log('Adding new owner to multisig')
        const addOwnerData = multiSig.contract.methods.addOwner(newOwnerAddress).encodeABI();
        console.log(addOwnerData);
        const result = await multiSig.contract.methods.submitTransaction(multiSigAddress, 0, addOwnerData).send({ from: deployer, gas: 300000 });
        console.log('New owner added')
        console.log(result)
    } catch (e) {
        callback(e);
    }
    callback();
}
