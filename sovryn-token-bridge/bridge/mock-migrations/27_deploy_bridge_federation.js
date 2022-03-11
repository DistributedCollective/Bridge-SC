const Utils = artifacts.require('Utils');
const AllowTokens = artifacts.require('AllowTokens');
const Bridge = artifacts.require('Bridge');
const Federation = artifacts.require('Federation');
const MockERC20 = artifacts.require('MockERC20');

module.exports = async function(deployer) {
    try {
        await deployer.deploy(Utils);
        await deployer.deploy(AllowTokens, '0x8c981fEa9Fa5eD6248a50da281ffD7fB87D0ee16');
        await deployer.link(Utils, Bridge);
        await deployer.deploy(Bridge);
        await deployer.deploy(
            Federation,
            [
                '0x8c981fEa9Fa5eD6248a50da281ffD7fB87D0ee16',
                '0xA59f8360a2BDB46104E601c5106eb0aA128d494B',
                '0x189Ec9a470F38Ee8Dc732b8fCC9d03624cD0d6A0',
            ],
            3,
        );

        await deployer.deploy(MockERC20);

        const bridge = await Bridge.deployed();
        const allowTokens = await AllowTokens.deployed();
        await bridge.initialize('0x8c981fEa9Fa5eD6248a50da281ffD7fB87D0ee16');
        await bridge.changeAllowTokens(allowTokens.address);
        console.log('AllowTokens address changed on bridge');
        const federation = await Federation.deployed();
        await federation.setBridge(bridge.address);
        console.log('Bridge set on federation');
    } catch (err) {
        console.log(`An error occured: ${err}`);
    }
};
