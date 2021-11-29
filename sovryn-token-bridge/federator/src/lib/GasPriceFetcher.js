const http = require('http');
const https = require('https');

module.exports = class GasPriceFetcher {
    constructor(logger)
        {
            this.logger = logger;
            etherscanApiKey = undefined;
            etherscanApiBaseUrl = 'https://api.etherscan.io/api';
            this.etherscanApiKey = etherscanApiKey;
            this.etherscanApiBaseUrl = etherscanApiBaseUrl;
        }        

    async getEtherscanBaseGasPrice() {
        let url = `${this.etherscanApiBaseUrl}?module=gastracker&action=gasoracle`;
        console.log(url);
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
            //lastblock: parseInt(result.LastBlock),
            safeGasPrice: parseInt(result.SafeGasPrice) * gwei,
            // proposeGasPrice: parseInt(result.ProposeGasPrice) * gwei,
            // fastGasPrice: parseInt(result.FastGasPrice) * gwei,
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