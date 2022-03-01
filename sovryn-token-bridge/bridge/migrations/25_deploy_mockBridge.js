const MockBridge = artifacts.require('./MockBridge.sol');

module.exports = function(deployer) {
  deployer.deploy(MockBridge);
};
