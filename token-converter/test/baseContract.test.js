const ConverterContract = artifacts.require("Converter");
const assert = require("assert");
const truffleAssert = require("truffle-assertions");

const initialDeploymentFee = 10000;
const updatedFee = 20000;
const fakeAddress = "0x35cA19131746B8A43F06B53fe0F0731a27328559"; // put a fake address

contract("Converter", (accounts) => {
  let converterContract;
  before(async function () {
    converterContract = await ConverterContract.deployed();
  });

  describe("Converter Contract should:", async () => {
    it(`Start with the Initial Deployment Fee of ${initialDeploymentFee} as initial value`, async () => {
      const conversionFeeBN = await converterContract.conversionFee();
      const conversionFee = conversionFeeBN.toNumber();

      assert.strictEqual(
        conversionFee,
        initialDeploymentFee,
        "Wrong initialization fee"
      );
    });

    it("REJECT conversionFee update when its value is zero", async () => {
      await truffleAssert.fails(
        converterContract.setConversionFee(0),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("UPDATE conversionFee when sender is owner && EMIT the proper event", async () => {
      const result = await converterContract.setConversionFee(updatedFee);
      const conversionFeeBN = await converterContract.conversionFee();
      const conversionFee = conversionFeeBN.toNumber();

      assert.strictEqual(
        conversionFee,
        updatedFee,
        "Transaction error when updating fee"
      );

      truffleAssert.eventEmitted(result, "ConversionFeeChanged");
    });

    it("REJECT conversionFee update when sender is NOT owner", async () => {
      await truffleAssert.fails(
        converterContract.setConversionFee(updatedFee, { from: fakeAddress })
      );
    });

    it("REJECT PAUSE action when sender is NOT owner", async () => {
      await truffleAssert.fails(
        converterContract.pauseContract({ from: fakeAddress })
      );
    });

    it("ACCEPT transaction when contract is NOT PAUSED", async () => {
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      const numberToAdd = 200;
      const testPauseVarPrevious = (
        await converterContract.testPauseVar()
      ).toNumber();
      const testPauseVarChangeTo = testPauseVarPrevious + numberToAdd;

      await converterContract.testPause(testPauseVarChangeTo);
      const testPauseVarCurrent = (
        await converterContract.testPauseVar()
      ).toNumber();

      assert.notStrictEqual(testPauseVarCurrent, testPauseVarPrevious);
      assert.strictEqual(testPauseVarChangeTo, testPauseVarCurrent);
    });

    it("PAUSE the contract when sender is owner and contract is UNPAUSED", async () => {
      await converterContract.pauseContract();
      const contractIsPaused = await converterContract.paused();
      assert.strictEqual(contractIsPaused, true);
    });

    it("REJECT any transaction (except update conversionFee by owner) when contract is PAUSED", async () => {
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      await truffleAssert.fails(converterContract.testPause(5));
    });

    it("REJECT PAUSE contract when contract is already PAUSED", async () => {
      await truffleAssert.fails(converterContract.pauseContract());
    });

    it("REJECT UNPAUSE action when sender is NOT owner", async () => {
      await truffleAssert.fails(
        converterContract.unpauseContract({ from: fakeAddress })
      );
    });

    it("UNPAUSE the contract when sender is owner", async () => {
      await converterContract.unpauseContract();
      const contractIsPaused = await converterContract.paused();
      assert.strictEqual(contractIsPaused, false);
    });

    it("REJECT UNPAUSE contract when contract is already UNPAUSED", async () => {
      await truffleAssert.fails(converterContract.unpauseContract());
    });
  });
});
