const log4js = require('log4js');
const web3 = require('web3');
const utils = require('./utils');

// Configurations
const config = require('../config/config.js');
const logConfig = require('../config/log-config.json');
log4js.configure(logConfig);

// Services
const Scheduler = require('./services/Scheduler.js');

//GasPriceFetcher
const Federator = require('./lib/Federator.js');
const {TelegramBot, NullBot} = require('./lib/chatBots.js');
const ClientId = require('./lib/ClientId.js');
const GasPriceFetcher = require('./lib/GasPriceFetcher.js');
const GasPriceAvg = require('./lib/GasPriceAvg.js');

// Global GasPrice Variables
let currentEthGasBasePrice;
let currentEthGasPriceAvg;

const logger = log4js.getLogger('Federators');
logger.info('RSK Host', config.mainchain.host);
logger.info('ETH Host', config.sidechain.host);

if(!config.mainchain || !config.sidechain) {
    logger.error('Mainchain and Sidechain configuration are required');
    process.exit();
}

let chatBot;
if(config.telegramBot && config.telegramBot.token && config.telegramBot.groupId) {
    chatBot = new TelegramBot(
        config.telegramBot.token,
        config.telegramBot.groupId,
        log4js.getLogger('CHATBOT'),
        config.federatorInstanceId,
    );
} else {
    chatBot = new NullBot(
        log4js.getLogger('CHATBOT')
    );
}

const clientId = new ClientId(
    log4js.getLogger('Get-Client-Id'),
    config,
    web3,
);

const gasPriceFetcher = new GasPriceFetcher(
    log4js.getLogger('ETH-MAINNET-GasPriceFetcher'),
);

const gasPriceAvg = new GasPriceAvg(
    log4js.getLogger('ETH-MAINNET-GasPriceFetAvg'),
);

const mainFederator = new Federator(
    config,
    log4js.getLogger('MAIN-FEDERATOR'),
    web3,
    chatBot,
);

const sideFederator = new Federator(
    {
        ...config,
        mainchain: config.sidechain,
        sidechain: config.mainchain,
        storagePath: `${config.storagePath}/side-fed`
    },
    log4js.getLogger('SIDE-FEDERATOR'),
    web3,
    chatBot,
);

let pollingInterval = config.runEvery * 1000 * 60; // Minutes
let gasApiPollingInterval = config.gasApiRunEvery * 1000 ; // Seconds
let avgGasPollingInterval = config.avgGasRunEvery * 1000 ; // Seconds
let avgGasPeriodInterval = config.periodAvgGas * 1000 * 60 ; // Minutes
let avgGasCount;

let scheduler = new Scheduler(pollingInterval, logger, { run: () => run() });

startServices();

async function startServices() {
    try {
        isEth = await clientId._getChainId();
    } catch(err) {
        logger.error('Unhandled Error on _getChainId()', err);
        process.exit();
    }
    if (isEth){
        let etherScanGasPriceService = new Scheduler(gasApiPollingInterval, logger, { run: () => runGasPriceService() });
        let gasPriceAvgService = new Scheduler(avgGasPollingInterval, logger, { run: () => runGasPriceAvg() });
        
        if(avgGasPollingInterval > 0) {
            avgGasCount = avgGasPeriodInterval/avgGasPollingInterval;
        }
        else {
            logger.error('config.avgGasPollingInterval cannot be 0', err);
            process.exit();
        };

        etherScanGasPriceService.start().catch((err) => {
            logger.error('Unhandled Error on etherScanGasPriceService start()', err);
        });
        
        gasPriceAvgService.start().catch((err) => {
            logger.error('Unhandled Error on gasPriceAvg start()', err);
        });  

        this.logger.debug(`Process is waiting to calculate average gas of ${avgGasPeriodInterval} ms.`);
        await utils.sleep(avgGasPeriodInterval, { logger: this.logger });
    }   
    scheduler.start().catch((err) => {
        logger.error('Unhandled Error on start()', err);
    });
}

async function runGasPriceService() {
    try {
        currentEthGasBasePrice = await gasPriceFetcher.getEtherscanBaseGasPrice();
    } catch(err) {
        logger.error('Unhandled Error on runGasPriceService()', err);
        process.exit();
    }
}

async function runGasPriceAvg() {
    try {
        currentEthGasPriceAvg = await gasPriceAvg.calcAvg(avgGasCount, currentEthGasBasePrice);
    } catch(err) {
        logger.error('Unhandled Error on runGasWatcher()', err);
        process.exit();
    }
}

async function run() {
    try {
        await mainFederator.run();
        await sideFederator.run();
    } catch(err) {
        logger.error('Unhandled Error on run()', err);
        process.exit();
    }
}

async function exitHandler() {
    process.exit();
}

// catches ctrl+c event
process.on('SIGINT', exitHandler);

// catches "kill pid" (for example: nodemon restart)
process.on('SIGUSR1', exitHandler);
process.on('SIGUSR2', exitHandler);

// export so we can test it
module.exports = { scheduler };
