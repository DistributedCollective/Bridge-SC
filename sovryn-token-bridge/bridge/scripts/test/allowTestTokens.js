const AllowTokens = artifacts.require("AllowTokens");
const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v1 = artifacts.require("Bridge");
const KovanTokens = require("./_constants_helper").kovanTokens;

module.exports = async (callback) => {
  try {
    const tokens = [
      KovanTokens.DAI_TOKEN[42].address,
      KovanTokens.WETH_TOKEN[42].address,
      KovanTokens.USDT_TOKEN[42].address,
      KovanTokens.RENBTC_TOKEN[42].address,
      KovanTokens.WBTC_TOKEN[42].address,
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

    const allowTokenPromises = tokens.map(async (token) => {
      const addAllowTokenData = allowTokens.contract.methods
        .addAllowedToken(token)
        .encodeABI();

      console.log(`Allowing token ${token}`);
      const result = await multiSig.methods
        .submitTransaction(allowTokens.address, 0, addAllowTokenData)
        .send({ from: deployer });
      console.log(result);
    });

    await Promise.all(allowTokenPromises);
  } catch (e) {
    callback(e);
  }
  callback();
};
