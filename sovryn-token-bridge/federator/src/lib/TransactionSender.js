
var globals = require('./Globals');
var constants = require('./Constants');

console.log(constants.ETHERSCAN_CHAIN_ID); 

const Tx = require('ethereumjs-tx');
const ethUtils = require('ethereumjs-util');
const utils = require('./utils');
const CustomError = require('./CustomError');
const GasPriceEstimator = require('./GasPriceEstimator');
const fs = require('fs');
const { FeeMarketEIP1559Transaction } = require( '@ethereumjs/tx' );
const Common = require( '@ethereumjs/common' ).default;

module.exports = class TransactionSender {

    constructor(client, logger, config) {

        this.client = client;
        this.logger = logger;
        this.chainId = null;
        this.manuallyCheck = `${config.storagePath || __dirname}/manuallyCheck.txt`;

        this.gasPriceEstimator = new GasPriceEstimator({
            web3: this.client,
            logger: this.logger,
            etherscanApiKey: config.etherscanApiKey,
        });
    }

    async getNonce(address) {
        return this.client.eth.getTransactionCount(address, "pending");
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
        //let estimatedGas = await this.client.eth.estimateGas({ gasPrice: rawTx.gasPrice, value: rawTx.value, to: rawTx.to, data: rawTx.data, from: rawTx.from});
        let estimatedGas = await this.client.eth.estimateGas({ value: rawTx.value, to: rawTx.to, data: rawTx.data, from: rawTx.from});

        // Vote: ~70k
        // Vote+execute: A little over 250k
        // First side token deployment: ~3.15M
        const minimum = 300000;
        estimatedGas = (estimatedGas < minimum) ? minimum : 3500000;

        return estimatedGas;
    }

    async createRawTransaction(from, to, data, value) {
        const nonce = await this.getNonce(from);
        console.log("----------nonce:   " + nonce);
        const chainId =  this.chainId || await this.client.eth.net.getId();

        console.log("chainId: " +chainId);

        // if(chainId === constants.ETHERSCAN_CHAIN_ID && nonce === 4) {
        //     const gasPriceDEBUG = 600 * 1000000000;
        //     let rawTx = {
        //         gasPrice: gasPriceDEBUG,
        //         value: this.numberToHexString(value),
        //         to: to,
        //         data: data,
        //         from: from,
        //         nonce: this.numberToHexString(nonce),
        //         r: 0,
        //         s: 0
        //     }
        //     rawTx.gas = this.numberToHexString(await this.getGasLimit(rawTx));
        //     return rawTx;
        // }
        // else
        if (chainId === constants.ETHERSCAN_CHAIN_ID ) {
            const rawTxETH = await this.createETHRawTransaction(from, to, data, value, chainId);
            let chain = new Common( { chain : 'rinkeby', hardfork : 'london' } );
            const tx = FeeMarketEIP1559Transaction.fromTxData( rawTxETH ,  { chain }  );
            this.logger.info('rawTxETH with feeMarket:', { tx} );
            console.log("rawTxETH: " +  { rawTxETH } );
            // return tx;
            return rawTxETH;
        }
        else {
            const gasPrice = await this.getGasPrice(chainId);
            let rawTx = {
                gasPrice: this.numberToHexString(gasPrice),
                value: this.numberToHexString(value),
                to: to,
                data: data,
                from: from,
                nonce: this.numberToHexString(nonce),
                r: 0,
                s: 0
            }
            rawTx.gas = this.numberToHexString(await this.getGasLimit(rawTx));
            return rawTx;
        }
    }
    
    async createETHRawTransaction(from, to, data, value, chain) {
        let nonce = await this.getNonce(from);
        console.log("XXXXXXXXXXXXXXXXXXgetTransactionCount: " + await this.client.eth.getTransactionCount(from));
        const gwei = 1000000000;
        const priorityFee = 2 ;
        const sleepOnGas = 10 * 1000 ; // 10 Seconds
        const maxSleepOnGas = 12;
        let sleepOnGasCounter = 0;
        let rawTx;
        let temp_maxFeePerGas;

            while (globals.currentEthGasBasePrice > globals.currentEthGasPriceAvg) {
            await utils.sleep(sleepOnGas, { logger: this.logger });
            sleepOnGasCounter++;
            if (sleepOnGasCounter > maxSleepOnGas) {
                throw new CustomError(`High Base Gas: Transaction wasn't sent`);
            }    
        }        

        //////////   Debug Only -->
        // if(nonce === 3) { 
        //     temp_maxFeePerGas = 600 }
        // else {
        //     temp_maxFeePerGas = globals.currentEthGasBasePrice + priorityFee;
        // }
        //////////   Debug Only <--

            rawTx = {
            //gasPrice: this.numberToHexString(gasPrice),
        // Debug Only
            maxFeePerGas: this.numberToHexString((parseInt(globals.currentEthGasBasePrice) + parseInt(priorityFee)) * gwei),
            // maxFeePerGas: this.numberToHexString((temp_maxFeePerGas) * gwei),
            maxPriorityFeePerGas: this.numberToHexString(priorityFee * gwei),
            value: this.numberToHexString(value),
            to: to,
            data: data,
            from: from,
            nonce: this.numberToHexString(nonce),
            chainId:  this.numberToHexString(chain),
            accessList: [],
            type: "0x02",
            // r: 0,
            // s: 0
        }
        rawTx.gasLimit = this.numberToHexString(await this.getGasLimit(rawTx));
        this.logger.info('raw tx is:', { rawTx} );
        console.log("ETH raw tx is:" + rawTx);

        return rawTx;
    }

    signRawTransaction(rawTx, privateKey) {
        let tx = new Tx(rawTx);
        tx.sign(utils.hexStringToBuffer(privateKey));
        return tx;
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
        var from = await this.getAddress(privateKey);
        if (!from) {
            throw new CustomError(`No from address given. Is there an issue with the private key? ${stack}`);
        }
        let rawTx = await this.createRawTransaction(from, to, data, value);
        let txHash;
        let error = '';
        let errorInfo = '';
    
        try {
            let receipt;
            if (privateKey && privateKey.length) {
                let signedTx = this.signRawTransaction(rawTx, privateKey);
                const serializedTx = ethUtils.bufferToHex(signedTx.serialize());
                receipt = await this.client.eth.sendSignedTransaction(serializedTx).once('transactionHash', hash => txHash = hash);
            } else {
                //If no private key provided we use personal (personal is only for testing)
                delete rawTx.r;
                delete rawTx.s;
                delete rawTx.v;
                receipt = await this.client.eth.sendTransaction(rawTx).once('transactionHash', hash => txHash = hash);
            }
            if(receipt.status == 1) {
                this.logger.info(`Transaction Successful txHash:${receipt.transactionHash} blockNumber:${receipt.blockNumber}`);
                return receipt;
            }
                error = 'Transaction Receipt Status Failed';
                errorInfo = receipt;
        } catch(err) {
            if (err.message.indexOf('it might still be mined') > 0) {
                this.logger.warn(`Transaction was not mined within 750 seconds, please make sure your transaction was properly sent. Be aware that
                    it might still be mined. transactionHash:${txHash}`);
                fs.appendFileSync(this.manuallyCheck, `transactionHash:${txHash} to:${to} data:${data}\n`);
                return { transactionHash: txHash };
            }
                error = `Send Signed Transaction Failed TxHash:${txHash}`;
                errorInfo = err;
        }
        this.logger.error(error, errorInfo);
        this.logger.error('RawTx that failed', rawTx);
        throw new CustomError(`Transaction Failed: ${error} ${stack}`, errorInfo);
    }

}
