const Bridge = artifacts.require("Bridge_v0");
const BridgeImpl = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const tokens = [
            '0x832915943cc51c0620f32dfbaf8b9addb0db25e1',
            '0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9',
            '0x755de969cbc0e7df97eac28933c6a2385c087ca1',
            '0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a',
            '0xd871ce15efa071b06104dac4225540f5461d17de'
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
