const http = require('http');
const https = require('https');

const CustomError = require('./CustomError');

module.exports = class GasPriceEstimator {
    constructor({
        web3,
        etherscanApiKey = undefined,
        logger = console,
        cacheTimeMs = undefined,
        etherscanApiBaseUrl = 'https://api.etherscan.io/api',
        etherscanChainId = 1,
    }) {
        if (!web3) {
            throw new CustomError('web3 is required');
        }
        this.web3 = web3;
        this.etherscanApiKey = etherscanApiKey;
        this.logger = logger;
        this.etherscanApiBaseUrl = etherscanApiBaseUrl;
        this.etherscanChainId = etherscanChainId;

        // Etherscan free plan allows 5 calls per second
        // However if no api key is given, the max allowed rate is 1 call / 5s
        if (cacheTimeMs !== undefined && cacheTimeMs !== null) {
            this.cacheTimeMs = cacheTimeMs;
        } else if (this.etherscanApiKey) {
            this.cacheTimeMs = 1000 / 5;
        } else {
            this.cacheTimeMs = 5000;
        }

        this.cachedEtherscanGasPrices = null;
        this.cachedEtherscanGasPriceTimestamp = 0;
    }

    async getGasPrice(chainId) {
        chainId = parseInt(chainId);
        if(chainId>= 30 && chainId <=33) {
            return await this.getRskGasPrice();
        }

        const web3GasPrice = parseInt(await this.web3.eth.getGasPrice());
        const fallbackGasPrice = web3GasPrice <= 1 ? 1: Math.round(web3GasPrice * 1.5);
        if (chainId !== this.etherscanChainId) {
            return fallbackGasPrice;
        }
        try {
            const { proposeGasPrice, fastGasPrice } = await this.getEtherscanGasPrices();
            if (web3GasPrice > proposeGasPrice) {
                return Math.round((web3GasPrice + proposeGasPrice) / 2);
            } else {
                return Math.max(proposeGasPrice * 1.25, fastGasPrice);
            }
        } catch (e) {
            this.logger.warn('error getting etherscan gas price, falling back to web3 gas price (with multiplier)');
            return fallbackGasPrice;
        }
    }

    async getRskGasPrice() {
        const block = await this.web3.eth.getBlock('latest');
        const gasPrice = parseInt(block.minimumGasPrice);
        return gasPrice <= 1 ? 1: Math.round(gasPrice * 1.05);
    }

    async getEtherscanGasPrices() {
        if (this.cachedEtherscanGasPrices && Date.now() <= (this.cachedEtherscanGasPriceTimestamp + this.cacheTimeMs)) {
            this.logger.debug(`Using cached gas price ${this.cachedEtherscanGasPriceTimestamp} with timestamp ${this.cachedEtherscanGasPriceTimestamp}`);
            return this.cachedEtherscanGasPrices;
        }

        this.logger.debug('Fetching gas prices from Etherscan');
        const gasPrices = await this.getEtherscanGasPricesWithoutCaching();
        this.cachedEtherscanGasPrices = gasPrices;
        this.cachedEtherscanGasPriceTimestamp = Date.now();
        return gasPrices;
    }

    async getEtherscanGasPricesWithoutCaching() {
        let url = `${this.etherscanApiBaseUrl}?module=gastracker&action=gasoracle`;
        if (this.etherscanApiKey) {
            url += `&apikey=${this.etherscanApiKey}`;
        }
        let response;
        try {
            response = await this._makeRequest(url);
        } catch (e) {
            throw new CustomError(`Error getting gas prices from ethesrcan: ${e.toString()}`, e);
        }
        this.logger.debug('gas price response from etherscan:', response);
        if (response.status !== '1') {
            throw new CustomError('Invalid status for response:' + JSON.stringify(response));
        }
        const result = response.result || {};
        const gwei = 1000000000;
        return {
            safeGasPrice: parseInt(result.SafeGasPrice) * gwei,
            proposeGasPrice: parseInt(result.ProposeGasPrice) * gwei,
            fastGasPrice: parseInt(result.FastGasPrice) * gwei,
        }
    }

    async _makeRequest(url) {
        const httpModule = url.startsWith('https:') ? https : http;
        return new Promise((resolve, reject) => {
            httpModule.get(url, (res) => {
                if (res.statusCode !== 200) {
                    res.resume(); // consume response to free memory
                    return reject(new Error(`invalid status code: ${res.statusCode}`))
                }

                res.setEncoding('utf8');
                let rawData = '';
                res.on('data', (chunk) => {
                    rawData += chunk;
                });
                res.on('end', () => {
                    try {
                        const jsonData = JSON.parse(rawData);
                        resolve(jsonData);
                    } catch (e) {
                        reject(e);
                    }
                });
            }).on('error', e => {
                reject(e);
            })
        })
    }
};