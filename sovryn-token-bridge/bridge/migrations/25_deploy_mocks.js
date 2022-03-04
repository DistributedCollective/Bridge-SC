const MockBridge = artifacts.require('MockBridge');

module.exports = function(deployer) {
    deployer.deploy(MockBridge);
};
