const ConverterContract = artifacts.require("Converter");
const Bridge = artifacts.require("Bridge");
const MockSideToken = artifacts.require("MockSideToken");

const assert = require("assert");
const truffleAssert = require("truffle-assertions");
const chai = require("chai");
const { expect } = require("chai");

chai.use(require("chai-as-promised"));

const { makeSellOrder } = require("./helpers/utilities");

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

    describe("Called takeSellOrder INCORRECTLY should:", async () => {
      it("REJECT when eth destination address is null", async () => {
        await expect(
          converterContract.takeSellOrder(
            ordersIds[0], // order id
            500, // qty tokens to buy
            zeroAddress,
            usersData[0],
            usersData[0]
          )
        ).to.be.rejectedWith(Error, NOT_NULL_ERROR);
      });

      it("REJECT when contract is paused", async () => {
        await converterContract.pauseContract();
        await expect(
          converterContract.takeSellOrder(
            ordersIds[0], // order id
            500, // qty tokens to buy
            ethDestinationAddress,
            usersData[0],
            usersData[0]
          )
        ).to.be.rejectedWith(Error, PAUSED_ERROR);
        await converterContract.unpauseContract();
      });

      it("REJECT when order id does not exist", async () => {
        await expect(
          converterContract.takeSellOrder(
            10, // order id
            500, // qty tokens to buy
            ethDestinationAddress,
            usersData[0],
            usersData[0]
          )
        ).to.be.rejectedWith(Error, NOT_NULL_ERROR);
      });

      it("REJECT when amount to buy is ZERO", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        await makeSellOrder(
          converterContract,
          10,
          whiteListedToken,
          sellerAddresses[0],
          { from: bridgeAddress }
        );
        await converterContract.setBridgeContract(bridge.address);

        await expect(
          converterContract.takeSellOrder(
            ordersIds[0],
            0, // qty tokens to buy
            ethDestinationAddress,
            usersData[0],
            usersData[0]
          )
        ).to.be.rejectedWith(Error, ZERO_AMOUNT_ERROR);
      });

      it("REJECT when amount to buy is grater than remaining amount", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        await makeSellOrder(
          converterContract,
          10,
          whiteListedToken,
          sellerAddresses[0],
          { from: bridgeAddress }
        );
        await converterContract.setBridgeContract(bridge.address);

        await expect(
          converterContract.takeSellOrder(
            ordersIds[0],
            11, // qty tokens to buy
            ethDestinationAddress,
            usersData[0],
            usersData[0]
          )
        ).to.be.rejectedWith(
          Error,
          "Amount to buy must be equal or less than remaining tokens"
        );
      });

      it("REJECT when value transferred is less than amount to buy with discount", async () => {
        const orderAmount = web3.utils.toWei("10");

        await converterContract.setBridgeContract(bridgeAddress);
        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[0],
          { from: bridgeAddress }
        );
        await converterContract.setBridgeContract(bridge.address);

        const orderId = (await converterContract.numOrder()).toNumber();
        const order = await converterContract.orders(orderId);

        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);
        const rbtcValueToTransfer = 6;

        expect(order.remainingAmount.toString()).to.equal(orderAmount);

        await expect(
          converterContract.takeSellOrder(
            orderId,
            orderAmount, // qty tokens to buy
            ethDestinationAddress,
            usersData[0],
            usersData[0],
            { value: web3.utils.toWei(`${rbtcValueToTransfer}`) }
          )
        ).to.be.rejectedWith(Error, "Transferred Amount is less than expected");
      });
    });

    describe("Called takeSellOrder should:", async () => {
      it("ACCEPT rBTC, Emit transfer events", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        const orderAmount = web3.utils.toWei("1");
        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[0],
          { from: bridgeAddress }
        );

        const orderId = (await converterContract.numOrder()).toNumber();
        const order = await converterContract.orders(orderId);

        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 0.9;
        expect(order.remainingAmount.toString()).to.equal(orderAmount);

        const result = await converterContract.takeSellOrder(
          orderId,
          orderAmount, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp1 }
        );

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
      });

      it("ACCEPT rBTC, return to LP exceeded amount", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        const orderAmount = web3.utils.toWei("1");
        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[0],
          { from: bridgeAddress }
        );

        const orderId = (await converterContract.numOrder()).toNumber();
        const order = await converterContract.orders(orderId);

        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 2;
        expect(order.remainingAmount.toString()).to.equal(orderAmount);

        const feePercentageDivider = await converterContract.feePercentageDivider();
        const amountWithDiscount =
          orderAmount - (orderAmount * conversionFee) / feePercentageDivider;
        const prevBalanceLP = await web3.eth.getBalance(lp2);

        const result = await converterContract.takeSellOrder(
          orderId,
          orderAmount, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp2 }
        );

        const finalBalanceLP = await web3.eth.getBalance(lp2);
        const difBalance = prevBalanceLP - finalBalanceLP;
        const difBalanceOrder = Math.round(
          (difBalance - amountWithDiscount) / 10 ** 18
        );

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
        assert.strictEqual(difBalanceOrder, 0, "");
        // THIS CAN BE IMPROVED TO USE A MORE ACCURATE SOLUTION
      });

      it("ACCEPT rBTC, transfer to seller encoded address", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        const orderAmount = web3.utils.toWei("1");
        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[2],
          { from: bridgeAddress }
        );

        const orderId = (await converterContract.numOrder()).toNumber();
        const order = await converterContract.orders(orderId);

        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 0.9;
        expect(order.remainingAmount.toString()).to.equal(orderAmount);

        const feePercentageDivider = await converterContract.feePercentageDivider();
        const amountWithDiscount =
          orderAmount - (orderAmount * conversionFee) / feePercentageDivider;

        const addressInContract = order.recipient;
        const addressInTest = sellerAddress3;
        assert.strictEqual(addressInContract, addressInTest, "");

        const prevBalanceSeller = BigInt(
          await web3.eth.getBalance(sellerAddress3)
        );

        const result = await converterContract.takeSellOrder(
          orderId,
          orderAmount, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp1 }
        );

        const finalBalanceSeller = BigInt(
          await web3.eth.getBalance(sellerAddress3)
        );

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");
        assert.strictEqual(
          finalBalanceSeller,
          prevBalanceSeller + BigInt(amountWithDiscount),
          ""
        );
      });

      it("ACCEPT rBTC, fill partialy an order - check remaining after take sell order", async () => {
        await converterContract.setBridgeContract(bridgeAddress);
        const orderAmount = web3.utils.toWei("1");
        const conversionFee = 1000; // 10.00%
        await converterContract.setConversionFee(conversionFee);

        await converterContract.onTokensMinted(
          orderAmount,
          whiteListedToken,
          usersData[1],
          { from: bridgeAddress }
        );

        const orderId = (await converterContract.numOrder()).toNumber();
        let order = await converterContract.orders(orderId);

        await converterContract.setBridgeContract(bridge.address);
        const rbtcValueToTransfer = 0.4;

        const addressInContract = order.recipient;
        const addressInTest = sellerAddress2;
        assert.strictEqual(addressInContract, addressInTest, "");

        const amountToBuy = web3.utils.toWei("0.4");
        const remaining = BigInt(parseInt(orderAmount) - parseInt(amountToBuy));

        const result = await converterContract.takeSellOrder(
          orderId,
          amountToBuy, // qty tokens to buy
          ethDestinationAddress,
          usersData[0],
          usersData[0],
          { value: web3.utils.toWei(`${rbtcValueToTransfer}`), from: lp1 }
        );

        truffleAssert.eventEmitted(result, "SentToBridge");
        truffleAssert.eventEmitted(result, "TakeSellOrder");

        order = await converterContract.orders(orderId);
        assert.strictEqual(
          order.remainingAmount.toString(),
          remaining.toString(),
          ""
        );
      });
    });
  }
);
