const { deployProxy, upgradeProxy } = require("@openzeppelin/truffle-upgrades");

const ConverterContract_v1 = artifacts.require("Converter");
const MockConverterContract_v2 = artifacts.require("MockConverter_v2");
const assert = require("assert");

const initialDeploymentFee = 15;
const updatedFee = 20;
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

    xit("ACCEPT transaction and store values", async () => {
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      const numberToAdd = 200;
      const testPauseVarPrevious = (
        await v1_contract.testPauseVar()
      ).toNumber();
      const testPauseVarChangeTo = testPauseVarPrevious + numberToAdd;

      await v1_contract.testPause(testPauseVarChangeTo);
      const testPauseVarCurrent = (await v1_contract.testPauseVar()).toNumber();
      v1_contractStoredValue = testPauseVarCurrent;
      assert.notStrictEqual(testPauseVarCurrent, testPauseVarPrevious);
      assert.strictEqual(testPauseVarChangeTo, testPauseVarCurrent);
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

    xit("ACCEPT transaction and store value + 10, as contrac was updated", async () => {
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      const numberToSend = 200;
      const numberToRetrieve = 210;

      await v2_contract.incrementValueByTen(numberToSend);
      const testPauseVarCurrent = (await v2_contract.testPauseVar()).toNumber();

      assert.strictEqual(numberToRetrieve, testPauseVarCurrent);
    });
  });
});
