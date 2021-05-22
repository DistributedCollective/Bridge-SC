const AllowTokens = artifacts.require("AllowTokens");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v1 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const dailyLimit = process.argv[6];
        if (!dailyLimit) {
            console.error('You need to pass the dailyLimit of the bridge');
            callback();
            return;
        }
        //const dailyLimit = Number.parseInt(dailyLimit);
        
        const dailyLimitWei = web3.utils.toWei(dailyLimit);
        
        const deployer = (await web3.eth.getAccounts())[0];
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v1 = new web3.eth.Contract(Bridge_v1.abi, bridgeAddress);

        const allowTokensAddress = await bridge_v1.methods.allowTokens().call();
        const allowTokens = await AllowTokens.at(allowTokensAddress);
        console.log(`Configuring AllowTokens contract ${allowTokens.address}`);

        const multiSigAddress = await allowTokens.contract.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        const changeDailyLimitData =
            allowTokens.contract.methods.changeDailyLimit(dailyLimitWei).encodeABI();

        console.log(`Setting dailyLimit tokens allowed in ${dailyLimitWei}`)
        const result = await multiSig.methods.submitTransaction(allowTokens.address, 0, changeDailyLimitData).send({ from: deployer });
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
