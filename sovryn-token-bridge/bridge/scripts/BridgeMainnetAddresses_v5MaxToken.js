// Bring all the addresses deployed in rsk
const bscBSCBridge = require("../../../federator-env/mainnet-BSC-RSK/bmainnet.json");
const rskBSCBridge = require("../../../federator-env/mainnet-BSC-RSK/rskmainnet.json");
const rskETHBridge = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet.json");
const ethETHBridge = require("../../../federator-env/mainnet-ETH-RSK/mainnet.json");

const bscBSCBridgeV5 = require("../../../federator-env/mainnet-BSC-RSK/bmainnet_v5.json");
const rskBSCBridgeV5 = require("../../../federator-env/mainnet-BSC-RSK/rskmainnet_v5.json");
const ethETHBridgeV5 = require("../../../federator-env/mainnet-ETH-RSK/mainnet_v5.json");
const rskETHBridgeV5 = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet_v5.json");

// Bring all the addresses deployed in kovan
//const kovanAddresses = require("../../../federator/config/kovan.json");

// Asign ABIs to each variable from the JSON
const bridgeABI = require("../../abis/Bridge.json");
const federationABI = require("../../abis/Federation.json");
const multiSigABI = require("../../abis/MultiSigWallet.json");
const allowTokensABI = require("../../abis/AllowTokens.json");
const erc777ConverterABI = require("../../abis/Erc777Converter.json");
const tokenABI = require("../build/contracts/AlternativeERC20Detailed.json").abi;

const allowTokensV5ABI = require("./OldAbis/AllowTokensV5.json");

const abisObject = {
  bridgeABI,
  federationABI,
  multiSigABI,
  allowTokensABI,
  erc777ConverterABI,
  tokenABI,
};

