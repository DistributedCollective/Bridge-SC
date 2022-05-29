// Bring all the addresses deployed in rsk
const bscBSCBridge = require("../../../federator-env/testnet-BSC-RSK/btestnet.json");
const rskBSCBridge = require("../../../federator-env/testnet-BSC-RSK/rsktestnet.json");
const rskETHBridge = require("../../../federator-env/rinkeby-ETH-RSK/rsktestnet.json");
const ethETHBridge = require("../../../federator-env/rinkeby-ETH-RSK/rinkeby.json");

// Bring all the addresses deployed in kovan
//const kovanAddresses = require("../../../federator/config/kovan.json");

// Asign ABIs to each variable from the JSON
const bridgeABI = require("../../abis/Bridge.json");
const federationABI = require("../../abis/Federation.json");
const multiSigABI = require("../../abis/MultiSigWallet.json");
const allowTokensABI = require("../../abis/AllowTokens.json");
const erc777ConverterABI = require("../../abis/Erc777Converter.json");
const tokenABI = require("../build/contracts/AlternativeERC20Detailed.json").abi;

const abisObject = {
  bridgeABI,
  federationABI,
  multiSigABI,
  allowTokensABI,
  erc777ConverterABI,
  tokenABI,
};

// Build an object with all the rsk addresses
const rskBSCConfig = {
  bridge: rskBSCBridge.bridge,
  federation: rskBSCBridge.federation,
  multiSig: rskBSCBridge.multiSig,
  allowTokens: rskBSCBridge.allowTokens,
  erc777Converter: rskBSCBridge.erc777Converter,
};
const bscBSCConfig = {
  bridge: bscBSCBridge.bridge,
  federation: bscBSCBridge.federation,
  multiSig: bscBSCBridge.multiSig,
  allowTokens: bscBSCBridge.allowTokens,
  erc777Converter: bscBSCBridge.erc777Converter,
};
const rskETHConfig = {
  bridge: rskETHBridge.bridge,
  federation: rskETHBridge.federation,
  multiSig: rskETHBridge.multiSig,
  allowTokens: rskETHBridge.allowTokens,
  erc777Converter: rskETHBridge.erc777Converter,
};
const ethETHConfig = {
  bridge: ethETHBridge.bridge,
  federation: ethETHBridge.federation,
  multiSig: ethETHBridge.multiSig,
  allowTokens: ethETHBridge.allowTokens,
  erc777Converter: ethETHBridge.erc777Converter,
};

const DAI_Testnet = {
  token: "DAI",
  name: "Dai Stablecoin",
  4: {
    symbol: "DAI",
    address: "0x3939Bfc5C14C3Cbb6f72D584FE40Bb0003db03AC",
    decimals: 18,
  },
};
const USDC_Testnet = {
  token: "USDC",
  name: "USD Coin",
  4: {
    symbol: "USDC",
    address: "0xCEEebe8fb88e48FE862FC9B606Bf21670Cd0eC01",
    decimals: 6,
  },
};
const USDT_Testnet = {
  token: "USDT",
  name: "Tether USD",
  4: {
    symbol: "USDT",
    address: "0x53eB18dFf8890813cECEAB96B436e61580868B85",
    decimals: 6,
  },
};


// btestnet stable coins
const DAI_BTestnet = {
  token: "DAI",
  name: "Dai Stablecoin",
  97: {
    symbol: "DAI",
    address: "0x83241490517384cb28382bdd4d1534ee54d9350f",
    decimals: 18,
  },
};
const USDC_BTestnet = {
  token: "USDC",
  name: "USD Coin",
  97: {
    symbol: "USDC",
    address: "0x0b654c687dc8b828139406c070e0a34486e5072b",
    decimals: 18,
  },
};
const USDT_BTestnet = {
  token: "USDT",
  name: "Tether USD",
  97: {
    symbol: "USDT",
    address: "0x268e3bf855cbcdf8fe31ba3557a554ab2283351f",
    decimals: 18,
  },
};
const BUSD_BTestnet = {
  token: "BUSD",
  name: "Binance USD",
  97: {
    symbol: "BUSD",
    address: "0x137BEc8c83740920ebc4f29f51C7B65b75Beec83",
    decimals: 18,
  },
};

// btestnet eth token
const ETH_BTestnet = {
  token: "ETH",
  name: "ETH Binance pegged",
  97: {
    symbol: "ETH",
    address: "0x7d1FE4FdB0Afaf26ada5083A688139EbA10d3e1B",
    decimals: 18,
  },
};

// btestnet bnb token
const BNB_BTestnet = {
  token: "WBNB",
  name: "BNB",
  97: {
    symbol: "BNB",
    address: "0x68bD35422b457f315AA176743325a9F7C9830c68",
    decimals: 18,
  },
};

// btestnet sov
const SOV_BTestnet = {
  token: "bSOV",
  name: "Sovryn Token",
  97: {
    symbol: "bSOV",
    address: "0x6b8daa42b8ac9a0d826981a9990248bef60e2d4c",
    decimals: 18,
  },
};

