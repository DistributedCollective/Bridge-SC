const ConverterContract = artifacts.require("Converter");
const Bridge = artifacts.require("Bridge");
const MockSideToken = artifacts.require("MockSideToken");
const assert = require("assert");
const chai = require("chai");
chai.use(require("chai-as-promised"));
const { checkGetOrders } = require("./helpers/utilities");

let ordersIds = [1, 2, 3, 4, 5, 6];
let ordersAmounts = [1000000, 1500000, 2000000, 2100000, 3200000, 1300000];

contract(
  "Converter",
  ([
    bridgeAddress,
    sellerAddress1,
    sellerAddress2,
    sellerAddress3,
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
      let orderId5 = 0;
      let orderId6 = 0;
      let firstOrderIndex = 0;
      let lastOrderIndex = 0;

      it("Build the map with the orders when calling onTokensMinted", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);

        await converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );
        orderId1 = (await converterContract.numOrder()).toNumber();
        let order1 = await converterContract.orders(orderId1);

        await converterContract.onTokensMinted(
          ordersAmounts[1],
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId2 = (await converterContract.numOrder()).toNumber();
        let order2 = await converterContract.orders(orderId2);

        await converterContract.onTokensMinted(
          ordersAmounts[2],
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId3 = (await converterContract.numOrder()).toNumber();
        let order3 = await converterContract.orders(orderId3);

        await converterContract.onTokensMinted(
          ordersAmounts[3],
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId4 = (await converterContract.numOrder()).toNumber();
        let order4 = await converterContract.orders(orderId4);

        await converterContract.onTokensMinted(
          ordersAmounts[4],
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId5 = (await converterContract.numOrder()).toNumber();
        let order5 = await converterContract.orders(orderId5);

        await converterContract.onTokensMinted(
          ordersAmounts[5],
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        orderId6 = (await converterContract.numOrder()).toNumber();
        let order6 = await converterContract.orders(orderId6);

        order1 = await converterContract.orders(orderId1);
        order2 = await converterContract.orders(orderId2);
        order3 = await converterContract.orders(orderId3);
        order4 = await converterContract.orders(orderId4);
        order5 = await converterContract.orders(orderId5);


        assert.strictEqual(order1.previousOrder.toString(), "0", "ErrPrev1 1a3");
        assert.strictEqual(order1.nextOrder.toString(), "2", "ErrNext1 1a3");
        assert.strictEqual(order2.previousOrder.toString(), "1", "ErrPrev2 1a3");
        assert.strictEqual(order2.nextOrder.toString(), "3", "ErrNext2 1a3");
        assert.strictEqual(order3.previousOrder.toString(), "2", "ErrPrev3 1a3");
        assert.strictEqual(order3.nextOrder.toString(), "4", "ErrNext3 1a3");
        assert.strictEqual(order4.previousOrder.toString(), "3", "ErrPrev4 1a4");
        assert.strictEqual(order4.nextOrder.toString(), "5", "ErrNext3 1a4");
        assert.strictEqual(order5.previousOrder.toString(), "4", "ErrPrev5 1a5");
        assert.strictEqual(order5.nextOrder.toString(), "6", "ErrNext5 1a5");
        assert.strictEqual(order6.previousOrder.toString(), "5", "ErrPrev6 1a6");
        assert.strictEqual(order6.nextOrder.toString(), "0", "ErrNext6 1a6");

        firstOrderIndex = (await converterContract.firstOrderIndex()).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1a6");
        assert.strictEqual(lastOrderIndex, 6, "ErrLast 1a6");
      });

      it("Get 3 orders from order three, sending as parameter to retrieve 18 orders", async () => {
        const startOrder = 3;
        ordersIds = [3, 4, 5, 6];
        const ordersAmounts = [2000000, 2100000, 3200000, 1300000];
        const orders = await converterContract.getSellOrders(startOrder, 18);
        const returnedObject = checkGetOrders(orders, ordersIds, ordersAmounts);

        assert.strictEqual(
          returnedObject.checkOrdersOk,
          true,
          "getSellOrders invalid result"
        );
        assert.strictEqual(returnedObject.qty, 4, "wrong orders qty");
      });

      it("Get 6 orders from order 1, sending as a parameter to retrieve 18 orders", async () => {
        ordersIds = [1, 2, 3, 4, 5, 6];
        ordersAmounts = [1000000, 1500000, 2000000, 2100000, 3200000, 1300000];
        
        const orders = await converterContract.getSellOrders(1, 18);
        const returnedObject = checkGetOrders(orders, ordersIds, ordersAmounts);
        
        assert.strictEqual(
          returnedObject.checkOrdersOk,
          true,
          "getSellOrders invalid result"
        );
        assert.strictEqual(returnedObject.qty, 6, "wrong orders qty");
      });
    });
  }
);
