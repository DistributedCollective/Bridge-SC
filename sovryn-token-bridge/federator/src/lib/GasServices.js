const web3 = require('web3');
const config = require('../../config/config.js');
const utils = require('./utils');
var globals = require('./Globals');

// Services
const Scheduler = require('../services/Scheduler.js');
const log4js = require('log4js');
const GasPriceFetcher = require('../lib/GasPriceFetcher.js');
const GasPriceAvg = require('../lib/GasPriceAvg.js');

let gasApiPollingInterval = config.gasApiRunEvery * 1000 ; // Seconds
let avgGasPollingInterval = config.avgGasRunEvery * 1000 ; // Seconds
let avgGasPeriodInterval = config.periodAvgGas * 1000 * 60 ; // Minutes
let avgGasCount;

// let currentEthGasBasePrice = globals.currentEthGasBasePrice;
// let currentEthGasPriceAvg = globals.currentEthGasPriceAvg;

let etherscanApiBaseUrl = config.sidechain.host.includes('rinkeby') ? 'https://api-rinkeby.etherscan.io/api' : 'https://api.etherscan.io/api';
console.log("etherscanApiBaseUrl: " + etherscanApiBaseUrl);
//For Mainnet:
// const etherScanApiBaseUrl = 'https://api.etherscan.io/api';            
//For RinkebyTestnet:
//const etherScanApiBaseUrl = 'https://api-rinkeby.etherscan.io/api';



module.exports = class GasServices {
    constructor(logger, config, Web3 = web3) {
        this.logger = logger;
        this.config = config;
        
        // this.gasPriceEstimator = new GasPriceEstimator({
        //     web3: this.client,
        //     logger: this.logger,
        //     etherscanApiKey: config.etherscanApiKey,
        // });


        this.gasPriceFetcher = new GasPriceFetcher(
            log4js.getLogger('ETH-MAINNET-GasPriceFetcher'),
            config.etherscanApiKey,
            etherScanApiBaseUrl
        );
        
        this.gasPriceAvg = new GasPriceAvg(
            log4js.getLogger('ETH-MAINNET-GasPriceFetAvg'),
        );
    }
    
    async startGasServices() {
        let etherScanGasPriceService = new Scheduler(gasApiPollingInterval, this.logger, { run: () => this.runGasPriceService() });
        let gasPriceAvgService = new Scheduler(avgGasPollingInterval, this.logger, { run: () => this.runGasPriceAvg() });
        
        if(avgGasPollingInterval > 0) {
            avgGasCount = avgGasPeriodInterval/avgGasPollingInterval;
        }
        else {
            this.logger.error('config.avgGasPollingInterval cannot be 0', err);
            process.exit();
        };

        etherScanGasPriceService.start().catch((err) => {
            this.logger.error('Unhandled Error on etherScanGasPriceService start()', err);
        });

        await utils.sleep(2 * gasApiPollingInterval, { logger: this.logger });

        gasPriceAvgService.start().catch((err) => {
            this.logger.error('Unhandled Error on gasPriceAvg start()', err);
        });  

        this.logger.info(`Process is waiting to calculate average gas of ${avgGasPeriodInterval} ms.`);
        this.logger.debug('Process is waiting to calculate average gas of ' ,avgGasPeriodInterval);
        await utils.sleep(avgGasPeriodInterval, { logger: this.logger });
    }

    async runGasPriceService() {
        
        try {
            globals.currentEthGasBasePrice = await this.gasPriceFetcher.getEtherscanBaseGasPrice();
            this.logger.debug('currentEthGasBasePrice: ' ,globals.currentEthGasBasePrice);
        } catch(err) {
            this.logger.error('Unhandled Error on runGasPriceService()', err);
        // process.exit();
        }
    }
    
    async runGasPriceAvg() {
        
        try {
            globals.currentEthGasPriceAvg = await this.gasPriceAvg.calcAvg(avgGasCount, globals.currentEthGasBasePrice);
            this.logger.debug('currentEthGasPriceAvg: ' ,globals.currentEthGasPriceAvg);
        } catch(err) {
            logger.error('Unhandled Error on runGasWatcher()', err);
        // process.exit();
        }
    }
    
}