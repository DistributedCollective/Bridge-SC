const http = require('http');
const https = require('https');
const CustomError = require('./CustomError');

module.exports = class GasPriceFetcher {
    constructor(
        logger,
        etherscanApiKey,
        etherscanApiBaseUrl = 'https://api.etherscan.io/v2/api'
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
        if (
            typeof this.etherscanApiKey !== 'string' ||
            !this.etherscanApiKey.trim() ||
            this.etherscanApiKey.length > 1024
        ) {
            throw new CustomError('Etherscan V2 read API key is unavailable');
        }
        if (/^(?:0x)?[0-9a-f]{64}$/i.test(this.etherscanApiKey.trim())) {
            throw new CustomError(
                'Etherscan read credential resembles a signing scalar; request refused'
            );
        }
        let url;
        try {
            url = new URL(this.etherscanApiBaseUrl);
            if (url.hostname === 'api.etherscan.io') url.pathname = '/v2/api';
            if (url.protocol !== 'https:' && url.protocol !== 'http:') throw new Error('scheme');
            url.searchParams.set('chainid', '1');
            url.searchParams.set('module', 'gastracker');
            url.searchParams.set('action', 'gasoracle');
            url.searchParams.set('apikey', this.etherscanApiKey.trim());
        } catch (err) {
            throw new CustomError('Etherscan endpoint configuration is invalid');
        }
        let response;
        try {
            response = await this._makeRequest(url.toString());
        } catch (err) {
            // Provider errors can embed URLs/API keys. Do not attach them to logged errors.
            throw new CustomError('Etherscan gas quote unavailable; bounded read failed');
        }
        const value = response && response.result && response.result.SafeGasPrice;
        if (
            !response ||
            response.status !== '1' ||
            typeof value !== 'string' ||
            !/^\d+(?:\.\d+)?$/.test(value) ||
            !Number.isFinite(Number(value)) ||
            Number(value) <= 0
        ) {
            throw new CustomError('Etherscan returned an invalid positive decimal gas quote');
        }
        return value;
    }

    async _makeRequest(url) {
        const httpModule = url.startsWith('https:') ? https : http;
        return new Promise((resolve, reject) => {
            let request;
            let response;
            let finished = false;
            const finish = (error, value) => {
                if (finished) return;
                finished = true;
                clearTimeout(timer);
                if (error) reject(new Error('Bounded gas oracle request failed'));
                else resolve(value);
            };
            const timer = setTimeout(() => {
                finish(true);
                if (response) response.destroy();
                if (request) request.destroy();
            }, 5000);
            try {
                request = httpModule.get(url, (res) => {
                    response = res;
                    if (res.statusCode !== 200) {
                        finish(true);
                        res.destroy();
                        if (request) request.destroy();
                        return;
                    }
                    res.setEncoding('utf8');
                    let rawData = '';
                    let size = 0;
                    res.on('data', (chunk) => {
                        if (finished) return;
                        size += Buffer.byteLength(chunk);
                        if (size > 128 * 1024) {
                            finish(true);
                            res.destroy();
                            if (request) request.destroy();
                            return;
                        }
                        rawData += chunk;
                    });
                    res.on('error', () => finish(true));
                    res.on('end', () => {
                        if (finished) return;
                        try {
                            finish(false, JSON.parse(rawData));
                        } catch (err) {
                            finish(true);
                        }
                    });
                });
                request.on('error', () => finish(true));
            } catch (err) {
                finish(true);
                if (response) response.destroy();
                if (request) request.destroy();
            }
        });
    }
};