// rinkeby sov
const SOV_Testnet = {
  token: "eSOV",
  name: "Sovryn Token",
  4: {
    symbol: "eSOV",
    address: "",
    decimals: 18,
  },
};

// RSK testnet Tokens
const SOV_RskTestnet = {
  token: "SOV",
  name: "Sovryn Token",
  31: {
    symbol: "SOV",
    address: "",
    decimals: 18,
  },
};

const RBTC_RskTestnet = {
  token: "WRBTC",
  name: "RBTC",
  31: {
    symbol: "RBTC",
    address: "",
    decimals: 18,
  },
};

// rskBSCbtestnet stable coins
const DAI_RskBSCTestnet = {
  token: "bsDAI",
  name: "Dai Stablecoin",
  31: {
    symbol: "bsDAI",
    address: "0x407ff7d4760d3a81b4740d268eb04490c7dfe7f2",
    decimals: 18,
  },
};
const USDC_RskBSCTestnet = {
  token: "bsUSDC",
  name: "USD Coin",
  31: {
    symbol: "bsUSDC",
    address: "0x3e2cf87e7ff4048a57f9cdde9368c9f4bfb43adf",
    decimals: 18,
  },
};
const USDT_RskBSCTestnet = {
  token: "bsUSDT",
  name: "Tether USD",
  31: {
    symbol: "bsUSDT",
    address: "0x43bc3f0ffff6c9bbf3c2eafe464c314d43f561de",
    decimals: 18,
  },
};
const BUSD_RskBSCTestnet = {
  token: "bsBUSD",
  name: "Binance USD",
  31: {
    symbol: "bsBUSD",
    address: "0x8c9abb6c9d8d15ddb7ada2e50086e1050ab32688",
    decimals: 18,
  },
};

// rskBSCbtestnet eth token
const ETH_RskBSCTestnet = {
  token: "ETH",
  name: "bsETH",
  31: {
    symbol: "bsETH",
    address: "0x793CE6F95912D5b43532c2116e1b68993d902272",
    decimals: 18,
  },
};

// rskBSCbtestnet bnb token
const BNB_RskBSCTestnet = {
  token: "bsBNB",
  name: "bsBNB",
  31: {
    symbol: "bsBNB",
    address: "0xafa6A1eb7E2282E8854822d2bB412b6db2cabA4E",
    decimals: 18,
  },
};

// rskETHtestnet stable coins
const DAI_RskETHTestnet = {
  token: "DAIes",
  name: "Dai Stablecoin",
  31: {
    symbol: "DAIes",
    address: "0x240e616AAF8e4bAe04888a9F2e21C48ac9ebD546",
    decimals: 18,
  },
};
const USDC_RskETHTestnet = {
  token: "USDCes",
  name: "USD Coin",
  31: {
    symbol: "USDCes",
    address: "0x1D85E25c95A3A21e7A3E05Aa0693Fb50221749D4",
    decimals: 18,
  },
};
const USDT_RskETHTestnet = {
  token: "USDTes",
  name: "Tether USD",
  31: {
    symbol: "USDTes",
    address: "0x6cD3162EDFdaeF9b4a6C7347EEEd463458aF5F20",
    decimals: 18,
  },
};

// testnet stable coins
const testnetStableCoins = {
  DAI_Testnet,
  USDT_Testnet,
  USDC_Testnet,
};

// btestnet stable coins
const btestnetStableCoins = {
  DAI_BTestnet,
  USDT_BTestnet,
  USDC_BTestnet,
  BUSD_BTestnet,
};

// btestnet ETH Token
const btestnetETHToken = {
  ETH_BTestnet
};

// btestnet BNB
const btestnetBNB = {
  BNB_BTestnet
};

// rsktestnet sov
const rsktestnetTokens = {
  SOV_RskTestnet
};

const rsktestnetRBTC = {
  RBTC_RskTestnet
};

// ropsten sov
const testnetSOV = {
  SOV_Testnet
};
// btestnet sov
const btestnetSOV = {
  SOV_BTestnet
};

// rskBSCtestnet stable coins
const rskbsctestnetStableCoins = {
  DAI_RskBSCTestnet,
  USDT_RskBSCTestnet,
  USDC_RskBSCTestnet,
  BUSD_RskBSCTestnet,
};

// rskBSCtestnet wth token
const rskbsctestnetETHToken = {
  ETH_RskBSCTestnet
};

// rskBSCtestnet bnb token
const rskbsctestnetBNB = {
  BNB_RskBSCTestnet
};

// rskETHtestnet stable coins
const rskethtestnetStableCoins = {
  DAI_RskETHTestnet,
  USDT_RskETHTestnet,
  USDC_RskETHTestnet
};

module.exports = {
  abisObject,
  rskBSCConfig,
  bscBSCConfig,
  rskETHConfig,
  ethETHConfig,
  testnetStableCoins,
  btestnetStableCoins,
  rsktestnetTokens,
  rskbsctestnetStableCoins,
  rskethtestnetStableCoins,
  btestnetETHToken,
  rskbsctestnetETHToken,
  btestnetBNB,
  rsktestnetRBTC,
  rskbsctestnetBNB,
  testnetSOV,
  btestnetSOV
};
