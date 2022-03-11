const MockERC20 = artifacts.require('MockERC20');
const Bridge = artifacts.require('Bridge');

const user = '0xd248CD168c8640C7CC14815Eb542061449aB29cf';

module.exports = async (callback) => {
    const mockERC20 = await MockERC20.deployed();
    const bridge = await Bridge.deployed();

    try {
        await mockERC20.mint(user, '100000000000000000000'); // 100 tokens
        console.log('Token minted');
        await mockERC20.approve(bridge.address, '100000000000000000000', {
            from: user,
        });
        console.log('Token approved');

        await bridge.receiveTokens(mockERC20.address, 1_000_000, {
            from: user,
        });
        console.log('Tokens sent through the bridge');
    } catch (err) {
        console.log(`An error occured: ${err}`);
    }

    callback();
};
