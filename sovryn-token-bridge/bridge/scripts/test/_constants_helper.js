// Bring all the addresses deployed in rsk
const rskAddresses = require("../../../federator/config/rsktestnet.json");

// Bring all the addresses deployed in kovan
const kovanAddresses = require("../../../federator/config/kovan.json");

// Asign ABIs to each variable from the JSON
const bridgeABI = require("../../build/contracts/Bridge.json").abi;
const federationABI = require("../../build/contracts/Federation.json").abi;
const multiSigABI = require("../../build/contracts/MultiSigWallet.json").abi;
const allowTokensABI = require("../../build/contracts/AllowTokens.json").abi;
const tokenABI = require("../../build/contracts/AlternativeERC20Detailed.json").abi;
const converterABI = require("../../../../token-converter/build/contracts/Converter.json")
  .abi;
const converterAddress = require("../../../../token-converter/build/contracts/Converter.json")
  .networks["31"].address;

const abisObject = {
  bridgeABI,
  federationABI,
  multiSigABI,
  allowTokensABI,
  tokenABI,
  converterABI,
};

// Build an object with all the rsk addresses
const rskConfig = {
  bridge: rskAddresses.bridge,
  federation: rskAddresses.federation,
  multiSig: rskAddresses.multiSig,
  allowTokens: rskAddresses.allowTokens,
  converter: converterAddress,
};

// Build an object with all the kovan addresses
const kovanConfig = {
  bridge: kovanAddresses.bridge,
  federation: kovanAddresses.federation,
  multiSig: kovanAddresses.multiSig,
  allowTokens: kovanAddresses.allowTokens,
  converter: converterAddress,
};

// rTokens definition
const rWETH_TOKEN = {
  token: "rWETH",
  name: "WrappedEther",
  31: {
    symbol: "rWETH",
    address: "0x45414a3072c577f0397f137458bf71a06e769354",
    decimals: 18,
  },
};
const rRENBTC_TOKEN = {
  token: "rRenBTC",
  name: "RenBTC",
  31: {
    symbol: "rRenBTC",
    address: "0x7dd5068e1967da72c751e5041864368800c14908",
    decimals: 18,
  },
};
const rDAI_TOKEN = {
  token: "rDAI",
  name: "DaiStablecoin",
  31: {
    symbol: "rDAI",
    address: "0xbd93b4b623d992703dd2ed66c48eb7eed8874ef1",
    decimals: 18,
  },
};
const rUSDT_TOKEN = {
  token: "rUSDT",
  name: "TetherUSD",
  31: {
    symbol: "rUSDT",
    address: "0x101e953909e959d839730b92ff7690a5a387feca",
    decimals: 18,
  },
};
const rWBTC_TOKEN = {
  token: "rWBTC",
  name: "WrappedBTC",
  31: {
    symbol: "rWBTC",
    address: "0x8c7221e18c8722b593e840b2d16339e6c438d528",
    decimals: 18,
  },
};

// rTokens Object
const rskTestnetTokens = {
  rWETH_TOKEN,
  rRENBTC_TOKEN,
  rDAI_TOKEN,
  rUSDT_TOKEN,
  rWBTC_TOKEN,
};

// kovan tokens definition
const WETH_TOKEN = {
  token: "WETH",
  name: "Wrapped Ether",
  icon:
  "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2/logo.png",
  42: {
    symbol: "WETH",
    address: "0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9",
    decimals: 18,
  },
};
const RENBTC_TOKEN = {
  token: "RenBTC",
  name: "Ren BTC",
  icon: "https://etherscan.io/token/images/renbtc_32.png",
  42: {
    symbol: "RenBTC",
    address: "0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a",
    decimals: 8,
  },
};
const DAI_TOKEN = {
  token: "DAI",
  name: "Dai Stablecoin",
  icon:
  "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0x6B175474E89094C44Da98b954EedeAC495271d0F/logo.png",
  42: {
    symbol: "DAI",
    address: "0x832915943cc51c0620f32dfbaf8b9addb0db25e1",
    decimals: 18,
  },
};
const USDT_TOKEN = {
  token: "USDT",
  name: "Tether USD",
  icon:
  "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xdAC17F958D2ee523a2206206994597C13D831ec7/logo.png",
  42: {
    symbol: "USDT",
    address: "0x755de969cbc0e7df97eac28933c6a2385c087ca1",
    decimals: 6,
  },
};
const WBTC_TOKEN = {
  token: "WBTC",
  name: "Wrapped BTC",
  icon: "https://etherscan.io/token/images/wbtc_28.png?v=1",
  42: {
    symbol: "WBTC",
    address: "0xd871ce15efa071b06104dac4225540f5461d17de",
    decimals: 8,
  },
};

// kovan token object
const kovanTokens = {
  WETH_TOKEN,
  RENBTC_TOKEN,
  DAI_TOKEN,
  USDT_TOKEN,
  WBTC_TOKEN,
};

module.exports = {
  abisObject,
  rskConfig,
  kovanConfig,
  rskTestnetTokens,
  kovanTokens,
};
