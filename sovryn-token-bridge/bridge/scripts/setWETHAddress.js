const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v3 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const WETHAddress = process.argv[6];
        if (!WETHAddress)
            console.error('You need to pass WETHAddress');
        
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v3 = new web3.eth.Contract(Bridge_v3.abi, bridgeAddress);

        const deployer = (await web3.eth.getAccounts())[0];

        console.log(`Set WETHAddress ${WETHAddress}by deployer ${deployer}`);

        console.log('Bridge address', bridgeAddress);
        const WETHAddressData = bridge_v3.methods.setWETHAddress(WETHAddress).encodeABI();

        const multisigAddress = await bridge_v3.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multisigAddress);
        console.log('MultiSig address', multisigAddress);
        const result = await multiSig.methods.submitTransaction(bridge_v0.address, 0, WETHAddressData).send({ from: deployer });

        console.log('WETHAddress was updates');
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
