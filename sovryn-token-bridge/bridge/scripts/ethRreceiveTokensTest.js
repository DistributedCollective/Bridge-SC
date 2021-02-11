module.exports = async callback => {
    const kovanConfig = require('../federator/config/kovan.json');

    const DAI_TOKEN = { token: 'DAI', name: 'Dai Stablecoin', icon: 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0x6B175474E89094C44Da98b954EedeAC495271d0F/logo.png', 31:{symbol:'rDAI', address:'0x9148c558eac5aedee9d84b4c3f3754dd49bf0b3b', decimals:18}, 42:{symbol:'DAI', address:'0x832915943cc51c0620f32dfbaf8b9addb0db25e1', decimals:18}};

    const WETH_TOKEN = { token: 'WETH', name: 'Wrapped Ether', icon: 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2/logo.png', 31:{symbol:'rWETH', address:'0x0057e76d6b2da3d991fae054c4dd2f05bdc5a111', decimals:18}, 42:{symbol:'WETH', address:'0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9', decimals:18},};

    const USDT_TOKEN = { token: 'USDT', name: 'Tether USD', icon: 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xdAC17F958D2ee523a2206206994597C13D831ec7/logo.png', 31:{symbol:'rUSDT', address:'0x157e66d1c3653a7cf56f16a0c5923425a738e471', decimals:18}, 42:{symbol:'USDT', address:'0x755de969cbc0e7df97eac28933c6a2385c087ca1', decimals:6},};

    const RENBTC_TOKEN = { token: 'RenBTC', name: 'Ren BTC', icon:'https://etherscan.io/token/images/renbtc_32.png', 31:{symbol: 'rRenBTC', address: '0x8ee826ec63e9f36c25759df5b011163b1109eb57', decimals: 18}, 42:{symbol: 'RenBTC', address: '0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a', decimals: 8},};

    const WBTC_TOKEN = { token: 'WBTC', name: 'Wrapped BTC', icon:'https://etherscan.io/token/images/wbtc_28.png?v=1', 31:{symbol: 'rWBTC', address: '0x7c733b197d17cb422f555604d8630b9f1196bc6b', decimals: 18}, 42:{symbol: 'WBTC', address: '0xd871ce15efa071b06104dac4225540f5461d17de', decimals: 8},};

    const TOKENS = [ DAI_TOKEN, RENBTC_TOKEN, USDT_TOKEN, WBTC_TOKEN, WETH_TOKEN ];

    const bridge = await Bridge.at(kovanConfig.bridge)

    const daiToken = await AlternativeERC20Detailed.at(DAI_TOKEN["42"].address);
    const wEthToken = await AlternativeERC20Detailed.at(WETH_TOKEN["42"].address);
    const usdtToken = await AlternativeERC20Detailed.at(USDT_TOKEN["42"].address);
    const renBtcToken = await AlternativeERC20Detailed.at(RENBTC_TOKEN["42"].address);
    const wBtcToken = await AlternativeERC20Detailed.at(WBTC_TOKEN["42"].address);

    const MultiSigWallet = artifacts.require("MultiSigWallet");
    const Bridge = artifacts.require("Bridge_v0");
    const Bridge_v1 = artifacts.require("Bridge");

    try {

    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
