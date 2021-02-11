const AllowTokens = artifacts.require("AllowTokens");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v1 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const tokens = [
            '0xbd93b4b623d992703dd2ed66c48eb7eed8874ef1',
            '0x6a5d54d13807a9b362e8fa01fd8cfd6e3ffbbaa3',
            '0x101e953909e959d839730b92ff7690a5a387feca',
            '0x7c262a199ee02704a0a07cac0159b6b8a729e853',
            '0x8c7221e18c8722b593e840b2d16339e6c438d528'
        ];

        const deployer = (await web3.eth.getAccounts())[0];
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v1 = new web3.eth.Contract(Bridge_v1.abi, bridgeAddress);

        console.log(await bridge_v1.methods.allowTokens().call());
        const allowTokensAddress = await bridge_v1.methods.allowTokens().call();
        const allowTokens = await AllowTokens.at(allowTokensAddress);
        console.log(`Configuring AllowTokens contract ${allowTokens.address}`);

        const multiSigAddress = await allowTokens.contract.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        const allowTokenPromises = tokens.map(async token => {
            const addAllowTokenData =
                allowTokens.contract.methods.addAllowedToken(token).encodeABI();

            console.log(`Allowing token ${token}`)
            const result = await multiSig.methods.submitTransaction(allowTokens.address, 0, addAllowTokenData).send({ from: deployer });
            console.log(result)
        });

        await Promise.all(allowTokenPromises);

    } catch (e) {
        callback(e);
    }
    callback();
}
