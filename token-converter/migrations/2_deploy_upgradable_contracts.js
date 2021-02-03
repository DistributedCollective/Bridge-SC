const { deployProxy } = require("@openzeppelin/truffle-upgrades");
const ConverterContract = artifacts.require("Converter");

const initialDeploymentFee = 10;

module.exports = async (deployer) => {
  const instance = await deployProxy(
    ConverterContract,
    [initialDeploymentFee],
    { deployer , unsafeAllowCustomTypes:true } //unsafeAllowCustomTypes    
  );
};