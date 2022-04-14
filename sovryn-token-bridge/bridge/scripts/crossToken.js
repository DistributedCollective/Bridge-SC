const MockERC20 = artifacts.require("MockERC20");
const AllowTokens = artifacts.require("AllowTokens");
const Bridge = artifacts.require("Bridge");

const user = "0x189Ec9a470F38Ee8Dc732b8fCC9d03624cD0d6A0";

module.exports = async (callback) => {
  try {
    console.log("Deploying mock token");
    const mockERC20 = await MockERC20.new();
    console.log("Mock token Deployed: ", mockERC20.address);
    const allowTokens = await AllowTokens.deployed();

    await allowTokens.addAllowedToken(mockERC20.address);
    await allowTokens.setFeeAndMinPerToken(mockERC20.address, 1, 1);
    console.log("Token allowed");

    const bridge = await Bridge.deployed();

    await mockERC20.mint(user, "100000000000000000000"); // 100 tokens
    console.log("Token minted");
    await mockERC20.approve(bridge.address, "100000000000000000000", {
      from: user,
    });
    console.log("Token approved");

    const res = await bridge.receiveTokens(mockERC20.address, "1000000", {
      from: user,
    });
    console.log("Tokens sent through the bridge");
    console.log(res);
  } catch (err) {
    console.log(`An error occured: ${err}`);
  }

  callback();
};
