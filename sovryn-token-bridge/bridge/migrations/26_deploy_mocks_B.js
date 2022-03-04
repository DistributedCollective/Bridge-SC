const MockFederation = artifacts.require('MockFederation');

module.exports = function(deployer) {
    deployer.deploy(
        MockFederation,
        [
            '0x8c981fEa9Fa5eD6248a50da281ffD7fB87D0ee16',
            '0xA59f8360a2BDB46104E601c5106eb0aA128d494B',
            '0x189Ec9a470F38Ee8Dc732b8fCC9d03624cD0d6A0',
        ],
        3,
    );
};
