const Bridge = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");
const KovanTokens = require("./_constants_helper").kovanTokens;


module.exports = async callback => {
    try {
        const tokens = [
            KovanTokens.DAI_TOKEN[42].address,
            KovanTokens.WETH_TOKEN[42].address,
            KovanTokens.USDT_TOKEN[42].address,
            KovanTokens.RENBTC_TOKEN[42].address,
            KovanTokens.WBTC_TOKEN[42].address,
        ];

        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge = await BridgeImpl.at(bridgeAddress);

        const promises = tokens.map(async tokenAddress => {
            const sideTokenAddress = await bridge.mappedTokens(tokenAddress);
            return { original: tokenAddress, sideToken: sideTokenAddress.toLowerCase() }
        });

        const res = await Promise.all(promises);
        console.table(res);

    } catch (e) {
        callback(e);
    }
    callback();
}

/*
/home/atix/dev/_atix/_git/sovryn-token-bridge-converter/sovryn-token-bridge/bridge/scripts/test/getSideTokensAddresses.js

npx truffle exec "./scripts/test/getSideTokensAddresses.js" --network rsktestnet
*/