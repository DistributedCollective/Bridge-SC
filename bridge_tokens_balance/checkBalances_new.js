var StatsD = require('hot-shots');
var dogstatsd = new StatsD();
const { createLogger, format, transports } = require('winston');
const BigNumber = require('bignumber.js');

var metrics = require('datadog-metrics');
metrics.init({ host: 'bridge-balance-checker', prefix: 'bridge.balance.' });
const ETHs_deficit = 36799000000000000000*1E-18;
const bridgeABI = require('../sovryn-token-bridge/abis/Bridge.json');

const Web3 = require('web3');
const log4js = require('log4js');
const Scheduler = require('./services/Scheduler.js');
const logConfig = require('./log-config.json');
log4js.configure(logConfig);

const pollingInterval = 1000*60*2;

const xusd	= "0x1440d19436bEeaF8517896bffB957a88EC95a00F";
const eths	= "0x4bF113905d7F69202106f613308bb02c84aaDF2F";
const bnbs	= "0xafD905Fe2EdBF5A7367A73B0F1e6a62Cb5E27D3e";

const rsk_BSCBridge = "0x971b97c8cc82e7d27bc467c2dc3f219c6ee2e350";
const rsk_ETH = "0x1CcAd820B6d031B41C54f1F3dA11c0d48b399581";
const bsc_BSCBridge = "0xdfc7127593c8af1a17146893f10e08528f4c2aa7";
const eth_ETH = "0x33C0D33a0d4312562ad622F91d12B0AC47366EE1"; 
const multisig_rsk_BSCBridge = "0xee9ea57555d9533d71f6f77e0e480961f068a6c5";
const multisig_rsk_ETH = "0xB64322e10b5aE1BE121B8Bb0dead560c53d9Dbc3";

const rskHost = "http://18.221.155.102:4444/";
const ethHost = "https://mainnet.infura.io/v3/728946296ea64626941bb3d120d16333";
const bscHost = "https://bsc-dataseed1.defibit.io/";


const web3RSK = new Web3(rskHost);
const web3ETH = new Web3(ethHost);
const web3BSC = new Web3(bscHost);

const logger = log4js.getLogger('Check Balances');

let scheduler = new Scheduler(pollingInterval, logger, { run: () => run() });


function Tokens(chain, bridge, symbol, address, decimals, amount) {
    this.chain = chain;
    this.bridge = bridge;
    this.symbol = symbol;
    this.address = address;
    this.decimals = decimals;
    this.amount = amount;
}

