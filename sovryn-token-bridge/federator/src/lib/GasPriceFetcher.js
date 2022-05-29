const http = require('http');
const https = require('https');
const CustomError = require('./CustomError');

module.exports = class GasPriceFetcher {
    constructor(
        logger,
        etherscanApiKey,
        etherscanApiBaseUrl //= 'https://api.etherscan.io/api',
        )
        {
            this.logger = logger;
            this.etherscanApiKey = etherscanApiKey;
            this.etherscanApiBaseUrl = etherscanApiBaseUrl;
            //For Mainnet:
            // const etherscanApiBaseUrl = 'https://api.etherscan.io/api';
            
            //For RinkebyTestnet:
            //const etherscanApiBaseUrl = 'https://api-rinkeby.etherscan.io/api';
            
            //For Unit Testing only:
            //const etherscanApiBaseUrl = 'https://example.invalid/api';
            
            //wss://rinkeby.infura.io/ws/v3/
            // this.etherscanApiKey = etherscanApiKey;
        }        

    async getEtherscanBaseGasPrice() {
        let url = `${this.etherscanApiBaseUrl}?module=gastracker&action=gasoracle`;
        // if (this.etherscanApiKey) {
        //     url += `&apikey=${this.etherscanApiKey}`;
        // }
        let response;
        try {
            response = await this._makeRequest(url);
        } catch (e) {
            throw new CustomError(`Error getting gas prices from ethesrcan: ${e.toString()}`, e);
        }
        // this.logger.debug('gas price response from etherscan:', response);
        if (response.status !== '1') {
            throw new CustomError('Invalid status for response:' + JSON.stringify(response));
        }
        const result = response.result || {};
        //this.logger.debug("result.SafeGasPrice: " ,result.SafeGasPrice);

        return result.SafeGasPrice;
        // return {
        //     //lastblock: parseInt(result.LastBlock),
        //     // safeGasPrice: parseInt(result.SafeGasPrice) * gwei,
        //     // proposeGasPrice: parseInt(result.ProposeGasPrice) * gwei,
        //     // fastGasPrice: parseInt(result.FastGasPrice) * gwei,
        // }
    }

    async _makeRequest(url) {
        const httpModule = url.startsWith('https:') ? https : http;
        return new Promise((resolve, reject) => {
            httpModule.get(url, (res) => {
                if (res.statusCode !== 200) {
                    res.resume(); // consume response to free memory
                    //return reject(new Error(`invalid status code: ${res.statusCode}`))
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