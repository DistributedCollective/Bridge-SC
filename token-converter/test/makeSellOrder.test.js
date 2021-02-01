const ConverterContract = artifacts.require("Converter");
const assert = require("assert");
const truffleAssert = require("truffle-assertions");

const bridgeAddress = "0x1DE9306A49D738443D2Ca79D6C0bFF1f8070F338";
const whiteListedToken = "0x35cA19131746B8A43F06B53fe0F0731a27328559";
const notWhiteListedToken = "0x02c3e04E90DE8B5ba93C6f1fec8124F2c177ba8A";
const userData = web3.utils.sha3("RANDOM_DATA");
const zeroAddress = "0x0000000000000000000000000000000000000000";
const firstAmount = 1000;
const secondAmount = 1500;
const thirdAmount = 2000;

const sellerAddress1 = "0xd6f527C12470A0aAeB38A3b2CEB99f07Bc8F174B";
const sellerAddress2 = "0x8AeF249d8191f1CBCCb3978b828A8C88251A6e7D";
const sellerAddress3 = "0x4D80D038D7191Ceb7E0451E5329389606e644fDa";

contract("Converter", (accounts) => {
  let converterContract;
  before(async function () {
    converterContract = await ConverterContract.deployed();
    await converterContract.addTokenToWhitelist(whiteListedToken);
    await converterContract.setBridgeContractAddress(bridgeAddress);
  });

  describe("Called onTokenReceived WRONGLY from the bridge should:", async () => {
    it("REJECT when calling address is not the Bridge", async () => {
      await truffleAssert.fails(
        converterContract.onTokensReceived(
          sellerAddress1,
          firstAmount,
          whiteListedToken,
          userData
        ),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("REJECT when contract is paused", async () => {
      converterContract.pauseContract();
      await truffleAssert.fails(
        converterContract.onTokensReceived(
          sellerAddress1,
          firstAmount,
          whiteListedToken,
          userData,
          { from: bridgeAddress }
        ),
        truffleAssert.ErrorType.REVERT
      );
      converterContract.unpauseContract();
    });

    it("REJECT when seller address is null", async () => {
      await truffleAssert.fails(
        converterContract.onTokensReceived(
          zeroAddress,
          firstAmount,
          whiteListedToken,
          userData,
          { from: bridgeAddress }
        ),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("REJECT when token address is null", async () => {
      await truffleAssert.fails(
        converterContract.onTokensReceived(
          zeroAddress,
          firstAmount,
          whiteListedToken,
          userData,
          { from: bridgeAddress }
        ),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("REJECT when amount received is zero", async () => {
      await truffleAssert.fails(
        converterContract.onTokensReceived(
          sellerAddress1,
          0,
          whiteListedToken,
          userData,
          { from: bridgeAddress }
        ),
        truffleAssert.ErrorType.REVERT
      );
    });

    it("REJECT when token address is not whitelisted", async () => {
      await truffleAssert.fails(
        converterContract.onTokensReceived(
          sellerAddress1,
          firstAmount,
          notWhiteListedToken,
          userData,
          { from: bridgeAddress }
        ),
        truffleAssert.ErrorType.REVERT
      );
    });
  });

  describe("Called onTokenReceived CORRECTLY from the bridge should:", async () => {
    let result;
    let previousNumOrder;
    let numOrder;
    let lastOrderIndex;

    it("Start with numOrder and lastOrderIndex as ZERO value", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();

      const lastOrderIndexBN = await converterContract.lastOrderIndex();
      lastOrderIndex = lastOrderIndexBN.toNumber();

      assert.strictEqual(numOrder, 0, "numOrder should be Zero");
      assert.strictEqual(lastOrderIndex, 0, "lastOrderIndex should be Zero");
    });

    it("First Sell Order: receive Tokens - emit TOKENS RECEIVED Event - call makeSellOrder", async () => {
      const previousNumOrderBN = await converterContract.numOrder();
      previousNumOrder = previousNumOrderBN.toNumber();

      result = await converterContract.onTokensReceived(
        sellerAddress1,
        firstAmount,
        whiteListedToken,
        userData,
        { from: bridgeAddress }
      );

      truffleAssert.eventEmitted(result, "TokensReceived");
      assert.strictEqual(
        previousNumOrder,
        0,
        "Previous NumOrder should be Zero"
      );
    });

    it("Increment numOrder by one. At first, it should be equal to 1", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(numOrder, 1, "numOrder should be 1");
    });

    it("Orders mapping should contain received parameters and set ZERO as next & previous order", async () => {
      const sellOrder = await converterContract.orders(numOrder);
      const previousOrder = sellOrder.previousOrder.toNumber();
      assert.strictEqual(previousOrder, 0, "Previous Order should be Zero");

      const nextOrder = sellOrder.nextOrder.toNumber();
      assert.strictEqual(nextOrder, 0, "Next Order should be Zero");

      assert.strictEqual(sellOrder.sellerAddress, sellerAddress1, "");
      assert.strictEqual(sellOrder.tokenAddress, whiteListedToken, "");
      assert.strictEqual(sellOrder.orderAmount.toNumber(), firstAmount, "");
    });

    it("Emit MAKE SELL ORDER Event for the First Order", async () => {
      truffleAssert.eventEmitted(result, "MakeSellOrder");
    });

    it("Second Sell Order: receive Tokens - emit TOKENS RECEIVED Event - call makeSellOrder", async () => {
      const previousNumOrderBN = await converterContract.numOrder();
      previousNumOrder = previousNumOrderBN.toNumber();

      result = await converterContract.onTokensReceived(
        sellerAddress2,
        secondAmount,
        whiteListedToken,
        userData,
        { from: bridgeAddress }
      );

      truffleAssert.eventEmitted(result, "TokensReceived");
      assert.strictEqual(previousNumOrder, 1, "Previous NumOrder should be 1");
    });

    it("Increment numOrder by one. It should be equal to 2", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(numOrder, 2, "numOrder should be 2");
    });

    it("Check Orders mapping - set next order & previous order from both sell orders", async () => {
      const previousSellOrder = await converterContract.orders(
        previousNumOrder
      );
      const prevOrderNext = previousSellOrder.nextOrder.toNumber();
      assert.strictEqual(
        prevOrderNext,
        2,
        "[Next] field of previous Order should be 2"
      );

      const sellOrder = await converterContract.orders(numOrder);
      const previousOrder = sellOrder.previousOrder.toNumber();
      assert.strictEqual(previousOrder, 1, "Previous Order should be 1");

      const nextOrder = sellOrder.nextOrder.toNumber();
      assert.strictEqual(nextOrder, 0, "Next Order should be Zero");

      assert.strictEqual(sellOrder.sellerAddress, sellerAddress2, "");
      assert.strictEqual(sellOrder.tokenAddress, whiteListedToken, "");
      assert.strictEqual(sellOrder.orderAmount.toNumber(), secondAmount, "");
    });

    it("Emit MAKE SELL ORDER Event for the Second Order", async () => {
      truffleAssert.eventEmitted(result, "MakeSellOrder");
    });

    it("Third Sell Order: receive Tokens - emit TOKENS RECEIVED Event - call makeSellOrder", async () => {
      const previousNumOrderBN = await converterContract.numOrder();
      previousNumOrder = previousNumOrderBN.toNumber();

      result = await converterContract.onTokensReceived(
        sellerAddress3,
        thirdAmount,
        whiteListedToken,
        userData,
        { from: bridgeAddress }
      );

      truffleAssert.eventEmitted(result, "TokensReceived");
      assert.strictEqual(previousNumOrder, 2, "Previous NumOrder should be 2");
    });

    it("Increment numOrder by one. It should be equal to 3", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(numOrder, 3, "numOrder should be 3");
    });

    it("Check Orders mapping - set next order & previous order from both sell orders", async () => {
      const previousSellOrder = await converterContract.orders(previousNumOrder);
      const prevOrderNext = previousSellOrder.nextOrder.toNumber();
      assert.strictEqual(prevOrderNext, 3, "[Next] field of previous Order should be 3");

      const sellOrder = await converterContract.orders(numOrder);
      const previousOrder = sellOrder.previousOrder.toNumber();
      assert.strictEqual(previousOrder, 2, "Previous Order should be 2");

      const nextOrder = sellOrder.nextOrder.toNumber();
      assert.strictEqual(nextOrder, 0, "Next Order should be Zero");

      assert.strictEqual(sellOrder.sellerAddress, sellerAddress3, "");
      assert.strictEqual(sellOrder.tokenAddress, whiteListedToken, "");
      assert.strictEqual(sellOrder.orderAmount.toNumber(), thirdAmount, "");
    });

    it("Emit MAKE SELL ORDER Event for the Third Order", async () => {
      truffleAssert.eventEmitted(result, "MakeSellOrder");
    });
  });
});
