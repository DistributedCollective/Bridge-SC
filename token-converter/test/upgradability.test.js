const { deployProxy, upgradeProxy } = require("@openzeppelin/truffle-upgrades");

const ConverterContract_v1 = artifacts.require("Converter");
const MockConverterContract_v2 = artifacts.require("MockConverter_v2");
const assert = require("assert");

const initialDeploymentFee = 1000;
const updatedFee = 1500;
let v1_contract;
let v1_contractStoredValue;
let v2_contract;

contract("Converter", async (accounts) => {
  before(async function () {
    v1_contract = await deployProxy(
      ConverterContract_v1,
      [initialDeploymentFee],
      { unsafeAllowCustomTypes: true }
    );
  });

  describe("Contract should", () => {
    it(`Store an initial conversionFee of ${initialDeploymentFee} in First Contract`, async () => {
      const conversionFeeBN = await v1_contract.conversionFee();
      const conversionFee = conversionFeeBN.toNumber();

      assert.strictEqual(
        conversionFee,
        initialDeploymentFee,
        "Wrong initialization fee"
      );
    });

    it(`UPDATE conversionFee with ${updatedFee} when sender is owner`, async () => {
      await v1_contract.setConversionFee(updatedFee);
      const conversionFeeBN = await v1_contract.conversionFee();
      const conversionFee = conversionFeeBN.toNumber();

      assert.strictEqual(
        conversionFee,
        updatedFee,
        "Transaction error when updating fee"
      );
    });
  });

  describe("Delpoy UPGRADED Contract should", () => {
    before(async function () {
      v2_contract = await upgradeProxy(
        v1_contract.address,
        MockConverterContract_v2,
        { unsafeAllowCustomTypes: true }
      );
    });

    it(`Check conversionFee is ${updatedFee} as updated in the previous contract`, async () => {
      const conversionFeeBN = await v2_contract.conversionFee();
      const conversionFee = conversionFeeBN.toNumber();

      assert.strictEqual(
        conversionFee,
        updatedFee,
        "Wrong upgraded contract -> initialization fee"
      );
    });
  });
});
