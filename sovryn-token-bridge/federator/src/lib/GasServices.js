const web3 = require('web3');
const config = require('../config/config.js');
// Services
const Scheduler = require('./services/Scheduler.js');
const log4js = require('log4js');
const GasPriceFetcher = require('./lib/GasPriceFetcher.js');
const GasPriceAvg = require('./lib/GasPriceAvg.js');

let gasApiPollingInterval = config.gasApiRunEvery * 1000 ; // Seconds
let avgGasPollingInterval = config.avgGasRunEvery * 1000 ; // Seconds
let avgGasPeriodInterval = config.periodAvgGas * 1000 * 60 ; // Minutes
let avgGasCount;

let currentEthGasBasePrice;
let currentEthGasPriceAvg;



module.exports = class GasServices {
    constructor(logger, config, Web3 = web3) {
        this.logger = logger;
        this.config = config;
        
        this.gasPriceFetcher = new GasPriceFetcher(
            log4js.getLogger('ETH-MAINNET-GasPriceFetcher'),
        );
        
        this.gasPriceAvg = new GasPriceAvg(
            log4js.getLogger('ETH-MAINNET-GasPriceFetAvg'),
        );
    }
    
    async startGasServices() {
        let etherScanGasPriceService = new Scheduler(gasApiPollingInterval, logger, { run: () => this.runGasPriceService() });
        let gasPriceAvgService = new Scheduler(avgGasPollingInterval, logger, { run: () => this.runGasPriceAvg() });
        
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

    async runGasPriceService() {
        
        try {
            currentEthGasBasePrice = await this.gasPriceFetcher.getEtherscanBaseGasPrice();
        } catch(err) {
            logger.error('Unhandled Error on runGasPriceService()', err);
            process.exit();
        }
    }
    
    async runGasPriceAvg() {
        
        try {
            currentEthGasPriceAvg = await this.gasPriceAvg.calcAvg(avgGasCount, currentEthGasBasePrice);
        } catch(err) {
            logger.error('Unhandled Error on runGasWatcher()', err);
            process.exit();
        }
    }
    
}