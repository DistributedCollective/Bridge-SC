const http = require('http');
const https = require('https');

const CustomError = require('./CustomError');

module.exports = class EtherscanGasPriceEstimator {
    constructor({
        apiKey = undefined,
        logger = console,
        cacheTimeMs = undefined,
        apiBaseUrl = 'https://api.etherscan.io/api',
        chainId = 1,
    }) {
        this.apiKey = apiKey;
        this.logger = logger;
        this.apiBaseUrl = apiBaseUrl;
        this.chainId = chainId;

        // Etherscan free plan allows 5 calls per second
        // However if no api key is given, the max allowed rate is 1 call / 5s
        if (cacheTimeMs !== undefined && cacheTimeMs !== null) {
            this.cacheTimeMs = cacheTimeMs;
        } else if (apiKey) {
            this.cacheTimeMs = 1000 / 5;
        } else {
            this.cacheTimeMs = 5000;
        }

        this.cachedGasPrice = null;
        this.cachedTimestamp = 0;
    }

    isEnabledForChain(chainId) {
        return chainId === this.chainId;
    }

    async getGasPrice() {
        if (this.cachedGasPrice && Date.now() <= (this.cachedTimestamp + this.cacheTimeMs)) {
            this.logger.debug(`Using cached gas price ${this.cachedTimestamp} with timestamp ${this.cachedTimestamp}`);
            return this.cachedGasPrice;
        }

        this.logger.debug('Fetching gas price from Etherscan');
        const gasPrice = await this.getGasPriceWithoutCaching();
        this.cachedGasPrice = gasPrice;
        this.cachedTimestamp = Date.now();
        return gasPrice;
    }

    async getGasPriceWithoutCaching() {
        let url = `${this.apiBaseUrl}?module=gastracker&action=gasoracle`;
        if (this.apiKey) {
            url += `&apikey=${this.apiKey}`;
        }
        let response;
        try {
            response = await this._makeRequest(url);
        } catch (e) {
            throw new CustomError(`Error getting gas price from ethesrcan: ${e.toString()}`, e);
        }
        this.logger.debug('gas price response from etherscan:', response);
        if (response.status !== '1') {
            throw new CustomError('Invalid status for response:' + JSON.stringify(response));
        }
        const result = response.result || {};
        const gasPriceGweiStr = result.ProposeGasPrice;
        if (!gasPriceGweiStr) {
            throw new CustomError('cannot find gas price:' + JSON.stringify(response));
        }

        return parseInt(gasPriceGweiStr) * 1000000000;
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