let myTokens = [
    new Tokens('eth', 'ETH' ,'DAI', '0x6b175474e89094c44da98b954eedeac495271d0f', 18, 0),
    new Tokens('eth', 'ETH' ,'USDC', '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 6, 0),
    new Tokens('eth', 'ETH' ,'USDT', '0xdac17f958d2ee523a2206206994597c13d831ec7', 6, 0),
    new Tokens('bsc', 'BSC' ,'DAI', '0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3', 18, 0),
    new Tokens('bsc', 'BSC' ,'USDC', '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d', 18, 0),
    new Tokens('bsc', 'BSC' ,'USDT', '0x55d398326f99059ff775485246999027b3197955', 18, 0),
    new Tokens('bsc', 'BSC' ,'BUSD', '0xe9e7cea3dedca5984780bafc599bd69add087d56', 18, 0),
    new Tokens('bsc', 'BSC' ,'ETH' ,'0x2170ed0880ac9a755fd29b2688956bd959f933f8', 18, 0),
    // new Tokens('rsk', 'ETH' ,'SOV', '0xEfC78FC7D48B64958315949279bA181C2114abbD', 18, 0),
    // new Tokens('eth', 'ETH' ,'eSOV', '0xbdab72602e9ad40fc6a6852caf43258113b8f7a5', 18, 0),
    // new Tokens('rsk', 'BSC' ,'SOV', '0xEfC78FC7D48B64958315949279bA181C2114abbD', 18, 0),
    // new Tokens('bsc', 'BSC' ,'bSOV', '0x8753ede1b3a36358e4d7780f384f3f7a2d9e4359', 18, 0),
];

let tokensOnXUSDAgg = [
    new Tokens('rsk', 'ETH' ,'DAIes', '0x1A37c482465e78E6DAbE1Ec77B9a24D4236D2A11', 18, 0),
    new Tokens('rsk', 'ETH' ,'USDCes', '0x8D1f7CbC6391D95E2774380e80A666FEbf655D6b', 18, 0),
    new Tokens('rsk', 'ETH' ,'USDTes', '0xD9665EA8F5fF70Cf97E1b1Cd1B4Cd0317b0976e8', 18, 0),
    new Tokens('rsk', 'BSC' ,'DAIbs', '0x6A42Ff12215a90f50866A5cE43A9c9C870116e76', 18, 0),
    new Tokens('rsk', 'BSC' ,'USDCbs', '0x91EDceE9567cd5612c9DEDeaAE24D5e574820af1', 18, 0),
    new Tokens('rsk', 'BSC' ,'USDTbs', '0xFf4299bCA0313C20A61dc5eD597739743BEf3f6d', 18, 0),
    new Tokens('rsk', 'BSC' ,'BUSDbs', '0x61e9604e31a736129d7f5C58964c75935b2d80D6', 18, 0),
];

let tokensOnETHsAgg = [
    new Tokens('rsk', 'ETH' ,'ETHes', '0xFe878227c8F334038DAb20a99fC3B373fFe0a755', 18, 0),
    new Tokens('rsk', 'BSC' ,'ETHbs', '0x30d1B36924c2c0CD1c03EC257D7FFf31bD8c3007', 18, 0),
];

let tokensOnBNBsAgg = [
    new Tokens('rsk', 'BSC' ,'BNBbs', '0xd2a826b78200c8434b957913ce4067e6e3169385', 18, 0),
];

let myNativeTokens = [
    new Tokens('eth', 'ETH' ,'ETH', '', 18, 0),
    new Tokens('bsc', 'BSC' ,'BNB', '', 18, 0),
    // new Tokens('rsk', 'ETH' ,'RBTC', '', 0),
    // new Tokens('rsk', 'BSC' ,'RBTC', '', 0),
];

const tokenABI = [
    {
      "constant": true,
      "inputs": [{ "name": "_owner", "type": "address" }],
      "name": "balanceOf",
      "outputs": [{ "name": "balance", "type": "uint256" }],
      "type": "function",
    },
  ];

async function getNativeFees() {

}

async function getBalances() {
    // myTokens.forEach(async function (token) {
    let i = 0;    
    for(token of myTokens){
    
    let tokenAddress = token.address.toLowerCase();
    let decimal = token.decimals;
    let web3Obj;
    let addressSC;

    if (token.chain === 'rsk') {
        web3Obj = web3RSK;
        if (token.bridge === 'ETH') {
            addressSC = rsk_ETH;
        }
        else {
            addressSC = rsk_BSCBridge;
        }
    } 
    else if (token.chain === 'eth') {
        web3Obj = web3ETH;
        addressSC = eth_ETH;
    }
    else {
        web3Obj = web3BSC;
        addressSC = bsc_BSCBridge;
    };

    try {
        let amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
        myTokens[i].amount = amount;
        //logger.log('info', tokenSymbol + ": " + myTokens[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
    }
    catch(e) {
        logger.log('info', `XXXfailed to load balance`);
    }
    i++;
    };
};  

async function getBalance(tokenAddress, web3Obj, addressSC, decimal) {
    let result;
    let format;
    try {
        const contract = await new web3Obj.eth.Contract(tokenABI, tokenAddress);
        result = await contract.methods.balanceOf(addressSC).call();
        format = (10 ** (18-decimal)) * web3Obj.utils.fromWei(result);   
        return format;    
    } catch(e) {
        logger.log('info', `failed to load balance of ${addressSC} for token ${tokenAddress} `);
    }
    
};

async function getNativeBalances() {
    // myNativeTokens.forEach(async function (token) {
    let i = 0;    
    for(token of myNativeTokens){
    let web3Obj;
    let addressSC;
    let amount;

    if (token.chain === 'rsk') {
        web3Obj = web3RSK;
        if (token.bridge === 'ETH') {
            addressSC = rsk_ETH;
        }
        else {
            addressSC = rsk_BSCBridge;
        }
    } 
    else if (token.chain === 'eth') {
        web3Obj = web3ETH;
        addressSC = eth_ETH;
    }
    else {
        web3Obj = web3BSC;
        addressSC = bsc_BSCBridge;
    };

    try {
        const contract = await new web3Obj.eth.Contract(bridgeABI, addressSC);
        let fees = await contract.methods.ethFeeCollected.call().call();
        fees =  web3Obj.utils.fromWei(fees, 'ether')
        amount = await getNativeBalance(web3Obj, addressSC);
        amount = amount - fees;
        myNativeTokens[i].amount = amount;
        //logger.log('info', "Native: " + tokenSymbol + ": " + myNativeTokens[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
    }
    catch(e) {
        logger.log('info', `XXXNative failed to load balance`);
    }

    i++;
    };
};  

async function getNativeBalance( web3Obj, addressSC) {
    let result;
    let amount;
    try {
        result =  await web3Obj.eth.getBalance(addressSC);
        amount =  web3Obj.utils.fromWei(result, 'ether')
        return amount;
    } catch(e) {
        logger.log('info', `failed to load balance of ${addressSC} `);
    } 
};

async function getXUSDAggBalances() {
    // tokensOnXUSDAgg.forEach(async function (token) {
    let i = 0;    
    for(token of tokensOnXUSDAgg){
        let tokenAddress = token.address.toLowerCase();
        let decimal = token.decimals;
        let web3Obj =web3RSK;
        let amount;

        let addressSC = xusd.toLowerCase();        
        try {
            amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
            tokensOnXUSDAgg[i].amount = amount;
            //logger.log('info', tokenSymbol + ": " + tokensOnXUSDAgg[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
        }
        catch(e) {
            logger.log('info', `XXXfailed to load balance`);
        }
        
        if(token.bridge === 'BSC') {
            addressSC = multisig_rsk_BSCBridge.toLowerCase();        
        } else {
            addressSC = multisig_rsk_ETH.toLowerCase();        
        }
            try {
            amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
            tokensOnXUSDAgg[i].amount = tokensOnXUSDAgg[i].amount + amount;
            //logger.log('info', tokenSymbol + ": " + tokensOnXUSDAgg[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
        }
        catch(e) {
            logger.log('info', `XXXfailed to load balance`);
        }

        i++;
    };
};

async function getETHSAggBalances() {
    //tokensOnETHsAgg.forEach(async function (token) {
    let i = 0;    
    for(token of tokensOnETHsAgg){
        let tokenAddress = token.address.toLowerCase();
        let decimal = token.decimals;
        let web3Obj =web3RSK;
        let amount;
        let ETHesDelta;

        let addressSC = eths.toLowerCase();
        try {
            amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
            tokensOnETHsAgg[i].amount = amount;
            //logger.log('info', tokenSymbol + ": " + tokensOnETHsAgg[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
        }
        catch(e) {
            logger.log('info', `XXXfailed to load balance`);
        };

        if(token.bridge === 'BSC') {
            addressSC = multisig_rsk_BSCBridge.toLowerCase();
            ETHesDelta = 0;        
        } else {
            addressSC = multisig_rsk_ETH.toLowerCase();        
            ETHesDelta = ETHs_deficit;
        };

        try {
            amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
            tokensOnETHsAgg[i].amount =  tokensOnETHsAgg[i].amount + amount - ETHesDelta;
            //logger.log('info', tokenSymbol + ": " + tokensOnETHsAgg[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
        }
        catch(e) {
            logger.log('info', `ETHS failed to load balance`);
        };
        i++
    };
};

async function getBNBSAggBalances() {
    //tokensOnBNBsAgg.forEach(async function (token) {
    let i = 0;    
    for(token of tokensOnBNBsAgg){
        let tokenAddress = token.address.toLowerCase();
        let decimal = token.decimals;
        let web3Obj =web3RSK;
        let amount;

        let addressSC = bnbs.toLowerCase();
        try {
            amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
            tokensOnBNBsAgg[i].amount = amount;
            //logger.log('info', tokenSymbol + ": " + tokensOnBNBsAgg[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
        }
        catch(e) {
            logger.log('info', `XXXfailed to load balance`);
        }

        if(token.bridge === 'BSC') {
            addressSC = multisig_rsk_BSCBridge.toLowerCase();        
        } else {
            addressSC = multisig_rsk_ETH.toLowerCase();        
        }
        
        try {
            amount =  await getBalance(tokenAddress, web3Obj, addressSC, decimal);
            tokensOnBNBsAgg[i].amount = amount + tokensOnBNBsAgg[i].amount;
            //logger.log('info', tokenSymbol + ": " + tokensOnBNBsAgg[i].amount + " Bridge: " + token.bridge + " Chain: " + token.chain);
        }
        catch(e) {
            logger.log('info', `XXXfailed to load balance`);
        }
        i++;
    };  
};  

async function printLogs() {
    //Bridge-ETH ETH ETHes
    logger.log('info', "Bridge-" + myNativeTokens[0].bridge + " " + myNativeTokens[0].symbol + " " +myNativeTokens[0].amount + 
        " "  + tokensOnETHsAgg[0].symbol + " " +tokensOnETHsAgg[0].amount+ " Delta: " + `${myNativeTokens[0].amount - tokensOnETHsAgg[0].amount}`,{color: 'blue' });
    //Bridge-BSC ETH ETHbs
    logger.log('info', "Bridge-" + myTokens[7].bridge + " " + myTokens[7].symbol + " " +myTokens[7].amount + 
        " "  + tokensOnETHsAgg[1].symbol + " " +tokensOnETHsAgg[1].amount+ " Delta: " + `${myTokens[7].amount - tokensOnETHsAgg[1].amount}`);
    //Bridge-BSC BNB BNBbs
    logger.log('info', "Bridge-" + myNativeTokens[1].bridge + " " + myNativeTokens[1].symbol + " " + myNativeTokens[1].amount + 
        " " + tokensOnBNBsAgg[0].symbol + " " + tokensOnBNBsAgg[0].amount+ " Delta: " + `${myNativeTokens[1].amount - tokensOnBNBsAgg[0].amount}`);
    //Bridge-ETH DAI DAIes
    logger.log('info', "Bridge-" + myTokens[0].bridge + " " + myTokens[0].symbol + " " + myTokens[0].amount + 
        " " + tokensOnXUSDAgg[0].symbol + " " + tokensOnXUSDAgg[0].amount+ " Delta: " + `${myTokens[0].amount - tokensOnXUSDAgg[0].amount}`);
    //Bridge-ETH USDC USDCes
    logger.log('info', "Bridge-" + myTokens[1].bridge + " " + myTokens[1].symbol + " " + myTokens[1].amount + 
        " " + tokensOnXUSDAgg[1].symbol + " " + tokensOnXUSDAgg[1].amount+ " Delta: " + `${myTokens[1].amount - tokensOnXUSDAgg[1].amount}`);
    //Bridge-ETH USDT USDTes
    logger.log('info', "Bridge-" + myTokens[2].bridge + " " + myTokens[2].symbol + " " + myTokens[2].amount + 
        " " + tokensOnXUSDAgg[2].symbol + " " + tokensOnXUSDAgg[2].amount+ " Delta: " + `${myTokens[2].amount - tokensOnXUSDAgg[2].amount}`);
    //Bridge-BSC DAI DAIbs
    logger.log('info', "Bridge-" + myTokens[3].bridge + " " + myTokens[3].symbol + " " + myTokens[3].amount + 
        " " + tokensOnXUSDAgg[3].symbol + " " + tokensOnXUSDAgg[3].amount+ " Delta: " + `${myTokens[3].amount - tokensOnXUSDAgg[3].amount}`);
    //Bridge-BSC USDC USDCbs
    logger.log('info', "Bridge-" + myTokens[4].bridge + " " + myTokens[4].symbol + " " + myTokens[4].amount + 
        " " + tokensOnXUSDAgg[4].symbol + " " + tokensOnXUSDAgg[4].amount+ " Delta: " + `${myTokens[4].amount - tokensOnXUSDAgg[4].amount}`);
    //Bridge-BSC USDT USDTbs
    logger.log('info', "Bridge-" + myTokens[5].bridge + " " + myTokens[5].symbol + " " + myTokens[5].amount + 
        " " + tokensOnXUSDAgg[5].symbol + " " + tokensOnXUSDAgg[5].amount+ " Delta: " + `${myTokens[5].amount - tokensOnXUSDAgg[5].amount}`);
    //Bridge-BSC BUSD BUSDbs
    logger.log('info', "Bridge-" + myTokens[6].bridge + " " + myTokens[6].symbol + " " + myTokens[6].amount + 
        " " + tokensOnXUSDAgg[6].symbol + " " + tokensOnXUSDAgg[6].amount+ " Delta: " + `${myTokens[6].amount - tokensOnXUSDAgg[6].amount}`);
};

scheduler.start().catch((err) => {
    logger.error('Unhandled Error on start()', err);
});

async function run() {
    try {
        await getBalances()   ;
        await getNativeBalances()   ;
        await getETHSAggBalances() ;
        await getBNBSAggBalances() ;
        await getXUSDAggBalances() ;
        await printLogs();
        collectMemoryStats();
    } catch(err) {
        logger.error('Unhandled Error on run()', err);
        process.exit();
    }

 
    function collectMemoryStats() {
        metrics.gauge('ETH.ETH', myNativeTokens[0].amount);
        metrics.gauge('ETH.ETHes', tokensOnETHsAgg[0].amount);
        metrics.gauge('ETH.DAI', myTokens[0].amount);
        metrics.gauge('ETH.DAIes', tokensOnXUSDAgg[0].amount);
        metrics.gauge('ETH.USDC', myTokens[1].amount);
        metrics.gauge('ETH.USDCes', tokensOnXUSDAgg[1].amount);
        metrics.gauge('ETH.USDT', myTokens[2].amount);
        metrics.gauge('ETH.USDTes', tokensOnXUSDAgg[2].amount);
        metrics.gauge('BSC.BNB', myNativeTokens[1].amount);
        metrics.gauge('BSC.BNBbs', tokensOnBNBsAgg[0].amount);
        metrics.gauge('BSC.ETH', myTokens[7].amount);
        metrics.gauge('BSC.ETHbs', tokensOnETHsAgg[1].amount);
        metrics.gauge('BSC.DAI', myTokens[3].amount);
        metrics.gauge('BSC.DAIes', tokensOnXUSDAgg[3].amount);
        metrics.gauge('BSC.USDC', myTokens[4].amount);
        metrics.gauge('BSC.USDCes', tokensOnXUSDAgg[4].amount);
        metrics.gauge('BSC.USDT', myTokens[5].amount);
        metrics.gauge('BSC.USDTes', tokensOnXUSDAgg[5].amount);
        metrics.gauge('BSC.BUSD', myTokens[6].amount);
        metrics.gauge('BSC.BUSDes', tokensOnXUSDAgg[6].amount);
    };
};
