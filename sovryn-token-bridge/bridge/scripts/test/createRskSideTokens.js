const Bridge = artifacts.require("Bridge_v0");
const AlternativeERC20Detailed = artifacts.require("AlternativeERC20Detailed");

const DAI_TOKEN = { token: 'DAI', name: 'Dai Stablecoin', 42:{symbol:'DAI', address:'0x832915943cc51c0620f32dfbaf8b9addb0db25e1', decimals:18}};
const WETH_TOKEN = { token: 'WETH', name: 'Wrapped Ether', 42:{symbol:'WETH', address:'0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9', decimals:18},};
const USDT_TOKEN = { token: 'USDT', name: 'Tether USD', 42:{symbol:'USDT', address:'0x755de969cbc0e7df97eac28933c6a2385c087ca1', decimals:6},};
const RENBTC_TOKEN = { token: 'RenBTC', name: 'Ren BTC', 42:{symbol: 'RenBTC', address: '0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a', decimals: 8},};
const WBTC_TOKEN = { token: 'WBTC', name: 'Wrapped BTC', 42:{symbol: 'WBTC', address: '0xd871ce15efa071b06104dac4225540f5461d17de', decimals: 8},};

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
        const daiToken = await AlternativeERC20Detailed.at(DAI_TOKEN["42"].address);
        const wEthToken = await AlternativeERC20Detailed.at(WETH_TOKEN["42"].address);
        const usdtToken = await AlternativeERC20Detailed.at(USDT_TOKEN["42"].address);
        const renBtcToken = await AlternativeERC20Detailed.at(RENBTC_TOKEN["42"].address);
        const wBtcToken = await AlternativeERC20Detailed.at(WBTC_TOKEN["42"].address);

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
