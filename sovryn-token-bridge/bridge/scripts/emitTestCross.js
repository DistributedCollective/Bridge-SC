const MockBridge = artifacts.require("MockBridge");

const tokenToUse = "0xD12AE7796e43801C871EfEEbafd81724efA9fDAd";
const receiver = "0xb1965640a23a30B1F7f0142491b6970Ea7748BD4";
const amountMinusFees = 1_00_000_000_000_000;
const symbol = "TST";
const userData = "0x";
const decimals = "18";
const granularity = "1";

module.exports = async (callback) => {
  const mockBridge = await MockBridge.deployed();
  const res = await mockBridge.crossTokens(
    tokenToUse,
    receiver,
    amountMinusFees,
    symbol,
    userData,
    decimals,
    granularity
  );
  console.log(res.logs);
  callback();
};
