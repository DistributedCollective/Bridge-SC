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
    MAIN_FEDERATOR,
    MAIN_SIGNATURE_REQUEST,
    SIDE_SIGNATURE_REQUEST,
    MAIN_SIGNATURE_SUBMISSION,
    SIDE_SIGNATURE_SUBMISSION,
} = require('./constants');
const { sign } = require('crypto');

module.exports = class Federator {
    constructor(type, config, logger, network, Web3 = web3, chatBot = null) {
        this.type = type;
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

    async populateMemberAddresses() {
        this.members = await this.federationContract.methods.getMembers().call();
    }

    async getMemberAddresses() {
        return this.members;
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
            const currentBlock = await this._getCurrentBlockNumber();

            let newLastBlockNumber;
            let allLogsConfirmed = true;
            for (let log of logs) {
                if (await this._isBlackListedLog(log)) {
                    this.logger.warn('Skipping transfer to/from a blacklisted address, skipped log:');
                    continue;
                }

                this.logger.info('Processing event log:', log);

                const { _amount: amount, _symbol: symbol } = log.returnValues;

                if (this._isConfirmed(ctr, symbol, amount, currentBlock, log.blockNumber)) {
                    const alreadyProcessed = await this._isAlreadyProcessed(log);
                    if (alreadyProcessed) {
                        this.logger.debug(
                            `Block: ${log.blockHash} Tx: ${log.transactionHash} token: ${symbol} is already processed (on Bridge) -- no need to get signatures`
                        );
                    } else {
                        const signatures = await this._requestSignatureFromFederators(log);
                        this.logger.info('Collected enough signatures');
                        await this._processLog(log, signatures);
                    }
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

    async _requestSignatureFromFederators(log) {
        this.logger.info(`VALID TRANSFER IN TX: ${log.transactionHash}`);
        return [];
        return new Promise((resolve, reject) => {
            this.logger.info('Requesting other federators to sign event');

            const timer = setTimeout(
                () => {
                    this.logger.warn("Timeout: Didn't get enough signatures after waiting");
                    try {
                        listener.unsubscribe();
                    } catch(e) {
                        this.logger.error(`Error subscribing from listener on timeout: ${e}`);
                    }
                    reject("Didn't get enough signatures before timeout")
                },
                this.config.signatureRequestTimeoutMs || 60000
            );

            // Select correct message type depending on main on side federator
            const { requestType, submissionType } =
                this.type === MAIN_FEDERATOR
                    ? {
                          requestType: MAIN_SIGNATURE_REQUEST,
                          submissionType: MAIN_SIGNATURE_SUBMISSION,
                      }
                    : {
                          requestType: SIDE_SIGNATURE_REQUEST,
                          submissionType: SIDE_SIGNATURE_SUBMISSION,
                      };

            const signatures = new Set();
            const signers = new Set();
            const listener = this.network.net.onMessage(async (msg) => {
                if (msg.type === submissionType && msg.data.logId === log.id) {
                    this.logger.info(`Submission received from ${msg.source.id}`);

                    const { signatureData } = msg.data;
                    const signerAddress = await this._recoverLogSigner(log, signatureData);

                    if (!this.members.includes(signerAddress)) {
                        this.logger.warn(
                            `Submission from ${msg.source.id} has not been signed by a member of federation`
                        );
                        return;
                    }

                    if (signers.has(signerAddress)) {
                        this.logger.warn(
                            `Signer ${signerAddress} has already submitted a signature`
                        );
                        return;
                    }
                    signers.add(signerAddress);

                    // Require 2 minutes or signaturesTTL/2 of buffer, whichever is smaller, to avoid sending the
                    // transactions with signatures that might expire before the transaction gets mined in the blockchain.
                    // 2 minutes might not be enough, but we need to start with something
                    const deadlineBufferSeconds = Math.min(
                        this.config.signaturesTTL / 2,
                        120
                    );
                    if (!utils.validateDeadline(signatureData.deadline, deadlineBufferSeconds)) {
                        this.logger.warn(
                            `Deadline ${signatureData.deadline} has either passed or is too close`
                        );
                        return;
                    }

                    signatures.add(signatureData);
                    if (signatures.size >= this.config.minimumPeerAmount) {
                        clearTimeout(timer);
                        listener.unsubscribe();
                        resolve(Array.from(signatures));
                    }
                }
            });
            this.network.net.broadcast(requestType, { log });
        });
    }

    async _recoverLogSigner(log, signatureData) {
        const { blockHash, transactionHash, logIndex } = log;
        const { _tokenAddress, _to, _amount, _symbol, _userData, _decimals, _granularity } =
            log.returnValues;
        const { signature, deadline } = signatureData;
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

        const networkId = await this.sideWeb3.eth.net.getId();
        const federationAddress = this.config.sidechain.federation;

        const payload = ethers.utils.solidityPack(
            ['bytes32', 'uint256', 'address', 'uint256'],
            [txId, networkId, federationAddress, deadline]
        );

        const digest = ethers.utils.hashMessage(ethers.utils.arrayify(payload));
        return ethers.utils.recoverAddress(digest, signature);
    }

    async _isAlreadyProcessed(log) {
        const isBlacklisted = await this._isBlackListedLog(log);  // extra safety
        if (isBlacklisted) {
            this.logger.warn('Treating already processed log as blacklisted. Log:');
            this.logger.warn(log);
            return true;
        }
        const {
            _to: receiver,
            _amount: amount,
        } = log.returnValues;
        let bridgeTransactionId = await this.sideBridgeContract.methods.getTransactionId(
            log.blockHash,
            log.transactionHash,
            receiver,
            amount,
            log.logIndex,
        ).call();
        return await this.sideBridgeContract.methods.processed(bridgeTransactionId).call();
    }

    async _processLog(log, signatures) {
        const {
            _to: receiver,
            _amount: amount,
            _symbol: symbol,
            _tokenAddress: tokenAddress,
            _decimals: decimals,
            _granularity: granularity,
            _userData: userData,
        } = log.returnValues;

        // We check the status from the bridge first before bothering checking the Federation contract.
        // Actually, a check from the bridge is all that we need (in principle) -- but let's leave the other checks
        // there too.
        // Note that we don't really need to double-check here either, since we check this before requesting
        // signatures from federators, but let's do it anyway for safety.
        let wasProcessed = await this._isAlreadyProcessed(log);
        if (wasProcessed) {
            this.logger.debug(
                `Block: ${log.blockHash} Tx: ${log.transactionHash} token: ${symbol} was already processed (on Bridge)`
            );
            return;
        }

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

        wasProcessed = await this.federationContract.methods
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
        signatures = signatures && this._removeNotNeededSignatures(signatures);

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

    _removeNotNeededSignatures(signatures) {
        return signatures.slice(0, this.config.minimumPeerAmount);
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
        const allLogs = await this.mainBridgeContract.getPastEvents('Cross', {
            fromBlock: blockNumber,
            toBlock: blockNumber,
        });
        // Passing filter: { id } to getPastEvents won't do any filtering, we need to filter like this
        const logs = allLogs.filter(log => log.id === id);

        if (logs.length !== 1) {
            this.logger.error(`Got ${logs.length} logs when expecting 1. Block number: ${blockNumber}, Log id: ${id}, Logs:`);
            this.logger.error(logs);
            throw new CustomError('Invalid return when searching for event');
        }

        if (await this._isBlackListedLog(logs[0])) {
            throw new CustomError(`Refusing to sign blacklisted log ${logs[0].id}, tx ${logs[0].transactionHash}`);
        }

        const { _tokenAddress, _amount, _to, _symbol, _decimals, _granularity, _userData } =
            logs[0].returnValues;
        const { blockHash, transactionHash, logIndex } = logs[0];

        const chainId = await this.sideWeb3.eth.net.getId();
        const ctr = new ConfirmationTableReader(chainId, this.confirmationTable);
        const currentBlock = await this._getCurrentBlockNumber();

        if (!this._isConfirmed(ctr, _symbol, _amount, currentBlock, blockNumber))
            throw new CustomError(
                `Block number ${blockNumber} not confirmed yet. No signature provided to leader.`
            );

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

        const deadline = utils.createTimestamp(this.config.signaturesTTL);
        const payload = ethers.utils.solidityPack(
            ['bytes32', 'uint256', 'address', 'uint256'],
            [txId, chainId, this.config.sidechain.federation, deadline]
        );

        const wallet = new ethers.Wallet(this.config.privateKey);
        const signature = await wallet.signMessage(ethers.utils.arrayify(payload));

        return { signatureData: { signature, deadline }, logId: id };
    }

    _isBlackListedAddress(address) {
        if (typeof address !== 'string' || !address.startsWith('0x') || address.length !== 42) {
            throw new CustomError(`Invalid address: ${address}`);
        }
        return (
            address.toLowerCase() ===
            '0xc92ebecda030234c10e149beead6bba61197531a'.toLowerCase()
        );
    }

    async _isBlackListedLog(log) {
        const txHash = log.transactionHash;
        const receiver = log.returnValues._to;
        const userData = log.returnValues._userData;
        if (this._isBlackListedAddress(receiver)) {
            this.logger.warn(`Transaction ${txHash} is blacklisted (receiver ${receiver})`);
            return true;
        }
        if (userData) {
            if (userData.length === 66) {
                const userDataAddress = userData.replace(/^0x000000000000000000000000/, '0x')
                if (userDataAddress.length === 42 && this._isBlackListedAddress(userDataAddress)) {
                    this.logger.warn(`Transaction ${txHash} is blacklisted (userData ${userData})`);
                    return true;
                }
            } else if (userData.length > 66) {
                this.logger.warn(`Transaction ${txHash} is a direct fastbtc transfer which is currently blocked`);
                return true;
            }
        }

        const transaction = await this.mainWeb3.eth.getTransaction(txHash);
        if (this._isBlackListedAddress(transaction.from)) {
            this.logger.warn(`Transaction ${txHash} is blacklisted (sender ${transaction.from})`);
            return true;
        }

        return false;
    }
};
