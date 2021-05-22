const Federation = artifacts.require("Federation");
const MultiSigWallet = artifacts.require("MultiSigWallet");

module.exports = async callback => {
    try {
        const oldMemberAddress = process.argv[6];
        if (!oldMemberAddress)
            console.error('You need to pass old member address');
        console.log(`The address ${oldMemberAddress} will be removed from federation`);

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

        const federation = await Federation.deployed();
        console.log(`Federation address: ${federation.address}`);
        const multiSigAddress = await federation.contract.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        console.log('Removing member from federation')
        const removedMemberData = federation.contract.methods.removeMember(oldMemberAddress).encodeABI();
        const result = await multiSig.methods.submitTransaction(federation.address, 0, removedMemberData).send({ from: deployer, gas: 300000 , gasPrice: gasPriceNow});
        console.log('Member removed')
        console.log(result)
    } catch (e) {
        callback(e);
    }
    callback();
}
