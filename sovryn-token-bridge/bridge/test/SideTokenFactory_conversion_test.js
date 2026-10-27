const SideTokenFactory = artifacts.require("./SideTokenFactory");
const SideToken = artifacts.require("./SideToken");
const Bridge = artifacts.require("./Bridge");
const BridgeV0 = artifacts.require("./Bridge_v0");
const Proxy = artifacts.require("./AdminUpgradeabilityProxy");
const AllowTokens = artifacts.require("./AllowTokens");
const Utils = artifacts.require("./Utils");
const { expectRevert } = require("@openzeppelin/test-helpers");

contract("SideTokenFactory attribute conversion", (accounts) => {
  const [primary, receiver, federation, outsider] = accounts;
  let factory;
  beforeEach(async () => {
    factory = await SideTokenFactory.new({ from: primary });
  });
  const tokenFrom = async (receipt) =>
    SideToken.at(
      receipt.logs.find((log) => log.event === "SideTokenCreated").args
        .sideToken
    );

  it("preserves the legacy creation topic and decoded symbol while adding readable attributes", async () => {
    const receipt = await factory.createSideToken("Token name", "TOK", 1);
    const legacy = receipt.logs.find((log) => log.event === "SideTokenCreated");
    assert.equal(legacy.args.symbol, "TOK");
    assert.equal(legacy.args.granularity.toString(), "1");
    const rich = receipt.logs.find(
      (log) => log.event === "SideTokenCreatedWithAttributes"
    );
    assert.equal(rich.args.sideToken, legacy.args.sideToken);
    assert.equal(rich.args.symbol, "TOK");
    assert.equal(rich.args.name, "Token name");
    assert.equal(rich.args.minter, primary);
    const raw = receipt.receipt.rawLogs.filter(
      (log) => log.address.toLowerCase() === factory.address.toLowerCase()
    );
    assert.equal(
      raw[0].topics[0],
      web3.utils.sha3("SideTokenCreated(address,string,uint256)")
    );
    assert.equal(
      web3.eth.abi.decodeParameters(["string", "uint256"], raw[0].data)[0],
      "TOK"
    );
  });

  it("converts only a configured symbol and keeps the original name when its override is empty", async () => {
    await factory.setTokenAttributesConversion("TOK", "NEW", "Converted");
    let token = await tokenFrom(
      await factory.createSideToken("Original", "TOK", 100)
    );
    assert.equal(await token.symbol(), "NEW");
    assert.equal(await token.name(), "Converted");
    assert.equal(await token.minter(), primary);
    assert.equal((await token.granularity()).toString(), "100");
    await factory.setTokenAttributesConversion("TOK", "OTHER", "");
    token = await tokenFrom(
      await factory.createSideToken("Original", "TOK", 1)
    );
    assert.equal(await token.symbol(), "OTHER");
    assert.equal(await token.name(), "Original");
    const unchanged = await tokenFrom(
      await factory.createSideToken("Untouched", "MISSING", 1)
    );
    assert.equal(await unchanged.symbol(), "MISSING");
    assert.equal(await unchanged.name(), "Untouched");
  });

  it("refuses unauthorized mapping writes and empty mapping keys or destination symbols", async () => {
    await expectRevert(
      factory.setTokenAttributesConversion("TOK", "NEW", "Name", {
        from: outsider,
      }),
      "Secondary: caller is not the primary account"
    );
    await expectRevert(
      factory.setTokenAttributesConversion("", "NEW", "Name"),
      "fromTokenSymbol must not be empty"
    );
    await expectRevert(
      factory.setTokenAttributesConversion("TOK", "", "Name"),
      "toTokenSymbol must not be empty"
    );
    const attrs = await factory.tokenAttributesConversion("TOK");
    assert.equal(attrs.toTokenSymbol, "");
    assert.equal(attrs.toTokenName, "");
  });

  it("preserves primary transfer and allows only the new primary to change mappings", async () => {
    await factory.transferPrimary(outsider);
    await expectRevert(
      factory.setTokenAttributesConversion("TOK", "NEW", "Name"),
      "Secondary: caller is not the primary account"
    );
    await factory.setTokenAttributesConversion("TOK", "NEW", "Name", {
      from: outsider,
    });
    const token = await tokenFrom(
      await factory.createSideToken("Original", "TOK", 1, { from: outsider })
    );
    assert.equal(await token.minter(), outsider);
    assert.equal(await token.symbol(), "NEW");
  });

  it("rejects empty creation names/symbols without creating tokens or changing mappings", async () => {
    await factory.setTokenAttributesConversion("TOK", "NEW", "Name");
    await expectRevert(
      factory.createSideToken("", "TOK", 1),
      "Side token name must not be empty"
    );
    await expectRevert(
      factory.createSideToken("Original", "", 1),
      "Side token symbol must not be empty"
    );
    assert.equal(
      (await factory.tokenAttributesConversion("TOK")).toTokenSymbol,
      "NEW"
    );
  });

  it("uses a preconfigured prefixed mapping through the real upgraded Bridge while preserving bridge mint authority", async () => {
    await factory.setTokenAttributesConversion("eTOK", "NEW", "Converted");
    const allowTokens = await AllowTokens.new(primary);
    const v0 = await BridgeV0.new();
    const initialization = v0.contract.methods
      .initialize(
        primary,
        federation,
        allowTokens.address,
        factory.address,
        "e"
      )
      .encodeABI();
    const proxy = await Proxy.new(v0.address, accounts[9], initialization);
    const utils = await Utils.new();
    await Bridge.detectNetwork();
    Bridge.link("Utils", utils.address);
    const implementation = await Bridge.new();
    await proxy.upgradeTo(implementation.address, { from: accounts[9] });
    const bridge = await Bridge.at(proxy.address);
    await factory.transferPrimary(bridge.address);
    await expectRevert(
      factory.setTokenAttributesConversion("eTOK", "BAD", "Bad"),
      "Secondary: caller is not the primary account"
    );
    const amount = web3.utils.toWei("1");
    await bridge.acceptTransfer(
      accounts[6],
      receiver,
      amount,
      "TOK",
      web3.utils.sha3("source block"),
      web3.utils.sha3("source transaction"),
      0,
      18,
      1,
      { from: federation }
    );
    const token = await SideToken.at(await bridge.mappedTokens(accounts[6]));
    assert.equal(await token.symbol(), "NEW");
    assert.equal(await token.name(), "Converted");
    assert.equal(await token.minter(), bridge.address);
    assert.equal((await token.balanceOf(receiver)).toString(), amount);
    assert.equal(await factory.primary(), bridge.address);
  });
});
