var globals = require('./globals');
const { MAINNET_ID, RINKEBY_ID, ROPSTEN_ID } = require('./constants');

const Tx = require('ethereumjs-tx');

const ethUtils = require('ethereumjs-util');
const utils = require('./utils');
const CustomError = require('./CustomError');
const GasPriceEstimator = require('./GasPriceEstimator');
const fs = require('fs');
const ethereumJsTx = require('@ethereumjs/tx');
const Common = require('@ethereumjs/common').default;

module.exports = class TransactionSender {
    constructor(client, logger, config, chainId) {
        this.client = client;
        this.logger = logger;
        this.chainId = chainId;
        this.config = config;
        this.manuallyCheck = `${config.storagePath || __dirname}/manuallyCheck.txt`;
        this.ethGasPriceThresholdGwei = config.ethGasPriceThresholdGwei ?? 10;

        this.gasPriceEstimator = new GasPriceEstimator({
            web3: this.client,
            logger: this.logger,
            etherscanApiKey: config.etherscanApiKey,
        });
    }

    async getNonce(address) {
        return await this.client.eth.getTransactionCount(address, 'pending');
    }

    numberToHexString(number) {
        if (!number) {
            return '0x0';
        }
        return `0x${Math.ceil(parseInt(number)).toString(16)}`;
    }

    async getGasPrice(chainId) {
        return this.gasPriceEstimator.getGasPrice(chainId);
    }

    async getGasLimit(rawTx) {
        const estimatedGas = await this.client.eth.estimateGas({
            value: rawTx.value,
            to: rawTx.to,
            data: rawTx.data,
            from: rawTx.from,
        });

        // Vote: ~70k
        // Vote+execute: A little over 250k
        // Vote+execute with signatures: Can get to over 300k, 500k+ with aggregators involved
        // First side token deployment: ~3.15M
        const multiplier = 1.5;
        const minimum = 400000;
        let gasLimit = Math.ceil(estimatedGas * multiplier);
        if (gasLimit < minimum) {
            gasLimit = minimum;
        }

        return gasLimit;
    }

    async getChainId() {
        const chainId = this.chainId || (await this.client.eth.net.getId());
        return chainId;
    }

    getChainName(chainId) {
        switch (chainId) {
            case MAINNET_ID:
                return 'mainnet';
            case RINKEBY_ID:
                return 'rinkeby';
            case ROPSTEN_ID:
                return 'ropsten';
            default:
                throw new Error('Unknown chain id');
        }
    }

    async createRawTransaction(from, to, data, value) {
        const nonce = await this.getNonce(from);
        const chainId = await this.getChainId();

        const chainIdInt = parseInt(chainId);

        if (chainIdInt === MAINNET_ID || chainIdInt === RINKEBY_ID || chainIdInt === ROPSTEN_ID) {
            const rawTxETH = await this.createETHRawTransaction(from, to, data, value, chainId);

            const chainName = this.getChainName(chainIdInt);

            const common = new Common({ chain: chainName, hardfork: 'london' });
            const tx = ethereumJsTx.FeeMarketEIP1559Transaction.fromTxData(rawTxETH, { common });
            return tx;
        } else {
            const gasPrice = await this.getGasPrice(chainId);
            let rawTx = {
                gasPrice: this.numberToHexString(gasPrice),
                value: this.numberToHexString(value),
                to: to,
                data: data,
                from: from,
                nonce: this.numberToHexString(nonce),
                r: 0,
                s: 0,
            };
            rawTx.gas = this.numberToHexString(await this.getGasLimit(rawTx));
            const rawTxType = new Tx(rawTx);
            return rawTxType;
        }
    }

    async createETHRawTransaction(from, to, data, value, chainId) {
        const nonce = await this.getNonce(from);
        const priorityFeeWei = 2000000000n;
        const sleepOnGas =
            Number.isFinite(this.config.sleepOnGas) && this.config.sleepOnGas >= 0
                ? this.config.sleepOnGas * 1000
                : 10000;
        const maxSleepOnGas =
            Number.isInteger(this.config.maxSleepOnGas) && this.config.maxSleepOnGas >= 0
                ? Math.min(this.config.maxSleepOnGas, 60)
                : 9;
        let sleepOnGasCounter = 0;
        let baseFee = await this.getLatestEthBaseFee();
        while (
            Number(baseFee) / 1e9 > this.ethGasPriceThresholdGwei &&
            (!Number.isFinite(Number(globals.currentEthGasPriceAvg)) ||
                Number(globals.currentEthGasPriceAvg) <= 0 ||
                Number(baseFee) / 1e9 > Number(globals.currentEthGasPriceAvg))
        ) {
            if (sleepOnGasCounter++ >= maxSleepOnGas) {
                throw new CustomError('High live ETH base fee: transaction was not constructed');
            }
            await utils.sleep(sleepOnGas, { logger: this.logger });
            baseFee = await this.getLatestEthBaseFee();
        }
        // Exact integer Wei arithmetic preserves fractional Gwei and rounds the buffer upward.
        const maxFee = ((baseFee + priorityFeeWei) * 13n + 9n) / 10n;

        const rawTx = {
            maxFeePerGas: '0x' + maxFee.toString(16),
            maxPriorityFeePerGas: '0x' + priorityFeeWei.toString(16),
            value: this.numberToHexString(value),
            to: to,
            data: data,
            from: from,
            nonce: this.numberToHexString(nonce),
            chainId: this.numberToHexString(parseInt(chainId)),
            accessList: [],
            type: '0x02',
            r: 0,
            s: 0,
        };
        rawTx.gasLimit = this.numberToHexString(await this.getGasLimit(rawTx));
        this.logger.info('raw tx is:', { rawTx });

        return rawTx;
    }

    async getLatestEthBaseFee() {
        let timer;
        try {
            const block = await Promise.race([
                this.client.eth.getBlock('latest'),
                new Promise((_, reject) => {
                    timer = setTimeout(() => reject(new Error('timeout')), 5000);
                }),
            ]);
            const value = block && block.baseFeePerGas;
            if (
                (typeof value !== 'string' && !Number.isSafeInteger(value)) ||
                !/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(String(value))
            ) {
                throw new Error('invalid base fee');
            }
            const fee = BigInt(value);
            const age = Date.now() / 1000 - Number(block.timestamp);
            if (fee <= 0n || fee >= 1n << 256n || !Number.isFinite(age) || age < -30 || age > 120) {
                throw new Error('invalid or stale block');
            }
            return fee;
        } catch (err) {
            throw new CustomError(
                'Fresh ETH block base fee unavailable; transaction not constructed'
            );
        } finally {
            clearTimeout(timer);
        }
    }

    signRawTransaction(rawTx, privateKey) {
        rawTx.sign(utils.hexStringToBuffer(privateKey));

        return rawTx;
    }

    signETHRawTransaction(rawTx, privateKey) {
        const signedTx = rawTx.sign(utils.hexStringToBuffer(privateKey));

        return signedTx;
    }

    async getAddress(privateKey) {
        let address = null;
        if (privateKey && privateKey.length) {
            address = utils.privateToAddress(privateKey);
        } else {
            //If no private key provided we use personal (personal is only for testing)
            let accounts = await this.client.eth.getAccounts();
            address = accounts[0];
        }
        return address;
    }

    async sendTransaction(to, data, value, privateKey) {
        const stack = new Error().stack;
        const chainId = await this.getChainId();

        var from = await this.getAddress(privateKey);
        if (!from) {
            throw new CustomError(
                `No from address given. Is there an issue with the private key? ${stack}`
            );
        }
        let rawTx = await this.createRawTransaction(from, to, data, value, privateKey);
        let txHash;
        let error = '';
        let errorInfo = '';

        try {
            let receipt;
            let signedTx;

            if (privateKey && privateKey.length) {
                if (
                    parseInt(chainId) === parseInt(MAINNET_ID) ||
                    parseInt(chainId) === parseInt(RINKEBY_ID) ||
                    parseInt(chainId) === parseInt(ROPSTEN_ID)
                ) {
                    signedTx = this.signETHRawTransaction(rawTx, privateKey);
                } else {
                    signedTx = this.signRawTransaction(rawTx, privateKey);
                }
                const serializedTx = ethUtils.bufferToHex(signedTx.serialize());
                receipt = await this.client.eth
                    .sendSignedTransaction(serializedTx)
                    .once('transactionHash', (hash) => (txHash = hash));
            } else {
                //If no private key provided we use personal (personal is only for testing)
                delete rawTx.r;
                delete rawTx.s;
                delete rawTx.v;
                receipt = await this.client.eth
                    .sendTransaction(rawTx)
                    .once('transactionHash', (hash) => (txHash = hash));
            }
            if (receipt.status == 1) {
                this.logger.info(
                    `Transaction Successful txHash:${receipt.transactionHash} blockNumber:${receipt.blockNumber}`
                );
                return receipt;
            }
            error = 'Transaction Receipt Status Failed';
            errorInfo = receipt;
        } catch (err) {
            if (err.message.indexOf('it might still be mined') > 0) {
                this.logger
                    .warn(`Transaction was not mined within 750 seconds, please make sure your transaction was properly sent. Be aware that
                    it might still be mined. transactionHash:${txHash}`);
                fs.appendFileSync(
                    this.manuallyCheck,
                    `transactionHash:${txHash} to:${to} data:${data}\n`
                );
                return { transactionHash: txHash };
            }
            error = `Send Signed Transaction Failed TxHash:${txHash}`;
            errorInfo = err;
        }
        this.logger.error(error, errorInfo);
        this.logger.error('RawTx that failed', rawTx);
        throw new CustomError(`Transaction Failed: ${error} ${stack}`, errorInfo);
    }
};
