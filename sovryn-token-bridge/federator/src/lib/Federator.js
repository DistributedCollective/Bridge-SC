const web3 = require('web3');
const { ethers } = require('ethers');
const fs = require('fs');
const abiBridge = require('../../../abis/Bridge.json');
const abiFederation = require('../../../abis/Federation.json');
const TransactionSender = require('./TransactionSender');
const { ConfirmationTableReader } = require('../helpers/ConfirmationTableReader');
const AppendOnlyFileStorage = require('../helpers/AppendOnlyFileStorage');
const CustomError = require('./CustomError');
const { NullBot } = require('./chatBots');
const utils = require('./utils');
const {
    MAIN_SIGNATURE_REQUEST,
    SIDE_SIGNATURE_REQUEST,
    MAIN_SIGNATURE_SUBMISSION,
    SIDE_SIGNATURE_SUBMISSION,
} = require('../helpers/p2pMessageTypes');
const { sign } = require('crypto');

module.exports = class Federator {
    constructor(config, logger, Web3 = web3, network, chatBot = null) {
        this.config = config;
        this.network = network;
        this.logger = logger;

        this.mainWeb3 = new Web3(config.mainchain.host);
        this.sideWeb3 = new Web3(config.sidechain.host);

        this.mainBridgeContract = new this.mainWeb3.eth.Contract(
            abiBridge,
            this.config.mainchain.bridge
        );
        this.sideBridgeContract = new this.sideWeb3.eth.Contract(
            abiBridge,
            this.config.sidechain.bridge
        );
        this.federationContract = new this.sideWeb3.eth.Contract(
            abiFederation,
            this.config.sidechain.federation
        );

        this.transactionSender = new TransactionSender(this.sideWeb3, this.logger, this.config, '');

        this.lastBlockPath = `${config.storagePath || __dirname}/lastBlock.txt`;
        const failingTxIdsPath = `${config.storagePath || __dirname}/failingTxIds.txt`;
        this.failingTxIds = new AppendOnlyFileStorage(failingTxIdsPath);

        this.confirmationTable = config.confirmationTable;

        this.chatBot = chatBot || new NullBot(this.logger);
    }

    async run() {
        this.logger.info('Starting federator run');
        const maxAttempts = 20;
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            // Get first and last blocks that will be scanned and run the scan
            try {
                const currentBlock = await this._getCurrentBlockNumber();
                const chainId = await this.mainWeb3.eth.net.getId();
                const ctr = new ConfirmationTableReader(chainId, this.confirmationTable);
                const toBlock = currentBlock - ctr.getMinConfirmation();

                this.logger.info('Running to Block', toBlock);

                if (toBlock <= 0) return false;

                const fromBlock = this._getFromBlock(toBlock);
                if (!fromBlock) return false;

                this.logger.debug('Running from Block', fromBlock);

                await this._processBlocks(ctr, fromBlock, toBlock);

                this.logger.info('Federator run finished');

                return true;
            } catch (err) {
                this.logger.error(new Error('Exception Running Federator'), err);
                if (attempt === maxAttempts) {
                    this.logger.error(
                        'All attempts exhausted and still no success. Proceeding on as normal.'
                    );
                    const truncatedError = err.toString().slice(0, 200);
                    await this.chatBot.sendMessage(
                        `Error running federator after ${maxAttempts} attempts: ${truncatedError}`
                    );
                    return false;
                } else {
                    this.logger.debug(`Retrying. Attempt ${attempt}/${maxAttempts}.`);
                    await utils.exponentialSleep(attempt, { logger: this.logger });
                }
            }
        }
    }

    // Paginate blocks to scan, fetch events of each page and run processing of them
    async _processBlocks(ctr, fromBlock, toBlock) {
        const blocksPerPage = 100;
        const numberOfPages = Math.ceil((toBlock - fromBlock) / blocksPerPage);
        this.logger.debug(`Total pages ${numberOfPages}, blocks per page ${blocksPerPage}`);

        let allLogsFromPagesConfirmed = true;
        let fromPageBlock = fromBlock;
        for (let currentPage = 1; currentPage <= numberOfPages; currentPage++) {
            let toPagedBlock = fromPageBlock + blocksPerPage - 1;
            if (currentPage === numberOfPages) {
                toPagedBlock = toBlock;
            }
            this.logger.debug(
                `Page ${currentPage} getting events from block ${fromPageBlock} to ${toPagedBlock}`
            );
            const logs = await this.mainBridgeContract.getPastEvents('Cross', {
                fromBlock: fromPageBlock,
                toBlock: toPagedBlock,
            });

            if (!logs) throw new Error('Failed to obtain the logs');
            this.logger.info(`Found ${logs.length} logs`);
            const lastBlockAllConfirmed = await this._processLogs(ctr, logs); // undefined meaning all blocks were confirmed

            if (allLogsFromPagesConfirmed) {
                // only save the progress when all before blocks were confirmed
                if (lastBlockAllConfirmed) allLogsFromPagesConfirmed = false;
                const newFromBlock = lastBlockAllConfirmed || toPagedBlock;
                this._saveProgress(this.lastBlockPath, newFromBlock.toString());
                this.logger.info(`Progress saved, newFromBlock: ${newFromBlock}`);
            }
            this.logger.info(`Logs processed successfully until block ${toPagedBlock}`);

            fromPageBlock = toPagedBlock + 1;
        }
    }

    // Loop around logs to process each of them
    async _processLogs(ctr, logs) {
        try {
            const transactionSender = new TransactionSender(
                this.sideWeb3,
                this.logger,
                this.config,
                ''
            );
            const from = await transactionSender.getAddress(this.config.privateKey);
            const currentBlock = await this._getCurrentBlockNumber();

            let newLastBlockNumber;
            let allLogsConfirmed = true;
            for (let log of logs) {
                this.logger.info('Processing event log:', log);

                const { _amount: amount, _symbol: symbol } = log.returnValues;

                if (this._isConfirmed(ctr, symbol, amount, currentBlock, log.blockNumber)) {
                    const signatures = await this._requestSignatureFromFederators(log);
                    this.logger.info('Collected enough signatures');
                    await this._processLog(log, from, signatures);
                } else if (allLogsConfirmed) {
                    newLastBlockNumber = log.blockNumber - 1;
                    allLogsConfirmed = false;
                }
            }

            return newLastBlockNumber;
        } catch (err) {
            throw new CustomError('Exception processing logs', err);
        }
    }

    _requestSignatureFromFederators(log) {
        return new Promise((resolve, reject) => {
            this.logger.info('Requesting other federators to sign event');

            setTimeout(
                () => reject("Didn't get enough signatures after 10 minutes timeout"),
                60000
            );

            // Select correct message type depending on main on side federator
            const { request, submission } =
                this.logger.category === 'MAIN-FEDERATOR'
                    ? { request: MAIN_SIGNATURE_REQUEST, submission: MAIN_SIGNATURE_SUBMISSION }
                    : { request: SIDE_SIGNATURE_REQUEST, submission: SIDE_SIGNATURE_SUBMISSION };

            const signatures = [];
            this.network.net.onMessage(async (msg) => {
                if (msg.type === submission) {
                    this.logger.info(`Submission received from ${msg.source.id}`);
                    signatures.push(msg.data);
                    if (signatures.length >= this.config.minimumPeerAmount) {
                        resolve(signatures);
                    }
                }
            });
            this.network.net.broadcast(request, { log });
        });
    }

    async _processLog(log, from, signatures) {
        const {
            _to: receiver,
            _amount: amount,
            _symbol: symbol,
            _tokenAddress: tokenAddress,
            _decimals: decimals,
            _granularity: granularity,
            _userData: userData,
        } = log.returnValues;

        let transactionId = await this.federationContract.methods
            .getTransactionId(
                tokenAddress,
                receiver,
                amount,
                symbol,
                log.blockHash,
                log.transactionHash,
                log.logIndex,
                decimals,
                granularity
            )
            .call();
        this.logger.info('get transaction id:', transactionId);

        let wasProcessed = await this.federationContract.methods
            .transactionWasProcessed(transactionId)
            .call();
        this.logger.info('wasProcessed:', wasProcessed);

        if (wasProcessed) {
            this.logger.debug(
                `Block: ${log.blockHash} Tx: ${log.transactionHash} token: ${symbol} was already processed`
            );
            return;
        }

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
            userData,
        });

        let transactionIdU = await this.federationContract.methods
            .getTransactionIdU(
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
            )
            .call();

        this.logger.info('get transaction id U:', transactionIdU);

        let wasProcessedU = await this.federationContract.methods
            .transactionWasProcessed(transactionIdU)
            .call();
        this.logger.info('wasProcessedU:', wasProcessedU);

        if (wasProcessedU) return;

        this.logger.info(
            `Executing tx: ${log.transactionHash} block: ${log.blockHash} token: ${symbol}`
        );
        await this._executeTransaction(
            tokenAddress,
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
            transactionIdU,
            signatures
        );
    }

    async _executeTransaction(
        tokenAddress,
        receiver,
        amount,
        symbol,
        blockHash,
        transactionHash,
        logIndex,
        decimals,
        granularity,
        userData,
        transactionId,
        transactionIdU,
        signatures
    ) {
        try {
            const transactionSender = new TransactionSender(
                this.sideWeb3,
                this.logger,
                this.config,
                ''
            );
            this.logger.info(
                `Executing Transfer ${amount} of ${symbol} trough sidechain bridge ${this.sideBridgeContract.options.address} to receiver ${receiver}`
            );

            const isFailing =
                this._isFailingByTxId(transactionId, transactionHash) ||
                this._isFailingByTxId(transactionIdU, transactionHash);
            if (isFailing) return false;

            let txData;
            if (userData) {
                txData = await this.federationContract.methods
                    .executeTransactionAt(
                        tokenAddress,
                        receiver,
                        amount,
                        symbol,
                        blockHash,
                        transactionHash,
                        logIndex,
                        decimals,
                        granularity,
                        userData,
                        signatures
                    )
                    .encodeABI();
            } else {
                txData = await this.federationContract.methods
                    .executeTransaction(
                        tokenAddress,
                        receiver,
                        amount,
                        symbol,
                        blockHash,
                        transactionHash,
                        logIndex,
                        decimals,
                        granularity,
                        signatures
                    )
                    .encodeABI();
            }

            await transactionSender.sendTransaction(
                this.federationContract.options.address,
                txData,
                0,
                this.config.privateKey
            );
            this.logger.info(
                `Executed transaction:${transactionHash} of block: ${blockHash} token ${symbol} to Federation Contract with TransactionIdU:${transactionIdU}`
            );

            return true;
        } catch (err) {
            if (transactionIdU && this._isEVMRevert(err)) {
                // we don't want to crash everything when there's a single failed transaction, so we keep a dead-letter
                // queue of those
                const msgHeader =
                    `EVM revert when executing tx with ` +
                    `idU: ${transactionIdU} hash: ${transactionHash} block: ${blockHash} token: ${symbol}.`;
                const msgFooter = `The transaction will be marked as failing and not retried automatically again.`;
                this.logger.error(msgHeader + ` Detailed error: ${err}\n` + msgFooter);

                this.failingTxIds.append(transactionIdU);

                await this.chatBot.sendMessage(`${msgHeader}\n${msgFooter}`);
                return false;
            } else {
                throw new CustomError(
                    `Exception executing tx:${transactionHash} block: ${blockHash} token ${symbol}`,
                    err
                );
            }
        }
    }

    _isFailingByTxId(txId, transactionHash) {
        if (this.failingTxIds.contains(txId)) {
            this.logger.info(
                `Transaction with id ${txId}, hash: ${transactionHash} is marked as failing -- not executing it`
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
            this.logger.warn(
                `Current chain Height ${toBlock} is the same or lesser than the last block processed ${fromBlock}`
            );
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
        let confirmations = ctr.getConfirmations(symbol, amount);
        let blockConfirmations = currentBlock - logBlockNumber;
        return confirmations <= blockConfirmations;
    }

    _isEVMRevert(error) {
        const revertMessages = [
            'Transaction has been reverted by the EVM',
            'Returned error: execution reverted',
        ];
        for (let revertMessage of revertMessages) {
            if (error.message.indexOf(revertMessage) !== -1) {
                return true;
            }
            if (error.stack && error.stack.toString().indexOf(revertMessage) !== -1) {
                return true;
            }
        }
        return false;
    }

    async _getCurrentBlockNumber() {
        return this.mainWeb3.eth.getBlockNumber();
    }

    async signTransaction({ blockNumber, id }) {
        const logs = await this.mainBridgeContract.getPastEvents('Cross', {
            fromBlock: blockNumber,
            toBlock: blockNumber,
            filter: { id },
        });

        if (logs.length !== 1) throw new Error('Invalid return when searching for event');

        const { _tokenAddress, _amount, _to, _symbol, _decimals, _granularity, _userData } =
            logs[0].returnValues;
        const { blockHash, transactionHash, logIndex } = logs[0];
        const txId = await this.federationContract.methods
            .getTransactionIdU(
                _tokenAddress,
                _to,
                _amount,
                _symbol,
                blockHash,
                transactionHash,
                logIndex,
                _decimals,
                _granularity,
                _userData || []
            )
            .call();

        const wallet = new ethers.Wallet(this.config.privateKey);
        return await wallet.signMessage(ethers.utils.arrayify(txId));
    }
};
