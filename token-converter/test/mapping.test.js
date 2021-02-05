const ConverterContract = artifacts.require("Converter");
const Bridge = artifacts.require("Bridge");

const assert = require("assert");
const truffleAssert = require("truffle-assertions");
const chai = require("chai");
const { expect } = require("chai");

chai.use(require("chai-as-promised"));

const { checkGetOrders, makeSellOrder } = require("./helpers/utilities");

const whiteListedToken = "0x35cA19131746B8A43F06B53fe0F0731a27328559";
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
    before(async function () {
      converterContract = await ConverterContract.deployed();
      bridge = await Bridge.new();
      await converterContract.setBridgeContract(bridge.address);
      await converterContract.addTokenToWhitelist(whiteListedToken);
    });

    describe("Called takeSellOrder should:", async () => {
      it("ACCEPT rBTC, fill an order - check maping", async () => {
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

        let orderId = (await converterContract.numOrder()).toNumber();
        let order = await converterContract.orders(orderId);

        console.log("orderId2 :>> ", orderId);
        console.log("nextOrder :>> ", order.nextOrder.toString());
        console.log("previousOrder :>> ", order.previousOrder.toString());

        assert.strictEqual(
          order.previousOrder.toString(),
          "0",
          "Wrong previous"
        );
        assert.strictEqual(order.nextOrder.toString(), "0", "Wrong next");

        // console.log('orderId :>> ', orderId);

        // await converterContract.setBridgeContract(bridge.address);
        // const rbtcValueToTransfer = 0.4;

        // const addressInContract = order.recipient;
        // const addressInTest = sellerAddress2;
        // assert.strictEqual(addressInContract, addressInTest, "");

        // const amountToBuy = web3.utils.toWei("0.4");
        // const remaining = BigInt(parseInt(orderAmount) - parseInt(amountToBuy));

        // console.log("orderAmount           :>> ", parseInt(orderAmount));
        // console.log("orderAmount           :>> ", typeof(orderAmount));
        // console.log("amountToBuy           :>> ", amountToBuy);
        // console.log("amountToBuy           :>> ", typeof(amountToBuy));
        // console.log("order.remainingAmount :>> ", order.remainingAmount.toString());
        // console.log("order.remainingAmount :>> ", typeof(order.remainingAmount));
        // console.log("remaining             :>> ", remaining);
        // console.log("remaining             :>> ", typeof(remaining));
        // console.log('nextOrder             :>> ', order.nextOrder.toString());
        // console.log('previousOrder         :>> ', order.previousOrder.toString());

        // const result = await converterContract.takeSellOrder(
        //   orderId,
        //   amountToBuy, // qty tokens to buy
        //   ethDestinationAddress,
        //   usersData[0],
        //   usersData[0],
        //   { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp1 }
        // );

        // // truffleAssert.eventEmitted(result, "SentToBridge");
        // // truffleAssert.eventEmitted(result, "TakeSellOrder");

        // order = await converterContract.orders(orderId);
        // // const order2 = await converterContract.orders(orderId);

        // console.log('orderId2               :>> ', orderId);
        // console.log('nextOrder2             :>> ', order.nextOrder.toString());
        // console.log('previousOrder2         :>> ', order.previousOrder.toString());
        // console.log("order.remainingAmount2 :>> ", order.remainingAmount.toString());
        // console.log("order.remainingAmount2 :>> ", typeof(order.remainingAmount));
        // console.log("orderAmount2           :>> ", order.orderAmount.toString());

        // assert.strictEqual(
        //   order.remainingAmount.toString(),
        //   remaining.toString(),
        //   ""
        // );
      });
    });
  }
);
