const ConverterContract = artifacts.require("Converter");
const assert = require("assert");
const truffleAssert = require("truffle-assertions");
const chai = require('chai');
const { expect } = require('chai');

chai.use(require('chai-as-promised'));

const { checkGetOrders } = require("./helpers/utilities");

const whiteListedToken = "0x35cA19131746B8A43F06B53fe0F0731a27328559";
const notWhiteListedToken = "0x02c3e04E90DE8B5ba93C6f1fec8124F2c177ba8A";
const zeroAddress = "0x0000000000000000000000000000000000000000";
const ordersIds = [1, 2, 3];
const ordersAmounts = [1000, 1500, 2000];
const sellerAddresses = [
  "0xd6f527C12470A0aAeB38A3b2CEB99f07Bc8F174B",
  "0x8AeF249d8191f1CBCCb3978b828A8C88251A6e7D",
  "0x4D80D038D7191Ceb7E0451E5329389606e644fDa",
];
const usersData = sellerAddresses.map((address) => web3.eth.abi.encodeParameter("address", address));
const zeroAddressUserData = web3.eth.abi.encodeParameter("address", zeroAddress);

contract("Converter", (
    [
      owner,
      bridgeAddress
    ]
) => {
  let converterContract;
  before(async function () {
    converterContract = await ConverterContract.deployed();
    await converterContract.addTokenToWhitelist(whiteListedToken);
    await converterContract.setBridgeContract(bridgeAddress);
  });

  describe("Called onTokenMinted INCORRECTLY from the bridge should:", async () => {
    it("REJECT when calling address is not the Bridge", async () => {
      await expect(
        converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken,
          usersData[0]
        )
      ).to.be.rejectedWith(Error);
    });

    it("REJECT when contract is paused", async () => {
      await converterContract.pauseContract();
      await expect(converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken,
          usersData[0],
          { from: bridgeAddress }
      )).to.be.rejectedWith(Error);
      await converterContract.unpauseContract();
    });

    it("REJECT when seller address is null", async () => {
      const invalidUserData = web3.eth.abi.encodeParameters([], []);
      await expect(
        converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken,
          invalidUserData,
          { from: bridgeAddress }
        )
      ).to.be.rejectedWith(Error);
    });

    it("REJECT when seller address is the zero address", async () => {
      await expect(
        converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken,
          zeroAddressUserData,
          { from: bridgeAddress }
        )
      ).to.be.rejectedWith(Error);
    });

    it("REJECT when token address is null", async () => {
      await expect(
        converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken,
          zeroAddressUserData,
          { from: bridgeAddress }
        )
      ).to.be.rejectedWith(Error);

    });

    it("REJECT when amount received is zero", async () => {
      await expect(
        converterContract.onTokensMinted(
          0,
          whiteListedToken,
          usersData[0],
          { from: bridgeAddress }
        )
      ).to.be.rejectedWith(Error);
    });

    it("REJECT when token address is not whitelisted", async () => {
      await expect(
        converterContract.onTokensMinted(
          ordersAmounts[0],
          notWhiteListedToken,
          usersData[0],
          { from: bridgeAddress }
        )
      ).to.be.rejectedWith(Error);
    });
  });

  describe("Called Get Sell Orders should:", async () => {
    it("REJECT when Qty to show Orders is ZERO or less", async () => {
      await expect(
        converterContract.getSellOrders(ordersIds[0], 0)
      ).to.be.rejectedWith(Error, "qtyToReturn must be greater than ZERO");
    });

    it("REJECT when contract is paused", async () => {
      await converterContract.pauseContract();
      await expect(
        converterContract.getSellOrders(ordersIds[0], 3)
      ).to.be.rejectedWith(Error);
      await converterContract.unpauseContract();
    });

    it("REJECT when there's no Orders", async () => {
      await expect(
        converterContract.getSellOrders(ordersIds[0], 3)
      ).to.be.rejectedWith(Error, "No orders to retrieve");
    });
  });

  describe("Called onTokenMinted CORRECTLY from the bridge should:", async () => {
    let result;
    let previousNumOrder;
    let numOrder;
    let lastOrderIndex;
    let firstOrderIndex;

    it("Start with numOrder and lastOrderIndex as ZERO / firstOrder as 1", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(numOrder, 0, "numOrder should be Zero");

      const lastOrderIndexBN = await converterContract.lastOrderIndex();
      lastOrderIndex = lastOrderIndexBN.toNumber();
      assert.strictEqual(lastOrderIndex, 0, "lastOrderIndex should be Zero");

      const firstOrderIndexBN = await converterContract.firstOrderIndex();
      firstOrderIndex = firstOrderIndexBN.toNumber();
      assert.strictEqual(firstOrderIndex, 0, "firstOrderIndex should be Zero");
    });

    it("First Sell Order: receive Tokens - emit TOKENS RECEIVED Event - call makeSellOrder", async () => {
      const previousNumOrderBN = await converterContract.numOrder();
      previousNumOrder = previousNumOrderBN.toNumber();

      result = await converterContract.onTokensMinted(
        ordersAmounts[0],
        whiteListedToken,
        usersData[0],
        { from: bridgeAddress }
      );

      truffleAssert.eventEmitted(result, "TokensReceived");
      assert.strictEqual(
        previousNumOrder,
        0,
        "Previous NumOrder should be Zero"
      );
    });

    it("Increment numOrder/lastOrderIndex by one. At first, it should be equal to 1  / firstOrder as 1", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(
        numOrder,
        ordersIds[0],
        "numOrder increment error (1)"
      );

      const lastOrderIndexBN = await converterContract.lastOrderIndex();
      lastOrderIndex = lastOrderIndexBN.toNumber();
      assert.strictEqual(
        lastOrderIndex,
        ordersIds[0],
        "lastOrderIndex increment error (1)"
      );

      const firstOrderIndexBN = await converterContract.firstOrderIndex();
      firstOrderIndex = firstOrderIndexBN.toNumber();
      assert.strictEqual(firstOrderIndex, 1, "firstOrderIndex should be 1");
    });

    it("Orders mapping should contain received parameters and set ZERO as next & previous order", async () => {
      const sellOrder = await converterContract.orders(numOrder);
      const previousOrder = sellOrder.previousOrder.toNumber();
      assert.strictEqual(previousOrder, 0, "Previous Order should be Zero");

      const nextOrder = sellOrder.nextOrder.toNumber();
      assert.strictEqual(nextOrder, 0, "Next Order should be Zero");

      assert.strictEqual(sellOrder.recipient, sellerAddresses[0], "");
      assert.strictEqual(sellOrder.tokenAddress, whiteListedToken, "");
      assert.strictEqual(
        sellOrder.orderAmount.toNumber(),
        ordersAmounts[0],
        ""
      );
    });

    it("Emit MAKE SELL ORDER Event for the First Order", async () => {
      truffleAssert.eventEmitted(result, "MakeSellOrder");
    });

    it("REJECT when From Order does not exists", async () => {
      await truffleAssert.fails(
        converterContract.getSellOrders(500, 3),
        truffleAssert.ErrorType.REVERT,
        "Invalid FROM order parameter"
      );
    });

    it("Retrieve the stored Sell Orders (1)", async () => {
      const orders = await converterContract.getSellOrders(1, 5);
      const returnedObject = checkGetOrders(orders, ordersIds, ordersAmounts);
      assert.strictEqual(
        returnedObject.checkOrdersOk,
        true,
        "getSellOrders invalid result"
      );
      assert.strictEqual(returnedObject.qty, 1, "wrong orders qty");
    });

    it("FAIL the comparission of the retrieved Sell Orders (fake Amounts)", async () => {
      const fakeAmounts = [500, 600];
      const orders = await converterContract.getSellOrders(1, 5);
      const returnedObject = checkGetOrders(orders, ordersIds, fakeAmounts);
      assert.strictEqual(returnedObject.checkOrdersOk, false, "");
    });

    it("FAIL the comparission of the retrieved Sell Orders (fake Ids)", async () => {
      const fakeIds = [3, 4];
      const orders = await converterContract.getSellOrders(1, 5);
      const returnedObject = checkGetOrders(orders, ordersIds, fakeIds);
      assert.strictEqual(returnedObject.checkOrdersOk, false, "");
    });

    it("Second Sell Order: receive Tokens - emit TOKENS RECEIVED Event - call makeSellOrder - with multipleUserData", async () => {
      const previousNumOrderBN = await converterContract.numOrder();
      previousNumOrder = previousNumOrderBN.toNumber();

      const intExtraData = "1000000000";
      const multipleUserData = web3.eth.abi.encodeParameters(
          ["address", "uint32"],
          [sellerAddresses[1], intExtraData]
      );

      result = await converterContract.onTokensMinted(
        ordersAmounts[1],
        whiteListedToken,
        multipleUserData,
        { from: bridgeAddress }
      );

      truffleAssert.eventEmitted(result, "TokensReceived");
      assert.strictEqual(
        previousNumOrder,
        ordersIds[0],
        "Previous NumOrder error (1)"
      );
    });

    it("Increment numOrder by one. It should be equal to 2", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(
        numOrder,
        ordersIds[1],
        "numOrder increment error (2)"
      );

      const lastOrderIndexBN = await converterContract.lastOrderIndex();
      lastOrderIndex = lastOrderIndexBN.toNumber();
      assert.strictEqual(
        lastOrderIndex,
        ordersIds[1],
        "lastOrderIndex increment error (2)"
      );
    });

    it("Check Orders mapping - set next order & previous order from both sell orders", async () => {
      const previousSellOrder = await converterContract.orders(
        previousNumOrder
      );
      const prevOrderNext = previousSellOrder.nextOrder.toNumber();
      assert.strictEqual(
        prevOrderNext,
        ordersIds[1],
        "[Next] field of previous Order error (2)"
      );

      const sellOrder = await converterContract.orders(numOrder);
      const previousOrder = sellOrder.previousOrder.toNumber();
      assert.strictEqual(
        previousOrder,
        ordersIds[0],
        "Previous Order linked error (1)"
      );

      const nextOrder = sellOrder.nextOrder.toNumber();
      assert.strictEqual(nextOrder, 0, "Next Order should be Zero");

      assert.strictEqual(sellOrder.recipient, sellerAddresses[1], "");
      assert.strictEqual(sellOrder.tokenAddress, whiteListedToken, "");
      assert.strictEqual(
        sellOrder.orderAmount.toNumber(),
        ordersAmounts[1],
        ""
      );
    });

    it("Emit MAKE SELL ORDER Event for the Second Order", async () => {
      truffleAssert.eventEmitted(result, "MakeSellOrder");
    });

    it("Retrieve the stored Sell Orders (2)", async () => {
      const orders = await converterContract.getSellOrders(1, 5);
      const returnedObject = checkGetOrders(orders, ordersIds, ordersAmounts);
      assert.strictEqual(
        returnedObject.checkOrdersOk,
        true,
        "getSellOrders invalid result"
      );
      assert.strictEqual(returnedObject.qty, 2, "wrong orders qty");
    });

    it("Third Sell Order: receive Tokens - emit TOKENS RECEIVED Event - call makeSellOrder", async () => {
      const previousNumOrderBN = await converterContract.numOrder();
      previousNumOrder = previousNumOrderBN.toNumber();

      result = await converterContract.onTokensMinted(
        ordersAmounts[2],
        whiteListedToken,
        usersData[2],
        { from: bridgeAddress }
      );

      truffleAssert.eventEmitted(result, "TokensReceived");
      assert.strictEqual(
        previousNumOrder,
        ordersIds[1],
        "Previous NumOrder error (2)"
      );
    });

    it("Increment numOrder by one. It should be equal to 3", async () => {
      const numOrderBN = await converterContract.numOrder();
      numOrder = numOrderBN.toNumber();
      assert.strictEqual(
        numOrder,
        ordersIds[2],
        "numOrder increment error (3)"
      );

      const lastOrderIndexBN = await converterContract.lastOrderIndex();
      lastOrderIndex = lastOrderIndexBN.toNumber();
      assert.strictEqual(
        lastOrderIndex,
        ordersIds[2],
        "lastOrderIndex increment error (3)"
      );
    });

    it("Check Orders mapping - set next order & previous order from both sell orders", async () => {
      const previousSellOrder = await converterContract.orders(
        previousNumOrder
      );
      const prevOrderNext = previousSellOrder.nextOrder.toNumber();
      assert.strictEqual(
        prevOrderNext,
        ordersIds[2],
        "[Next] field of previous Order error"
      );

      const sellOrder = await converterContract.orders(numOrder);
      const previousOrder = sellOrder.previousOrder.toNumber();
      assert.strictEqual(
        previousOrder,
        ordersIds[1],
        "Previous Order linked error (2)"
      );

      const nextOrder = sellOrder.nextOrder.toNumber();
      assert.strictEqual(nextOrder, 0, "Next Order should be Zero");

      assert.strictEqual(sellOrder.recipient, sellerAddresses[2], "");
      assert.strictEqual(sellOrder.tokenAddress, whiteListedToken, "");
      assert.strictEqual(
        sellOrder.orderAmount.toNumber(),
        ordersAmounts[2],
        ""
      );
    });

    it("Emit MAKE SELL ORDER Event for the Third Order", async () => {
      truffleAssert.eventEmitted(result, "MakeSellOrder");
    });

    it("Retrieve the stored Sell Orders (3)", async () => {
      const orders = await converterContract.getSellOrders(1, 5);
      const returnedObject = checkGetOrders(orders, ordersIds, ordersAmounts);
      assert.strictEqual(
        returnedObject.checkOrdersOk,
        true,
        "getSellOrders invalid result"
      );
      assert.strictEqual(returnedObject.qty, 3, "wrong orders qty");
    });
  });
});
