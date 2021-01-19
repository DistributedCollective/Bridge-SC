const ConverterContract = artifacts.require("Converter");
const assert = require("assert");
const truffleAssert = require("truffle-assertions");

const initialDeploymentFee = 10;
const updatedFee = 20;
const fakeAddress = "0x35cA19131746B8A43F06B53fe0F0731a27328559"; // put a fake address
const fakeAddress2 = "0x02c3e04E90DE8B5ba93C6f1fec8124F2c177ba8A"; // put a fake address

contract("Converter", (accounts) => {
  let converterContract;
  before(async function () {
    converterContract = await ConverterContract.deployed();
  });

  describe("Contract should:", async () => {
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

<<<<<<< HEAD
    it("REJECT conversionFee update when its value is more than 10000", async () => {
      await truffleAssert.fails(
        converterContract.setConversionFee(10001),
=======
    it("REJECT conversionFee update when its value is more than 100", async () => {
      await truffleAssert.fails(
        converterContract.setConversionFee(110),
>>>>>>> feat: added make/take SellOrder - getOrders - more
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

    it("REJECT BridgeContractAddress update when sender is NOT owner", async () => {
<<<<<<< HEAD
=======
      await truffleAssert.fails(
        converterContract.setBridgeContractAddress(fakeAddress, {
          from: fakeAddress,
        })
      );
    });

    xit("REJECT BridgeContractAddress update when its value is zero", async () => {
      await truffleAssert.fails(
        converterContract.setBridgeContractAddress(0),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("UPDATE BridgeContractAddress when sender is owner && EMIT the proper event", async () => {
      const result = await converterContract.setBridgeContractAddress(
        fakeAddress
      );
      const conversionFee = await converterContract.bridgeContractAddress();

      assert.strictEqual(
        conversionFee,
        fakeAddress,
        "Transaction error when updating Bridge Contract Address"
      );

      truffleAssert.eventEmitted(result, "BridgeContractAddressChanged");
    });

    it("REJECT conversionFee update when sender is NOT owner", async () => {
>>>>>>> feat: added make/take SellOrder - getOrders - more
      await truffleAssert.fails(
        converterContract.setBridgeContractAddress(fakeAddress, {
          from: fakeAddress,
        })
      );
    });

    xit("REJECT BridgeContractAddress update when its value is zero", async () => {
      await truffleAssert.fails(
        converterContract.setBridgeContractAddress(0),
        truffleAssert.ErrorType.REVERT
      );
    });

<<<<<<< HEAD
    it("UPDATE BridgeContractAddress when sender is owner && EMIT the proper event", async () => {
      const result = await converterContract.setBridgeContractAddress(
        fakeAddress
      );
      const conversionFee = await converterContract.bridgeContractAddress();
=======
    xit("ACCEPT transaction when contract is NOT PAUSED", async () => {
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      const numberToAdd = 200;
      const testPauseVarPrevious = (
        await converterContract.testPauseVar()
      ).toNumber();
      const testPauseVarChangeTo = testPauseVarPrevious + numberToAdd;
>>>>>>> feat: added make/take SellOrder - getOrders - more

      assert.strictEqual(
        conversionFee,
        fakeAddress,
        "Transaction error when updating Bridge Contract Address"
      );

      truffleAssert.eventEmitted(result, "BridgeContractAddressChanged");
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

    it("PAUSE the contract when sender is owner and contract is UNPAUSED", async () => {
      await converterContract.pauseContract();
      const contractIsPaused = await converterContract.paused();
      assert.strictEqual(contractIsPaused, true);
    });

    xit("REJECT any transaction (except update conversionFee by owner) when contract is PAUSED", async () => {
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      // THIS TEST MUST BE UPDATED WITH A REAL FUNCTION OF THE CONTRACT
      await converterContract.pauseContract();
      // TODO test function with whenNotPaused modifier
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

    it("REJECT addWhiteListToken when sender is not owner", async () => {
      await truffleAssert.fails(
        converterContract.addTokenToWhitelist(fakeAddress, {
          from: fakeAddress,
        })
      );
    });

    xit("REJECT addWhiteListToken when address is ZERO", async () => {
      await truffleAssert.fails(
        converterContract.addTokenToWhitelist(0),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("ADD token to whitelist when sender is owner && EMIT the proper event", async () => {
      // const isTokenValidPrev = await converterContract.isValidToken(fakeAddress);
      const result = await converterContract.addTokenToWhitelist(fakeAddress);
      const isTokenValid = await converterContract.isTokenValid(fakeAddress);

      assert.strictEqual(
        isTokenValid,
        true,
        "Transaction error when adding WhiteList Token Address"
      );

      truffleAssert.eventEmitted(result, "WhitelistTokenAdded");
    });

    it("REJECT already WhiteListed Token when sender is not owner", async () => {
      await truffleAssert.fails(
        converterContract.addTokenToWhitelist(fakeAddress),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("REJECT removeTokenFromWhitelist when sender is not owner", async () => {
      await truffleAssert.fails(
        converterContract.removeTokenFromWhitelist(fakeAddress, {
          from: fakeAddress,
        })
      );
    });

    it("REJECT removeTokenFromWhitelist when Token is not whitelisted", async () => {
      await truffleAssert.fails(
        converterContract.removeTokenFromWhitelist(fakeAddress2),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("REMOVE token from whitelist when sender is owner && EMIT the proper event", async () => {
      // const isTokenValidPrev = await converterContract.isValidToken(fakeAddress);
      const result = await converterContract.removeTokenFromWhitelist(fakeAddress);
<<<<<<< HEAD

=======
      
>>>>>>> feat: added make/take SellOrder - getOrders - more
      const isTokenValid = await converterContract.isTokenValid(fakeAddress);

      assert.strictEqual(
        isTokenValid,
        false,
        "Transaction error when removing WhiteList Token Address"
      );

      truffleAssert.eventEmitted(result, "WhitelistTokenRemoved");
    });
  });
});
