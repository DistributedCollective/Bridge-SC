const Bridge = artifacts.require("Bridge_v0");
const AlternativeERC20Detailed = artifacts.require("AlternativeERC20Detailed");
const KovanTokens = require("./_constants_helper").kovanTokens;

module.exports = async callback => {
    try {
        const tokenQuantity = parseFloat(process.argv[6]);
        console.log(tokenQuantity);
        if (!tokenQuantity) {
            console.error('You need to pass how much tokens you want to cross');
            callback();
            return;
        }

        const bridge = await Bridge.deployed();
        const daiToken = await AlternativeERC20Detailed.at(KovanTokens.DAI_TOKEN["42"].address);
        const wEthToken = await AlternativeERC20Detailed.at(KovanTokens.WETH_TOKEN["42"].address);
        const usdtToken = await AlternativeERC20Detailed.at(KovanTokens.USDT_TOKEN["42"].address);
        const renBtcToken = await AlternativeERC20Detailed.at(KovanTokens.RENBTC_TOKEN["42"].address);
        const wBtcToken = await AlternativeERC20Detailed.at(KovanTokens.WBTC_TOKEN["42"].address);

        const tokens = [daiToken, wEthToken, usdtToken, renBtcToken, wBtcToken];

        const deployer = (await web3.eth.getAccounts())[0];
        console.log(`${tokenQuantity} of each token will be transfer to ${deployer} in RSK`);

        const promises = tokens.map(async token => {
            const decimals = await token.decimals();
            const symbol = await token.name();
            const formattedAmount = (tokenQuantity * (10 ** decimals)).toString();
            await token.approve(bridge.address, formattedAmount);
            console.log(`${formattedAmount} ${symbol} approved, transfering...`);
            const res = await bridge.receiveTokens(token.address, formattedAmount);
            console.log(`${symbol} transfer completed`);
            return res;
        });

        const results = await Promise.all(promises);

        console.log(...results)
    } catch (e) {
        callback(e);
    }
    callback();
}
