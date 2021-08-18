const web3 = require('web3');
const fs = require('fs');
const abiBridge = require('../../../abis/Bridge.json');
const abiFederation = require('../../../abis/Federation.json');
const TransactionSender = require('./TransactionSender');
const {ConfirmationTableReader} = require('../helpers/ConfirmationTableReader');
const AppendOnlyFileStorage = require('../helpers/AppendOnlyFileStorage');
const CustomError = require('./CustomError');
const {NullBot} = require('./chatBots');
const utils = require('./utils');

module.exports = class Federator {
    constructor(config, logger, Web3 = web3, chatBot = null) {
        this.config = config;
        this.logger = logger;

        this.mainWeb3 = new Web3(config.mainchain.host);
        this.sideWeb3 = new Web3(config.sidechain.host);

        this.mainBridgeContract = new this.mainWeb3.eth.Contract(abiBridge, this.config.mainchain.bridge);
        this.sideBridgeContract = new this.sideWeb3.eth.Contract(abiBridge, this.config.sidechain.bridge);
        this.federationContract = new this.sideWeb3.eth.Contract(abiFederation, this.config.sidechain.federation);

        this.transactionSender = new TransactionSender(this.sideWeb3, this.logger, this.config);

        this.lastBlockPath = `${config.storagePath || __dirname}/lastBlock.txt`;
        const failingTxIdsPath = `${config.storagePath || __dirname}/failingTxIds.txt`;
        this.failingTxIds = new AppendOnlyFileStorage(failingTxIdsPath);

        this.confirmationTable = config.confirmationTable;

        this.chatBot = chatBot || new NullBot(this.logger);
    }

    async run() {
        this.logger.info('Starting federator run');
        const maxAttempts = 20;
        for(let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                const currentBlock = await this._getCurrentBlockNumber();
                const chainId = await this.mainWeb3.eth.net.getId();
                const ctr = new ConfirmationTableReader(chainId, this.confirmationTable);

                const toBlock = currentBlock - ctr.getMinConfirmation();
                this.logger.info('Running to Block', toBlock);

                if (toBlock <= 0) return false;

                const fromBlock = this._getFromBlock(toBlock)
                this.logger.debug('Running from Block', fromBlock);

                if (!fromBlock) return false;

                await this._processBlocks(ctr, fromBlock, toBlock)

                this.logger.info('Federator run finished');
                return true;
            } catch (err) {
                this.logger.error(new Error('Exception Running Federator'), err);
                if(attempt === maxAttempts) {
                    this.logger.error('All attempts exhausted and still no success. Proceeding on as normal.')
                    const truncatedError = err.toString().slice(0, 200);
                    await this.chatBot.sendMessage(
                        `Error running federator after ${maxAttempts} attempts: ${truncatedError}`
                    );
                    return;
                } else {
                    this.logger.debug(`Retrying. Attempt ${attempt}/${maxAttempts}.`);
                    await utils.exponentialSleep(attempt, { logger: this.logger });
                }
            }
        }
    }

    async _processBlocks(ctr, fromBlock, toBlock) {
        const blocksPerPage = 1000;
        const numberOfPages = Math.ceil((toBlock - fromBlock) / blocksPerPage);
        this.logger.debug(`Total pages ${numberOfPages}, blocks per page ${blocksPerPage}`);

        let allLogsFromPagesConfirmed = true;
        let fromPageBlock = fromBlock;
        for (let currentPage = 1; currentPage <= numberOfPages; currentPage++) {
            let toPagedBlock = fromPageBlock + blocksPerPage - 1;
            if (currentPage === numberOfPages) {
                toPagedBlock = toBlock
            }
            this.logger.debug(`Page ${currentPage} getting events from block ${fromPageBlock} to ${toPagedBlock}`);
            const logs = await this.mainBridgeContract.getPastEvents('Cross', {
                fromBlock: fromPageBlock,
                toBlock: toPagedBlock
            });
            if (!logs) throw new Error('Failed to obtain the logs');

            this.logger.info(`Found ${logs.length} logs`);
            const lastBlockAllConfirmed = await this._processLogs(ctr, logs); // undefined meaning all blocks were confirmed

            if (allLogsFromPagesConfirmed) {
                // only save the progress when all before blocks were confirmed
                if (lastBlockAllConfirmed) allLogsFromPagesConfirmed = false;
                const newFromBlock = lastBlockAllConfirmed || toPagedBlock;
                this._saveProgress(this.lastBlockPath, newFromBlock);
                this.logger.info(`Progress saved, newFromBlock: ${newFromBlock}`);
            }

            this.logger.info(`Logs processed successfully until block ${toPagedBlock}`);

            fromPageBlock = toPagedBlock + 1;
        }
    }

    async _processLogs(ctr, logs) {
        try {
            const transactionSender = new TransactionSender(this.sideWeb3, this.logger, this.config);
            const from = await transactionSender.getAddress(this.config.privateKey);
            const currentBlock = await this._getCurrentBlockNumber();

            let newLastBlockNumber;
            let allLogsConfirmed = true;
            for (let log of logs) {
                this.logger.info('Processing event log:', log);

                const {
                    _amount: amount, _symbol: symbol,
                } = log.returnValues;

                if (this._isConfirmed(ctr, symbol, amount, currentBlock, log.blockNumber)) {
                    await this._processLog(log, from)
                } else if (allLogsConfirmed) {
                    newLastBlockNumber = log.blockNumber - 1;
                    allLogsConfirmed = false;
                }
            }

            return newLastBlockNumber;
        } catch (err) {
            throw new CustomError(`Exception processing logs`, err);
        }
    }

    async _processLog(log, from) {
        const {
            _to: receiver, _amount: amount, _symbol: symbol, _tokenAddress: tokenAddress,
            _decimals: decimals, _granularity: granularity, _userData: userData
        } = log.returnValues;

        let transactionId = await this.federationContract.methods.getTransactionId(
            tokenAddress,
            receiver,
            amount,
            symbol,
            log.blockHash,
            log.transactionHash,
            log.logIndex,
            decimals,
            granularity
        ).call();
        this.logger.info('get transaction id:', transactionId);

        let wasProcessed = await this.federationContract.methods.transactionWasProcessed(transactionId).call();
        this.logger.info('wasProcessed:', wasProcessed);
        if (!wasProcessed) {
            this.logger.info('getting transactionIdU:', {
                tokenAddress,
                receiver,
                amount,
                symbol,
                blockHash: log.blockHash,
                transactionHash: log.transactionHash,
                logIndex: log.logIndex,
                decimals,
                granularity,
                userData
            });

            let transactionIdU = await this.federationContract.methods.getTransactionIdU(
                tokenAddress,
                receiver,
                amount,
                symbol,
                log.blockHash,
                log.transactionHash,
                log.logIndex,
                decimals,
                granularity,
                userData || []
            ).call();

            this.logger.info('get transaction id U:', transactionIdU);
            let wasProcessedU = await this.federationContract.methods.transactionWasProcessed(transactionIdU).call();
            this.logger.info('wasProcessedU:', wasProcessedU);
            if (!wasProcessedU) {
                let hasVoted = await this.federationContract.methods.hasVoted(transactionIdU).call({ from: from });
                if (!hasVoted) {
                    this.logger.info(`Voting tx: ${log.transactionHash} block: ${log.blockHash} token: ${symbol}`);
                    await this._voteTransaction(tokenAddress,
                        receiver,
                        amount,
                        symbol,
                        log.blockHash,
                        log.transactionHash,
                        log.logIndex,
                        decimals,
                        granularity,
                        userData,
                        transactionId,
                        transactionIdU
                    );
                } else {
                    this.logger.debug(`Block: ${log.blockHash} Tx: ${log.transactionHash} token: ${symbol}  has already been voted by us`);
                }
            }
        } else {
            this.logger.debug(`Block: ${log.blockHash} Tx: ${log.transactionHash} token: ${symbol} was already processed`);
        }
    }


    async _voteTransaction(tokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData, transactionId, transactionIdU) {
        try {

            const transactionSender = new TransactionSender(this.sideWeb3, this.logger, this.config);
            this.logger.info(`Voting Transfer ${amount} of ${symbol} trough sidechain bridge ${this.sideBridgeContract.options.address} to receiver ${receiver}`);

            const isFailing = this._isFailingByTxId(transactionId, transactionHash) || this._isFailingByTxId(transactionIdU, transactionHash)
            if (isFailing) return false

            let txData;
            if(userData) {
                txData = await this.federationContract.methods.voteTransactionAt(
                    tokenAddress,
                    receiver,
                    amount,
                    symbol,
                    blockHash,
                    transactionHash,
                    logIndex,
                    decimals,
                    granularity,
                    userData
                ).encodeABI();
            } else {
                txData = await this.federationContract.methods.voteTransaction(
                    tokenAddress,
                    receiver,
                    amount,
                    symbol,
                    blockHash,
                    transactionHash,
                    logIndex,
                    decimals,
                    granularity
                ).encodeABI();
            }

            this.logger.info(`voteTransaction(${tokenAddress}, ${receiver}, ${amount}, ${symbol}, ${blockHash}, ${transactionHash}, ${logIndex}, ${decimals}, ${granularity}, ${userData})`);
            await transactionSender.sendTransaction(this.federationContract.options.address, txData, 0, this.config.privateKey);
            this.logger.info(`Voted transaction:${transactionHash} of block: ${blockHash} token ${symbol} to Federation Contract with TransactionIdU:${transactionIdU}`);
            return true;
        } catch (err) {
            if (transactionIdU && this._isEVMRevert(err)) {
                // we don't want to crash everything when there's a single failed transaction, so we keep a dead-letter
                // queue of those
                const msgHeader = (
                    `EVM revert when voting for tx with ` +
                    `idU: ${transactionIdU} hash: ${transactionHash} block: ${blockHash} token: ${symbol}.`
                );
                const msgFooter = `The transaction will be marked as failing and not retried automatically again.`;
                this.logger.error(msgHeader + ` Detailed error: ${err}\n` + msgFooter);

                this.failingTxIds.append(transactionIdU);

                await this.chatBot.sendMessage(`${msgHeader}\n${msgFooter}`);
                return false;
            } else {
                throw new CustomError(`Exception Voting tx:${transactionHash} block: ${blockHash} token ${symbol}`, err);
            }
        }
    }

    _isFailingByTxId(txId, transactionHash) {
        if (this.failingTxIds.contains(txId)) {
            this.logger.info(
                `Transaction with id ${txId}, hash: ${transactionHash} is marked as failing -- not voting for it`
            );
            return true;
        }
        return false;
    }

    _getFromBlock(toBlock) {
        if (!fs.existsSync(this.config.storagePath)) {
            fs.mkdirSync(this.config.storagePath);
        }
        let originalFromBlock = this.config.mainchain.fromBlock || 0;
        let fromBlock;
        try {
            fromBlock = fs.readFileSync(this.lastBlockPath, 'utf8');
        } catch (err) {
            fromBlock = originalFromBlock;
        }
        if (fromBlock < originalFromBlock) {
            fromBlock = originalFromBlock;
        }
        if (fromBlock >= toBlock) {
            this.logger.warn(`Current chain Height ${toBlock} is the same or lesser than the last block processed ${fromBlock}`);
            return undefined;
        }
        fromBlock = parseInt(fromBlock) + 1;

        return fromBlock;
    }

    _saveProgress(path, value) {
        if (value) {
            fs.writeFileSync(path, value);
        }
    }

    _isConfirmed(ctr, symbol, amount, currentBlock, logBlockNumber) {
        let confirmations = ctr.getConfirmations(symbol, amount)
        let blockConfirmations = currentBlock - logBlockNumber;
        return confirmations <= blockConfirmations;
    }

    _isEVMRevert(error) {
        const revertMessage = 'Transaction has been reverted by the EVM';
        if (error.message.indexOf(revertMessage) !== -1) {
            return true;
        }
        if (error.stack && error.stack.toString().indexOf(revertMessage) !== -1) {
            return true;
        }
        return false;
    }

    async _getCurrentBlockNumber() {
        return this.mainWeb3.eth.getBlockNumber();
    }
}
