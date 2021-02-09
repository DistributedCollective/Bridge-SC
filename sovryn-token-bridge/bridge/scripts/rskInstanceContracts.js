const rskConfig = require('../federator/config/rsktestnet.json');
const {fixSignature, getSignature} = require('./utils/cryptoUtils');

const DAI_TOKEN ={token:'DAI',name:'DaiStablecoin',icon:'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0x6B175474E89094C44Da98b954EedeAC495271d0F/logo.png',31:{symbol:'rDAI',address:'0x8c9196780dce226ec911ef9007cd3b1c187a5244',decimals:18},42:{symbol:'DAI',address:'0x832915943cc51c0620f32dfbaf8b9addb0db25e1',decimals:18}};
const WETH_TOKEN ={token:'WETH',name:'WrappedEther',icon:'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2/logo.png',31:{symbol:'rWETH',address:'0x9ada402cc8e2bf27d20eaa3ab9eb29733cbf50c5',decimals:18},42:{symbol:'WETH',address:'0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9',decimals:18},};
const USDT_TOKEN ={token:'USDT',name:'TetherUSD',icon:'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xdAC17F958D2ee523a2206206994597C13D831ec7/logo.png',31:{symbol:'rUSDT',address:'0x821ce426dd93f48e787bab75a36a321089688fa5',decimals:18},42:{symbol:'USDT',address:'0x755de969cbc0e7df97eac28933c6a2385c087ca1',decimals:6},};
const RENBTC_TOKEN ={token:'RenBTC',name:'RenBTC',icon:'https://etherscan.io/token/images/renbtc_32.png',31:{symbol:'rRenBTC',address:'0xfa4b46d637c3601039c17b24803eafae873dd206',decimals:18},42:{symbol:'RenBTC',address:'0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a',decimals:8},};
const WBTC_TOKEN ={token:'WBTC',name:'WrappedBTC',icon:'https://etherscan.io/token/images/wbtc_28.png?v=1',31:{symbol:'rWBTC',address:'0xc5df59ab9a1cec5677946b29dc84a63011a58ba5',decimals:18},42:{symbol:'WBTC',address:'0xd871ce15efa071b06104dac4225540f5461d17de',decimals:8},};

const bridge = await Bridge.at(rskConfig.bridge)
const daiToken = await AlternativeERC20Detailed.at(DAI_TOKEN["31"].address);
const wEthToken = await AlternativeERC20Detailed.at(WETH_TOKEN["31"].address);
const usdtToken = await AlternativeERC20Detailed.at(USDT_TOKEN["31"].address);
const renBtcToken = await AlternativeERC20Detailed.at(RENBTC_TOKEN["31"].address);
const wBtcToken = await AlternativeERC20Detailed.at(WBTC_TOKEN["31"].address);

const account1 = accounts[0];
