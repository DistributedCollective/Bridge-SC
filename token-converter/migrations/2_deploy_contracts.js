const ConverterContract = artifacts.require("Converter");

const initialDeploymentFee = 10000;

module.exports = function (deployer) {
  deployer.deploy(ConverterContract, initialDeploymentFee);
};
