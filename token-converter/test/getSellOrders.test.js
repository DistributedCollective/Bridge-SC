const ConverterContract = artifacts.require("Converter");
const MockBridge = artifacts.require("MockBridge");
const MockSideToken = artifacts.require("MockSideToken");
const assert = require("assert");
const chai = require("chai");
chai.use(require("chai-as-promised"));
const { checkGetOrders, checkTokenOrders } = require("./helpers/utilities");

let ordersIds = [1, 2, 3, 4, 5, 6];
let ordersAmounts = [1000000, 1500000, 2000000, 2100000, 3200000, 1300000];
let ordersTotalToken1 = ordersAmounts[0] + ordersAmounts[5];
let ordersTotalToken2 =
  ordersAmounts[1] + ordersAmounts[2] + ordersAmounts[3] + ordersAmounts[4];

contract(
  "Converter",
  ([bridgeAddress, sellerAddress1, sellerAddress2, sellerAddress3]) => {
    const sellerAddresses = [sellerAddress1, sellerAddress2, sellerAddress3];
    const usersData = sellerAddresses.map((address) =>
      web3.eth.abi.encodeParameter("address", address)
    );
    let converterContract;
    let bridge;
    let whiteListedToken1;
    let whiteListedToken2;

    before(async function () {
      converterContract = await ConverterContract.deployed();
      bridge = await MockBridge.new();
      await converterContract.setBridgeContract(bridge.address);
      whiteListedToken1 = (await MockSideToken.new()).address;
      whiteListedToken2 = (await MockSideToken.new()).address;
      await converterContract.addTokenToWhitelist(whiteListedToken1);
      await converterContract.addTokenToWhitelist(whiteListedToken2);
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

        const sideToken1 = await MockSideToken.at(whiteListedToken1);
        const sideToken2 = await MockSideToken.at(whiteListedToken2);

        const oldBalanceToken1 = await sideToken1.balanceOf(
          converterContract.address
        );
        const oldBalanceToken2 = await sideToken2.balanceOf(
          converterContract.address
        );

        await converterContract.onTokensMinted(
          ordersAmounts[0],
          whiteListedToken1,
          usersData[1],
          { from: bridgeAddress }
        );
        sideToken1.mint(
          converterContract.address,
          ordersAmounts[0],
          Buffer.from(""),
          Buffer.from("")
        );
        orderId1 = (await converterContract.numOrder()).toNumber();
        let order1 = await converterContract.orders(orderId1);

        await converterContract.onTokensMinted(
          ordersAmounts[1],
          whiteListedToken2,
          usersData[1],
          { from: bridgeAddress }
        );
        sideToken2.mint(
          converterContract.address,
          ordersAmounts[1],
          Buffer.from(""),
          Buffer.from("")
        );
        orderId2 = (await converterContract.numOrder()).toNumber();
        let order2 = await converterContract.orders(orderId2);

        await converterContract.onTokensMinted(
          ordersAmounts[2],
          whiteListedToken2,
          usersData[1],
          { from: bridgeAddress }
        );

        sideToken2.mint(
          converterContract.address,
          ordersAmounts[2],
          Buffer.from(""),
          Buffer.from("")
        );
        orderId3 = (await converterContract.numOrder()).toNumber();
        let order3 = await converterContract.orders(orderId3);

        await converterContract.onTokensMinted(
          ordersAmounts[3],
          whiteListedToken2,
          usersData[1],
          { from: bridgeAddress }
        );

        sideToken2.mint(
          converterContract.address,
          ordersAmounts[3],
          Buffer.from(""),
          Buffer.from("")
        );
        orderId4 = (await converterContract.numOrder()).toNumber();
        let order4 = await converterContract.orders(orderId4);

        await converterContract.onTokensMinted(
          ordersAmounts[4],
          whiteListedToken2,
          usersData[1],
          { from: bridgeAddress }
        );

        sideToken2.mint(
          converterContract.address,
          ordersAmounts[4],
          Buffer.from(""),
          Buffer.from("")
        );
        orderId5 = (await converterContract.numOrder()).toNumber();
        let order5 = await converterContract.orders(orderId5);

        await converterContract.onTokensMinted(
          ordersAmounts[5],
          whiteListedToken1,
          usersData[1],
          { from: bridgeAddress }
        );

        sideToken1.mint(
          converterContract.address,
          ordersAmounts[5],
          Buffer.from(""),
          Buffer.from("")
        );
        orderId6 = (await converterContract.numOrder()).toNumber();
        let order6 = await converterContract.orders(orderId6);

        order1 = await converterContract.orders(orderId1);
        order2 = await converterContract.orders(orderId2);
        order3 = await converterContract.orders(orderId3);
        order4 = await converterContract.orders(orderId4);
        order5 = await converterContract.orders(orderId5);

        assert.strictEqual(
          order1.previousOrder.toString(),
          "0",
          "ErrPrev1 1a3"
        );
        assert.strictEqual(order1.nextOrder.toString(), "2", "ErrNext1 1a3");
        assert.strictEqual(
          order2.previousOrder.toString(),
          "1",
          "ErrPrev2 1a3"
        );
        assert.strictEqual(order2.nextOrder.toString(), "3", "ErrNext2 1a3");
        assert.strictEqual(
          order3.previousOrder.toString(),
          "2",
          "ErrPrev3 1a3"
        );
        assert.strictEqual(order3.nextOrder.toString(), "4", "ErrNext3 1a3");
        assert.strictEqual(
          order4.previousOrder.toString(),
          "3",
          "ErrPrev4 1a4"
        );
        assert.strictEqual(order4.nextOrder.toString(), "5", "ErrNext3 1a4");
        assert.strictEqual(
          order5.previousOrder.toString(),
          "4",
          "ErrPrev5 1a5"
        );
        assert.strictEqual(order5.nextOrder.toString(), "6", "ErrNext5 1a5");
        assert.strictEqual(
          order6.previousOrder.toString(),
          "5",
          "ErrPrev6 1a6"
        );
        assert.strictEqual(order6.nextOrder.toString(), "0", "ErrNext6 1a6");

        firstOrderIndex = (
          await converterContract.firstOrderIndex()
        ).toNumber();
        lastOrderIndex = (await converterContract.lastOrderIndex()).toNumber();
        assert.strictEqual(firstOrderIndex, 1, "ErrFirst 1a6");
        assert.strictEqual(lastOrderIndex, 6, "ErrLast 1a6");

        const newBalanceToken1 = await sideToken1.balanceOf(
          converterContract.address
        );
        const newBalanceToken2 = await sideToken2.balanceOf(
          converterContract.address
        );

        expect(newBalanceToken1.toString()).to.equal(
          (oldBalanceToken1.toNumber() + ordersTotalToken1).toString()
        );
        expect(newBalanceToken2.toString()).to.equal(
          (oldBalanceToken2.toNumber() + ordersTotalToken2).toString()
        );
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

      it("Return the correct token addresses when getting all 6 orders", async () => {
        const tokenOrders = [
          whiteListedToken1,
          whiteListedToken2,
          whiteListedToken2,
          whiteListedToken2,
          whiteListedToken2,
          whiteListedToken1,
        ];
        ordersIds = [1, 2, 3, 4, 5, 6];

        const orders = await converterContract.getSellOrders(1, 6);
        const returnedObject = checkTokenOrders(orders, ordersIds, tokenOrders);

        assert.strictEqual(returnedObject, true);
      });
    });
  }
);
