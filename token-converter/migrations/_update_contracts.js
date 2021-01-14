// SAMPLE FILE TO UPGRADE A CONTRACT

const { upgradeProxy } = require("@openzeppelin/truffle-upgrades");

const ConverterContract = artifacts.require("Converter");
const ConverterContract_v2 = artifacts.require("MockConverter_v2");

module.exports = async function (deployer) {
  const existing = await ConverterContract.deployed();
  const instance = await upgradeProxy(existing.address, ConverterContract_v2, { deployer });
  console.log("\nUpgraded Contract in ==> ", instance.address);
};