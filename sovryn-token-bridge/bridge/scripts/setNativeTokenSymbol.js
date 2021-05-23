const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v3 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const nativeSymbol = process.argv[6];
        if (!nativeSymbol)
            console.error('You need to pass nativeSymbol');
        
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v3 = new web3.eth.Contract(Bridge_v3.abi, bridgeAddress);

        const deployer = (await web3.eth.getAccounts())[0];

        console.log(`Set nativeSymbol ${nativeSymbol} by deployer ${deployer}`);

        console.log('Bridge address', bridgeAddress);
        const nativeSymbolData = bridge_v3.methods.setNativeTokenSymbol(nativeSymbol).encodeABI();

        const multisigAddress = await bridge_v3.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multisigAddress);
        console.log('MultiSig address', multisigAddress);
        const result = await multiSig.methods.submitTransaction(bridge_v0.address, 0, nativeSymbolData).send({ from: deployer });

        console.log('nativeSymbol was updates');
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
