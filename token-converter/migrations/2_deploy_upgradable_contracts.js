const { deployProxy } = require("@openzeppelin/truffle-upgrades");
const ConverterContract = artifacts.require("Converter");

const initialDeploymentFee = 10000;

module.exports = async (deployer) => {
  const instance = await deployProxy(
    ConverterContract,
    [initialDeploymentFee],
    { deployer }
  );
  console.log("\nDeployed Converter Contract in ==> ", instance.address);  
};
