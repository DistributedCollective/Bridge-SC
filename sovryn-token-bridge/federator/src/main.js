const log4js = require('log4js');
const web3 = require('web3');

const P2p = require('./lib/P2p.js');
const utils = require('./lib/utils');

// Configurations
const config = require('../config/config.js');
const logConfig = require('../config/log-config.json');
log4js.configure(logConfig);

// Services
const Scheduler = require('./services/Scheduler.js');

//GasPriceFetcher
const Federator = require('./lib/Federator.js');
const { TelegramBot, NullBot } = require('./lib/chatBots.js');
const ClientId = require('./lib/ClientId.js');
// const GasPriceFetcher = require('./lib/GasPriceFetcher.js');
// const GasPriceAvg = require('./lib/GasPriceAvg.js');
const GasServices = require('./lib/GasServices.js');

// Global GasPrice Variables
// let currentEthGasBasePrice;
// let currentEthGasPriceAvg;

const logger = log4js.getLogger('Federators');
logger.info('RSK Host', config.mainchain.host);
logger.info('ETH Host', config.sidechain.host);

this.logger = logger;

if (!config.mainchain || !config.sidechain) {
    logger.error('Mainchain and Sidechain configuration are required');
    process.exit();
}

let chatBot;
if (config.telegramBot && config.telegramBot.token && config.telegramBot.groupId) {
    chatBot = new TelegramBot(
        config.telegramBot.token,
        config.telegramBot.groupId,
        log4js.getLogger('CHATBOT'),
        config.federatorInstanceId
    );
} else {
    chatBot = new NullBot(log4js.getLogger('CHATBOT'));
}

const port = parseInt(process.argv[2]) || config.port;
const privateKey = process.argv[3] || config.privateKey;
const p2pNode = new P2p('bridge-federators', port, config.peers, privateKey, logger);

const clientId = new ClientId(log4js.getLogger('Get-Client-Id'), config, web3);

const gasServices = new GasServices(log4js.getLogger('ETH-GasServices'), config, web3);

// const gasPriceFetcher = new GasPriceFetcher(
//     log4js.getLogger('ETH-MAINNET-GasPriceFetcher'),
// );

// const gasPriceAvg = new GasPriceAvg(
//     log4js.getLogger('ETH-MAINNET-GasPriceFetAvg'),
// );

const mainFederator = new Federator(config, log4js.getLogger('MAIN-FEDERATOR'), web3, chatBot);

const sideFederator = new Federator(
    {
        ...config,
        mainchain: config.sidechain,
        sidechain: config.mainchain,
        storagePath: `${config.storagePath}/side-fed`,
    },
    log4js.getLogger('SIDE-FEDERATOR'),
    web3,
    chatBot
);

let pollingInterval = config.runEvery * 1000 * 60; // Minutes
// let gasApiPollingInterval = config.gasApiRunEvery * 1000 ; // Seconds
// let avgGasPollingInterval = config.avgGasRunEvery * 1000 ; // Seconds
// let avgGasPeriodInterval = config.periodAvgGas * 1000 * 60 ; // Minutes
// let avgGasCount;

let scheduler = new Scheduler(pollingInterval, logger, { run: () => run() });

startServices().catch((err) => {
    console.error('Error starting services:', err);
});

async function startServices() {
    // let isEth;
    // try {
    //     isEth = await clientId.isEthereumChain();
    //     console.log('isEth: ' + isEth);
    // } catch (err) {
    //     logger.error('Unhandled Error on isEthereumChain()', err);
    //     process.exit();
    // }

    // if (isEth){
    //     try {
    //         await gasServices.startGasServices();
    //     } catch(err) {
    //         logger.error('Cannnot start ETH gas services()', err);
    //         process.exit();
    //     }
    // };

    try {
        await p2pNode.start();
    } catch (err) {
        logger.error("Couldn't start P2P network", err);
        process.exit();
    }

    scheduler.start().catch((err) => {
        logger.error('Unhandled Error on start()', err);
    });
}

async function run() {
    if (p2pNode.getPeerAmount() < config.minimumPeerAmount) {
        logger.info('Waiting for enough peers');
        return;
    }

    if (p2pNode.isLeader()) {
        try {
            console.log('Scheduler work');
            // console.log('before mainfed');
            // await mainFederator.run();
            // console.log('before sidefed');
            // await sideFederator.run();
        } catch (err) {
            logger.error('Unhandled Error on run()', err);
            process.exit();
        }
    }
}

async function exitHandler() {
    try {
        await p2pNode.stop();
    } catch (err) {
        throw new Error(err);
    }
    process.exit();
}

// catches ctrl+c event
process.on('SIGINT', exitHandler);

// catches "kill pid" (for example: nodemon restart)
process.on('SIGUSR1', exitHandler);
process.on('SIGUSR2', exitHandler);

// export so we can test it
module.exports = { scheduler };
