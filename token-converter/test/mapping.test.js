const ConverterContract = artifacts.require("Converter");
const Bridge = artifacts.require("Bridge");
const MockSideToken = artifacts.require("MockSideToken");

const assert = require("assert");
const truffleAssert = require("truffle-assertions");
const chai = require("chai");
const { expect } = require("chai");

chai.use(require("chai-as-promised"));

const { checkGetOrders, makeSellOrder } = require("./helpers/utilities");

const ethDestinationAddress = "0x35cA19131746B8A43F06B53fe0F0731a27328559";
const zeroAddress = "0x0000000000000000000000000000000000000000";
const ordersIds = [1, 2, 3];

const NOT_NULL_ERROR = "Address cannot be empty";
const PAUSED_ERROR = "Pausable: paused";
const ZERO_AMOUNT_ERROR = "Amount to buy must be greater than 0";

contract(
  "Converter",
  ([
    owner,
    bridgeAddress,
    sellerAddress1,
    sellerAddress2,
    sellerAddress3,
    lp1,
    lp2,
  ]) => {
    const sellerAddresses = [sellerAddress1, sellerAddress2, sellerAddress3];
    const usersData = sellerAddresses.map((address) =>
      web3.eth.abi.encodeParameter("address", address)
    );
    let converterContract;
    let bridge;
    let whiteListedToken;

    before(async function () {
      converterContract = await ConverterContract.deployed();
      bridge = await Bridge.new();
      await converterContract.setBridgeContract(bridge.address);
      whiteListedToken = (await MockSideToken.new()).address;
      await converterContract.addTokenToWhitelist(whiteListedToken);
    });

    describe("Check the sell order map", async () => {
      let orderId1 = 0;
      let orderId2 = 0;
      let orderId3 = 0;
      let orderId4 = 0;
      let firstOrderIndex=0;
      let lastOrderIndex=0;

      it("Build the map with the orders when calling onTokensMinted", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        let orderAmount = web3.utils.toWei("1");
        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );
        orderId1 = (await converterContract.numOrder()).toNumber();
        let order1 = await converterContract.orders(orderId1);

        assert.strictEqual(order1.previousOrder.toString(), "0", "Err prev 1");
        assert.strictEqual(order1.nextOrder.toString(), "0", "Err next 1");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1a1");
        assert.strictEqual(lastOrderIndex, 1, "ErrLast 1a1");

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId2 = (await converterContract.numOrder()).toNumber();
        let order2 = await converterContract.orders(orderId2);
        order1 = await converterContract.orders(orderId1);

        assert.strictEqual(order1.previousOrder.toString(), "0", "ErrPrev1 1a2");
        assert.strictEqual(order1.nextOrder.toString(), "2", "ErrNext1 1a2");

        assert.strictEqual(order2.previousOrder.toString(), "1", "ErrPrev2 1a2");
        assert.strictEqual(order2.nextOrder.toString(), "0", "ErrNext2 1a2");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1a2");
        assert.strictEqual(lastOrderIndex, 2, "ErrLast 1a2");

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId3 = (await converterContract.numOrder()).toNumber();
        let order3 = await converterContract.orders(orderId3);
        order1 = await converterContract.orders(orderId1);
        order2 = await converterContract.orders(orderId2);

        assert.strictEqual(order1.previousOrder.toString(), "0", "ErrPrev1 1a3");
        assert.strictEqual(order1.nextOrder.toString(), "2", "ErrNext1 1a3");

        assert.strictEqual(order2.previousOrder.toString(), "1", "ErrPrev2 1a3");
        assert.strictEqual(order2.nextOrder.toString(), "3", "ErrNext2 1a3");

        assert.strictEqual(order3.previousOrder.toString(), "2", "ErrPrev3 1a3");
        assert.strictEqual(order3.nextOrder.toString(), "0", "ErrNext3 1a3");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1a3");
        assert.strictEqual(lastOrderIndex, 3, "ErrLast 1a3");

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId4 = (await converterContract.numOrder()).toNumber();
        let order4 = await converterContract.orders(orderId4);
        order1 = await converterContract.orders(orderId1);
        order2 = await converterContract.orders(orderId2);
        order3 = await converterContract.orders(orderId3);

        assert.strictEqual(order1.previousOrder.toString(), "0", "ErrPrev1 1a4");
        assert.strictEqual(order1.nextOrder.toString(), "2", "ErrNext1 1a4");

        assert.strictEqual(order2.previousOrder.toString(), "1", "ErrPrev2 1a4");
        assert.strictEqual(order2.nextOrder.toString(), "3", "ErrNext2 1a4");

        assert.strictEqual(order3.previousOrder.toString(), "2", "ErrPrev3 1a4");
        assert.strictEqual(order3.nextOrder.toString(), "4", "ErrNext3 1a4");

        assert.strictEqual(order4.previousOrder.toString(), "3", "ErrPrev4 1a4");
        assert.strictEqual(order4.nextOrder.toString(), "0", "ErrNext4 1a4");


        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1a4");
        assert.strictEqual(lastOrderIndex, 4, "ErrLast 1a4");

      });

      it("TakeSellOrder should Update the map, removing filled order 2", async () => {
        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 1;
        const amountToBuy = web3.utils.toWei("1");

        const result = await converterContract.takeSellOrder(
          orderId2,
          amountToBuy, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp2 }
        );

        order1 = await converterContract.orders(orderId1);
        order3 = await converterContract.orders(orderId3);
        order4 = await converterContract.orders(orderId4);

        assert.strictEqual(order1.previousOrder.toString(), "0", "ErrPrev1 1-3-4b");
        assert.strictEqual(order1.nextOrder.toString(), "3", "ErrNext1 1-3-4b");

        assert.strictEqual(order3.previousOrder.toString(), "1", "ErrPrev3 1-3-4b");
        assert.strictEqual(order3.nextOrder.toString(), "4", "ErrNext3 1-3-4b");

        assert.strictEqual(order4.previousOrder.toString(), "3", "ErrPrev4 1-3-4b");
        assert.strictEqual(order4.nextOrder.toString(), "0", "ErrNext4 1-3-4b");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1-3-4b");
        assert.strictEqual(lastOrderIndex, 4, "ErrLast 1-3-4b");

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
      });

      it("Update the map, remove first order (1)", async () => {
        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 1;
        const amountToBuy = web3.utils.toWei("1");

        const result = await converterContract.takeSellOrder(
          orderId1,
          amountToBuy, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp2 }
        );

        order3 = await converterContract.orders(orderId3);
        order4 = await converterContract.orders(orderId4);

        assert.strictEqual(order3.previousOrder.toString(), "0", "ErrPrev3 3-4b");
        assert.strictEqual(order3.nextOrder.toString(), "4", "ErrNext3 3-4b");

        assert.strictEqual(order4.previousOrder.toString(), "3", "ErrPrev4 3-4b");
        assert.strictEqual(order4.nextOrder.toString(), "0", "ErrNext4 3-4b");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 3, "ErrFirst 3-4b");
        assert.strictEqual(lastOrderIndex, 4, "ErrLast 3-4b");

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
      });

      it("Update the map, remove last order (4)", async () => {
        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 1;
        const amountToBuy = web3.utils.toWei("1");

        const result = await converterContract.takeSellOrder(
          orderId4,
          amountToBuy, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp2 }
        );

        order3 = await converterContract.orders(orderId3);

        assert.strictEqual(order3.previousOrder.toString(), "0", "ErrPrev3 3b");
        assert.strictEqual(order3.nextOrder.toString(), "0", "ErrNext3 3b");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 3, "ErrFirst 3-3b");
        assert.strictEqual(lastOrderIndex, 3, "ErrLast 3-3b");

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
      });

      it("TakeSellOrder should Update the map, remove only left order (3)", async () => {
        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 1;
        const amountToBuy = web3.utils.toWei("1");

        const result = await converterContract.takeSellOrder(
          orderId3,
          amountToBuy, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp1 }
        );

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 0, "ErrFirst 0");
        assert.strictEqual(lastOrderIndex, 0, "ErrLast 0");

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
      });

    });
  }
);
