const rskConfig = require('../federator/config/rsktestnet.json');
const {fixSignature, getSignature} = require('./utils/cryptoUtils');

const DAI_TOKEN ={token:'DAI',name:'DaiStablecoin',31:{symbol:'rDAI', address:'0xbd93b4b623d992703dd2ed66c48eb7eed8874ef1',decimals:18}};
const WETH_TOKEN ={token:'WETH',name:'WrappedEther',31:{symbol:'rWETH', address:'0x6a5d54d13807a9b362e8fa01fd8cfd6e3ffbbaa3',decimals:18},};
const USDT_TOKEN ={token:'USDT',name:'TetherUSD',31:{symbol:'rUSDT', address:'0x101e953909e959d839730b92ff7690a5a387feca',decimals:18},};
const RENBTC_TOKEN ={token:'RenBTC',name:'RenBTC',31:{symbol:'rRenBTC', address:'0x7c262a199ee02704a0a07cac0159b6b8a729e853',decimals:18},};
const WBTC_TOKEN ={token:'WBTC',name:'WrappedBTC',31:{symbol:'rWBTC', address:'0x8c7221e18c8722b593e840b2d16339e6c438d528',decimals:18},};

const bridge = await Bridge.at(rskConfig.bridge)
const daiToken = await AlternativeERC20Detailed.at(DAI_TOKEN["31"].address);
const wEthToken = await AlternativeERC20Detailed.at(WETH_TOKEN["31"].address);
const usdtToken = await AlternativeERC20Detailed.at(USDT_TOKEN["31"].address);
const renBtcToken = await AlternativeERC20Detailed.at(RENBTC_TOKEN["31"].address);
const wBtcToken = await AlternativeERC20Detailed.at(WBTC_TOKEN["31"].address);

const account1 = accounts[0];