const abisObjectV5 = {
  bridgeABI,
  federationABI,
  multiSigABI,
  allowTokensV5ABI,
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

const bscBSCV5Config = {
  allowTokens: bscBSCBridgeV5.allowTokens,
};
const rskBSCV5Config = {
  allowTokens: rskBSCBridgeV5.allowTokens,
};
const ethETHV5Config = {
  allowTokens: ethETHBridgeV5.allowTokens,
};
const rskETHV5Config = {
  allowTokens: rskETHBridgeV5.allowTokens,
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

const DAI_Mainnet = {
  token: "DAI",
  name: "Dai Stablecoin",
  1: {
    symbol: "DAI",
    address: "0x6b175474e89094c44da98b954eedeac495271d0f",
    decimals: 18,
  },
};
const USDC_Mainnet = {
  token: "USDC",
  name: "USD Coin",
  1: {
    symbol: "USDC",
    address: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    decimals: 6,
  },
};
const USDT_Mainnet = {
  token: "USDT",
  name: "Tether USD",
  1: {
    symbol: "USDT",
    address: "0xdac17f958d2ee523a2206206994597c13d831ec7",
    decimals: 6,
  },
};


// bmainnet stable coins
const DAI_BMainnet = {
  token: "DAI",
  name: "Dai Stablecoin",
  56: {
    symbol: "DAI",
    address: "0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3",
    decimals: 18,
  },
};
const USDC_BMainnet = {
  token: "USDC",
  name: "USD Coin",
  56: {
    symbol: "USDC",
    address: "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
    decimals: 18,
  },
};
const USDT_BMainnet = {
  token: "USDT",
  name: "Tether USD",
  56: {
    symbol: "USDT",
    address: "0x55d398326f99059ff775485246999027b3197955",
    decimals: 18,
  },
};
const BUSD_BMainnet = {
  token: "BUSD",
  name: "Binance USD",
  56: {
    symbol: "BUSD",
    address: "0xe9e7cea3dedca5984780bafc599bd69add087d56",
    decimals: 18,
  },
};

// bmainnet eth token
const ETH_BMainnet = {
  token: "ETH",
  name: "ETH Binance pegged",
  56: {
    symbol: "ETH",
    address: "0x2170ed0880ac9a755fd29b2688956bd959f933f8",
    decimals: 18,
  },
};

// bmainnet bnb token
const BNB_BMainnet = {
  token: "WBNB",
  name: "BNB",
  56: {
    symbol: "BNB",
    address: "0xB6C313a427fa911A4C9a119e80Feea0fe20E69F0",
    decimals: 18,
  },
};

// bmainnet sov
const SOV_BMainnet = {
  token: "bSOV",
  name: "Sovryn Token",
  56: {
    symbol: "bSOV",
    address: "0x8753ede1b3a36358e4d7780f384f3f7a2d9e4359",
    decimals: 18,
  },
};

// mainnet sov
const SOV_Mainnet = {
  token: "eSOV",
  name: "Sovryn Token",
  1: {
    symbol: "eSOV",
    address: "0xbdab72602e9ad40fc6a6852caf43258113b8f7a5",
    decimals: 18,
  },
};

// mainnet Weth
const ETH_Mainnet = {
  token: "WETH",
  name: "WETH",
  1: {
    symbol: "WETH",
    address: "0xd412acd34a832a09c80c8a4895ff46d733f09538",
    decimals: 18,
  },
};


// RSK mainnet Tokens
const SOV_RskMainnet = {
  token: "SOV",
  name: "Sovryn Token",
  30: {
    symbol: "SOV",
    address: "0xefc78fc7d48b64958315949279ba181c2114abbd",
    decimals: 18,
  },
};

const RBTC_RskMainnet = {
  token: "WRBTC",
  name: "RBTC",
  30: {
    symbol: "WRBTC",
    address: "0xa233108b33dc77f1eee9d183ee1dc9725e76d475",
    decimals: 18,
  },
};

// rskETHmainnet eth token
const ETH_RskMainnet = {
  token: "ETH",
  name: "ETHes",
  30: {
    symbol: "ETHes",
    address: "0xfe878227c8f334038dab20a99fc3b373ffe0a755",
    decimals: 18,
  },
};

// rskBSCbmainnet stable coins
const DAI_RskBSCMainnet = {
  token: "DAIbs",
  name: "Dai Stablecoin",
  30: {
    symbol: "DAIbs",
    address: "0x6A42Ff12215a90f50866A5cE43A9c9C870116e76",
    decimals: 18,
  },
};
const USDC_RskBSCMainnet = {
  token: "USDCbs",
  name: "USD Coin",
  30: {
    symbol: "USDCbs",
    address: "0x91EDceE9567cd5612c9DEDeaAE24D5e574820af1",
    decimals: 18,
  },
};
const USDT_RskBSCMainnet = {
  token: "USDTbs",
  name: "Tether USD",
  30: {
    symbol: "USDTbs",
    address: "0xFf4299bCA0313C20A61dc5eD597739743BEf3f6d",
    decimals: 18,
  },
};
const BUSD_RskBSCMainnet = {
  token: "BUSDbs",
  name: "Binance USD",
  30: {
    symbol: "BUSDbs",
    address: "0x61e9604e31a736129d7f5C58964c75935b2d80D6",
    decimals: 18,
  },
};

// rskBSCbmainnet eth token
const ETH_RskBSCMainnet = {
  token: "ETH",
  name: "ETHbs",
  30: {
    symbol: "ETHbs",
    address: "0x30d1B36924c2c0CD1c03EC257D7FFf31bD8c3007",
    decimals: 18,
  },
};

// rskBSCbmainnet bnb token
const BNB_RskBSCMainnet = {
  token: "BNBbs",
  name: "BNBbs",
  30: {
    symbol: "BNBbs",
    address: "0xd2a826b78200c8434b957913ce4067e6e3169385",
    decimals: 18,
  },
};

// bscBSCbmainnet bRBTC token
const RBTC_BscBSCMainnet = {
  token: "bRBTC",
  name: "bRBTC",
  56: {
    symbol: "bRBTC",
    address: "0x68e75416a99f61a8ef3186b3bee41dbf2a3fd4e8",
    decimals: 18,
  },
};
// rskETHbmainnet stable coins
const DAI_RskETHMainnet = {
  token: "DAIes",
  name: "Dai Stablecoin",
  30: {
    symbol: "DAIes",
    address: "0x1A37c482465e78E6DAbE1Ec77B9a24D4236D2A11",
    decimals: 18,
  },
};
const USDC_RskETHMainnet = {
  token: "USDCes",
  name: "USD Coin",
  30: {
    symbol: "USDCes",
    address: "0x8D1f7CbC6391D95E2774380e80A666FEbf655D6b",
    decimals: 18,
  },
};
const USDT_RskETHMainnet = {
  token: "USDTes",
  name: "Tether USD",
  30: {
    symbol: "USDTes",
    address: "0xD9665EA8F5fF70Cf97E1b1Cd1B4Cd0317b0976e8",
    decimals: 18,
  },
};

// mainnet stable coins
const mainnetStableCoins = {
  DAI_Mainnet,
  USDT_Mainnet,
  USDC_Mainnet,
};

// bmainnet stable coins
const bmainnetStableCoins = {
  DAI_BMainnet,
  USDT_BMainnet,
  USDC_BMainnet,
  BUSD_BMainnet,
};

// bmainnet ETH Token
const bmainnetETHToken = {
  ETH_BMainnet
};

// bmainnet BNB
const bmainnetBNB = {
  BNB_BMainnet
};

// rskmainnet sov
const rskmainnetTokens = {
  SOV_RskMainnet
};

const rskmainnetRBTC = {
  RBTC_RskMainnet
};

// rskmainnet ETHes
const rskmainnetTokensETH = {
  ETH_RskMainnet
};

// mainnet ETH
const mainnetETH = {
  ETH_Mainnet
};

// mainnet sov
const mainnetSOV = {
  SOV_Mainnet
};
// bmainnet sov
const bmainnetSOV = {
  SOV_BMainnet
};

// rskBSCmainnet stable coins
const rskbscmainnetStableCoins = {
  DAI_RskBSCMainnet,
  USDT_RskBSCMainnet,
  USDC_RskBSCMainnet,
  BUSD_RskBSCMainnet,
};

// rskBSCmainnet wth token
const rskbscmainnetETHToken = {
  ETH_RskBSCMainnet
};

// rskBSCmainnet bnb token
const rskbscmainnetBNB = {
  BNB_RskBSCMainnet
};

// bscBSCbmainnet brbtc token
const bscbscbmainnetRBTC = {
  RBTC_BscBSCMainnet
};

// rskETHmainnet stable coins
const rskethmainnetStableCoins = {
  DAI_RskETHMainnet,
  USDT_RskETHMainnet,
  USDC_RskETHMainnet
};

module.exports = {
  abisObject,
  abisObjectV5,
  rskBSCConfig,
  bscBSCConfig,
  bscBSCV5Config,
  rskBSCV5Config,
  ethETHV5Config,
  rskETHV5Config,
  rskETHConfig,
  ethETHConfig,
  mainnetStableCoins,
  bmainnetStableCoins,
  rskmainnetTokens,
  rskbscmainnetStableCoins,
  rskethmainnetStableCoins,
  rskmainnetTokensETH,
  bmainnetETHToken,
  rskbscmainnetETHToken,
  bmainnetBNB,
  rskmainnetRBTC,
  rskbscmainnetBNB,
  bscbscbmainnetRBTC,
  mainnetSOV,
  bmainnetSOV,
  mainnetETH,
};
