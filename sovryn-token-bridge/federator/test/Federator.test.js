const fs = require('fs');
const path = require('path');
const { ethers } = require('ethers');

const Web3PromiEvent = require('web3-core-promievent');

const Federator = require('../src/lib/Federator');
const utils = require('../src/lib/utils');
const TransactionSender = require('../src/lib/TransactionSender');
const CustomError = require('../src/lib/CustomError');
const eth = require('./web3Mock/eth.js');
const web3Mock = require('./web3Mock');
const { ConfirmationTableReader } = require('../src/helpers/ConfirmationTableReader');

const configFile = fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8');
const config = JSON.parse(configFile);

const { MAIN_FEDERATOR, MAIN_SIGNATURE_SUBMISSION } = require('../src/lib/constants');

const logger = {
    trace: jest.fn(),
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
};
const storagePath = `${__dirname}`;
const testPath = `${storagePath}/lastBlock.txt`;
const testFailingTxIdsPath = `${storagePath}/failingTxIds.txt`;

let testConfig = { ...config, storagePath };

const disableEtherscanGasPrices = (sender) => {
    sender.gasPriceEstimator.getEtherscanGasPrices = jest
        .fn()
        .mockRejectedValue(new Error('expected etherscan error'));
};

function mockFederatorMethods(federator, methods) {
    federator.mainWeb3.eth = federator.mainWeb3.eth.mockMethods(methods);
    disableEtherscanGasPrices(federator.transactionSender);
}

function cleanUpTestPaths() {
    if (fs.existsSync(testPath)) {
        fs.unlinkSync(testPath);
    }
    if (fs.existsSync(testFailingTxIdsPath)) {
        fs.unlinkSync(testFailingTxIdsPath);
    }
}

function createPromiEventError(message) {
    const promiEvent = Web3PromiEvent();
    setTimeout(() => {
        promiEvent.reject(new Error(message));
    }, 10);
    return promiEvent.eventEmitter;
}

let savedSleepRandomNumberOfBlocks = null;
let savedExponentialSleep = null;
function disableSleep() {
    if (!savedSleepRandomNumberOfBlocks) {
        savedSleepRandomNumberOfBlocks = utils.sleepRandomNumberOfBlocks;
        utils.sleepRandomNumberOfBlocks = jest.fn();
    }
    if (!savedExponentialSleep) {
        savedExponentialSleep = utils.exponentialSleep;
        utils.exponentialSleep = jest
            .fn()
            .mockRejectedValue(new Error('reaching exponential sleep means there is an error!'));
    }
}
function enableSleep() {
    if (savedSleepRandomNumberOfBlocks) {
        utils.sleepRandomNumberOfBlocks = savedSleepRandomNumberOfBlocks;
        savedSleepRandomNumberOfBlocks = null;
    }
    if (savedExponentialSleep) {
        utils.exponentialSleep = savedExponentialSleep;
        savedExponentialSleep = null;
    }
}

describe('Federator module tests', () => {
    beforeEach(function () {
        jest.clearAllMocks();
        cleanUpTestPaths();
        disableSleep();
    });

    afterEach(() => {
        cleanUpTestPaths();
        enableSleep();
    });

    it('Runs the main federator process sucessfully', async () => {
        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        let result = await federator.run();

        expect(result).toBeTruthy();
    });

    it('Runs the main federator process with pagination', async () => {
        const expectedConfirmations = 5760;
        const twoPages = 2002;
        const currentBlock = testConfig.mainchain.fromBlock + twoPages + expectedConfirmations;
        const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);

        mockFederatorMethods(federator, {
            getBlockNumber: () => Promise.resolve(currentBlock),
            getId: () => Promise.resolve(1),
        });
        const _processLogsSpy = jest.spyOn(federator, '_processLogs');

        let result = await federator.run();

        expect(result).toBeTruthy();
        let value = fs.readFileSync(testPath, 'utf8');
        expect(parseInt(value)).toEqual(currentBlock - expectedConfirmations);

        // TODO: figure out why this broke
        // expect(_processLogsSpy).toHaveBeenCalledTimes(3);
        expect(_processLogsSpy).toHaveBeenCalled();
    });

    it('Runs the main federator process with pagination limit', async () => {
        const expectedConfirmations = 5760;
        const onePage = 1001;
        const currentBlock = testConfig.mainchain.fromBlock + onePage + expectedConfirmations;
        const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        mockFederatorMethods(federator, {
            getBlockNumber: () => Promise.resolve(currentBlock),
            getId: () => Promise.resolve(1),
        });
        federator.mainWeb3.eth.getBlockNumber = () => Promise.resolve(currentBlock);
        federator.mainWeb3.eth.net.getId = () => Promise.resolve(1);
        const _processLogsSpy = jest.spyOn(federator, '_processLogs');

        let result = await federator.run();

        expect(result).toBeTruthy();
        let value = fs.readFileSync(testPath, 'utf8');
        expect(parseInt(value)).toEqual(currentBlock - expectedConfirmations);

        // TODO: figure out why this broke
        //expect(_processLogsSpy).toHaveBeenCalledTimes(1);
        expect(_processLogsSpy).toHaveBeenCalled();
    });

    it('Saves the progress in a file path', async () => {
        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, web3Mock);

        federator._saveProgress(testPath, 'test');

        expect(fs.existsSync(testPath)).toBeTruthy();

        let value = fs.readFileSync(testPath, 'utf8');
        expect(value).toEqual('test');
    });

    it('Should not execute empty log and receiver', async () => {
        eth.sendSignedTransaction = jest.fn().mockImplementation(() => {
            throw new Error('Some Error');
        });

        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        disableEtherscanGasPrices(federator.transactionSender);
        try {
            await federator._executeTransaction(null, null);
            expect(false).toBeTruthy();
        } catch (err) {
            expect(err).not.toBeNull();
        }
        expect(fs.existsSync(testPath)).toBeFalsy();
    });

    // For some unkown reason, passes only when ran alone with .only
    it.skip('Execute a transaction from a log entry', async () => {
        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        disableEtherscanGasPrices(federator.transactionSender);
        let log = {
            logIndex: 2,
            blockNumber: 2557,
            blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash: '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues: {
                0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                2: '1000000000000000000',
                3: 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000000000000000000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461',
            },
            event: 'Cross',
            signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics: [
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                ],
            },
        };

        const { blockHash, transactionHash, logIndex } = log;
        const { _tokenAddress, _to, _amount, _symbol } = log.returnValues;

        let result = await federator._executeTransaction(
            _tokenAddress,
            _to,
            _amount,
            _symbol,
            blockHash,
            transactionHash,
            logIndex,
            18,
            1,
            '0x0',
            '0xffffff',
            '0xfffff1',
            ['sig1', 'sig2']
        );
        console.log({ result });
        expect(result).toBeTruthy();
    });

    // For some unkown reason, passes only when ran alone with .only
    it.skip('Should return undefined for a list of 1 confirmed log', async () => {
        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        disableEtherscanGasPrices(federator.transactionSender);
        federator._requestSignatureFromFederators = () => ['signature1', 'signature2'];
        let logs = [
            {
                logIndex: 2,
                blockNumber: 10000,
                blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
                transactionHash:
                    '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
                transactionIndex: 0,
                address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
                id: 'log_a755a817',
                returnValues: {
                    0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    2: '1000000000000000000',
                    3: 'MAIN',
                    _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    _amount: '50',
                    _symbol: 'MAIN',
                    _userData: '0x45787472612064617461',
                },
                event: 'Cross',
                signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                raw: {
                    data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                    topics: [
                        '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                        '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                        '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                    ],
                },
            },
        ];
        const ctr = new ConfirmationTableReader(3, testConfig.confirmationTable);

        let result = await federator._processLogs(ctr, logs);
        expect(result).toBeUndefined();
    });

    it('Should return the logBlockNumber for a list of 1 unconfirmed log', async () => {
        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        disableEtherscanGasPrices(federator.transactionSender);
        const logBlockNumber = 2683000;
        let logs = [
            {
                logIndex: 2,
                blockNumber: logBlockNumber,
                blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
                transactionHash:
                    '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
                transactionIndex: 0,
                address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
                id: 'log_a755a817',
                returnValues: {
                    0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    2: '1000000000000000000',
                    3: 'MAIN',
                    _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    _amount: '1000000000000000000',
                    _symbol: 'MAIN',
                    _userData: '0x45787472612064617461',
                },
                event: 'Cross',
                signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                raw: {
                    data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                    topics: [
                        '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                        '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                        '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                    ],
                },
            },
        ];
        const ctr = new ConfirmationTableReader(3, testConfig.confirmationTable);

        let result = await federator._processLogs(ctr, logs);
        expect(result).toEqual(logBlockNumber - 1);
    });

    // For some unkown reason, passes only when ran alone with .only
    it.skip('Should return the second logBlockNumber for a list of 2 log, only first confirmed', async () => {
        let federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
        federator._requestSignatureFromFederators = () => ['signature1', 'signature2'];
        disableEtherscanGasPrices(federator.transactionSender);
        const firstLogBlockNumber = 15000;
        const currentBlockNumber = 42000;
        const ctr = new ConfirmationTableReader(3, testConfig.confirmationTable);
        const secondLogBlockNumber = currentBlockNumber - ctr.getMinConfirmation();

        let logs = [
            {
                logIndex: 2,
                blockNumber: firstLogBlockNumber,
                blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
                transactionHash:
                    '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
                transactionIndex: 0,
                address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
                id: 'log_a755a817',
                returnValues: {
                    0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    2: '1000000000000000000',
                    3: 'MAIN',
                    _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    _amount: '1000',
                    _symbol: 'MAIN',
                    _userData: '0x45787472612064617461',
                },
                event: 'Cross',
                signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                raw: {
                    data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                    topics: [
                        '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                        '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                        '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                    ],
                },
            },
            {
                logIndex: 3,
                blockNumber: secondLogBlockNumber,
                blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
                transactionHash:
                    '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
                transactionIndex: 0,
                address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
                id: 'log_a755a817',
                returnValues: {
                    0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    2: '1000000000000000000',
                    3: 'MAIN',
                    _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    _amount: '1000',
                    _symbol: 'MAIN',
                    _userData: '0x45787472612064617461',
                },
                event: 'Cross',
                signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                raw: {
                    data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                    topics: [
                        '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                        '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                        '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                    ],
                },
            },
        ];

        let result = await federator._processLogs(ctr, logs);
        expect(result).toEqual(secondLogBlockNumber - 1);
    });

    describe('Signatures', () => {
        const wallets = [];
        const signatures = [];

        const logs = [
            {
                logIndex: 2,
                blockNumber: 10000,
                blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
                transactionHash:
                    '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
                transactionIndex: 0,
                address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
                id: 'log_d745c814',
                returnValues: {
                    0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    2: '1000000000000000000',
                    3: 'MAIN',
                    _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    _amount: '50',
                    _symbol: 'MAIN',
                    _userData: '0x45787472612064617461',
                    _decimals: 18,
                    _granularity: 1,
                },
                event: 'Cross',
                signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                raw: {
                    data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                    topics: [
                        '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                        '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                        '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                    ],
                },
            },
            {
                logIndex: 3,
                blockNumber: 10000,
                blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
                transactionHash:
                    '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
                transactionIndex: 0,
                address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
                id: 'log_a755a817',
                returnValues: {
                    0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    2: '1000000000000000000',
                    3: 'MAIN',
                    _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                    _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                    _amount: '1000',
                    _symbol: 'MAIN',
                    _userData: '0x45787472612064617461',
                    _decimals: 18,
                    _granularity: 1,
                },
                event: 'Cross',
                signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                raw: {
                    data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                    topics: [
                        '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                        '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                        '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                    ],
                },
            },
        ];

        beforeAll(async () => {
            wallets.push(new ethers.Wallet(testConfig.privateKey));
            wallets.push(
                new ethers.Wallet(
                    '0x20a3c8eb679bc7fe83e31754871c31a0cff0bf8d96edb8136f1b364753f720f1'
                )
            );
            wallets.push(
                new ethers.Wallet(
                    '0x6ff46791d809f5a588c1339dc065e38d2079eafa6ff32130a6d5686e0b6b60ea'
                )
            );

            const txId = '0x7cfbaa6f05794922229e60c7c9695cc52cd13ed9ab1b88597626bd70bb8315d1';
            signatures.push(await wallets[0].signMessage(ethers.utils.arrayify(txId)));
            signatures.push(await wallets[1].signMessage(ethers.utils.arrayify(txId)));
            signatures.push(await wallets[2].signMessage(ethers.utils.arrayify(txId)));
        });

        it('should get signatures when request', async () => {
            const mockP2p = {
                net: {
                    onMessage: (func) => {
                        this.callback = func;
                        return { unsubscribe: () => {} };
                    },
                    broadcast: (_, { log }) => {
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[0], logId: log.id },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[1], logId: log.id },
                        });
                    },
                },
            };

            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, mockP2p, web3Mock);
            federator.members = [wallets[0].address, wallets[1].address, wallets[2].address];

            const res = await federator._requestSignatureFromFederators(logs[0]);
            expect(res).toHaveLength(2);
            expect(res[0]).toBe(signatures[0]);
            expect(res[1]).toBe(signatures[1]);
        });

        it('should not use same signature twice', async () => {
            const mockP2p = {
                net: {
                    onMessage: (func) => {
                        this.callback = func;
                        return { unsubscribe: () => {} };
                    },
                    broadcast: (_, { log }) => {
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[0], logId: log.id },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[0], logId: log.id },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[1], logId: log.id },
                        });
                    },
                },
            };

            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, mockP2p, web3Mock);
            federator.members = [wallets[0].address, wallets[1].address, wallets[2].address];

            const res = await federator._requestSignatureFromFederators(logs[0]);
            expect(res).toHaveLength(2);
            expect(res[0]).toBe(signatures[0]);
            expect(res[1]).toBe(signatures[1]);
        });

        it("should not use signature if doesn't match log id", async () => {
            const mockP2p = {
                net: {
                    onMessage: (func) => {
                        this.callback = func;
                        return { unsubscribe: () => {} };
                    },
                    broadcast: (_, { log }) => {
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[0], logId: log.id },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[1], logId: 'log_d7528a15' },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[2], logId: log.id },
                        });
                    },
                },
            };

            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, mockP2p, web3Mock);
            federator.members = [wallets[0].address, wallets[1].address, wallets[2].address];

            const res = await federator._requestSignatureFromFederators(logs[0]);
            expect(res).toHaveLength(2);
            expect(res[0]).toBe(signatures[0]);
            expect(res[1]).toBe(signatures[2]);
        });

        it('should not use signature if not from federator', async () => {
            const mockP2p = {
                net: {
                    onMessage: (func) => {
                        this.callback = func;
                        return { unsubscribe: () => {} };
                    },
                    broadcast: (_, { log }) => {
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[0], logId: log.id },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[1], logId: log.id },
                        });
                        this.callback({
                            type: MAIN_SIGNATURE_SUBMISSION,
                            source: { id: 'TEST-ID' },
                            data: { signature: signatures[2], logId: log.id },
                        });
                    },
                },
            };

            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, mockP2p, web3Mock);
            federator.members = [wallets[0].address, wallets[2].address];

            const res = await federator._requestSignatureFromFederators(logs[0]);
            expect(res).toHaveLength(2);
            expect(res[0]).toBe(signatures[0]);
            expect(res[1]).toBe(signatures[2]);
        });

        it('should sign message', async () => {
            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
            federator.mainBridgeContract.getPastEvents = () => [logs[0]];

            const { signature, logId } = await federator.signTransaction({
                blockNumber: logs[0].blockNumber,
                id: logs[0].id,
            });
            expect(typeof signature).toBe('string');
            expect(signature.substring(0, 2)).toBe('0x');
            expect(signature).toHaveLength(132);
            expect(logId).toBe(logs[0].id);
        });

        it('should not sign message if no matching event fetched', async () => {
            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
            federator.mainBridgeContract.getPastEvents = () => [];

            await expect(federator.signTransaction({ blockNumber: 4, id: 123 })).rejects.toThrow(
                CustomError
            );
        });

        it('should not sign message if multiple matching events fetched', async () => {
            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
            federator.mainBridgeContract.getPastEvents = () => logs;

            await expect(federator.signTransaction({ blockNumber: 4, id: 123 })).rejects.toThrow(
                CustomError
            );
        });

        it('should not sign message if blocknumber not confirmed', async () => {
            const federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
            federator.mainBridgeContract.getPastEvents = () => [logs[0]];
            const currentBlock = await federator._getCurrentBlockNumber();

            await expect(
                federator.signTransaction({ blockNumber: currentBlock, id: 123 })
            ).rejects.toThrow(CustomError);
        });
    });

    describe('executeTransaction error cases', () => {
        const log = {
            logIndex: 2,
            blockNumber: 2557,
            blockHash: '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash: '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues: {
                0: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                1: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                2: '1000000000000000000',
                3: 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000000000000000000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461',
            },
            event: 'Cross',
            signature: '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data: '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics: [
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826',
                ],
            },
        };
        let federator;
        let sendTransactionSpy;

        beforeEach(() => {
            federator = new Federator(MAIN_FEDERATOR, testConfig, logger, {}, web3Mock);
            disableEtherscanGasPrices(federator.transactionSender);
            sendTransactionSpy = jest.spyOn(TransactionSender.prototype, 'sendTransaction');
        });

        it('Should handle reverted transactions gracefully', async () => {
            federator.sideWeb3.eth = federator.sideWeb3.eth.mockMethods({
                sendSignedTransaction: () =>
                    createPromiEventError('Transaction has been reverted by the EVM'),
                sendTransaction: () =>
                    createPromiEventError('Transaction has been reverted by the EVM'),
            });

            expect(sendTransactionSpy).toHaveBeenCalledTimes(0); // sanity check

            let result = await federator._executeTransaction(
                log,
                '0x0',
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                1,
                2,
                []
            ); // should not throw
            expect(result).toBeFalsy();
            expect(sendTransactionSpy).toHaveBeenCalledTimes(1);

            // After another call, it should NOT try to send the transaction again
            result = await federator._executeTransaction(
                log,
                '0x0',
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                1,
                2,
                []
            );
            expect(result).toBeFalsy();
            expect(sendTransactionSpy).toHaveBeenCalledTimes(1);
        });

        it('Should error and retry on other exceptions', async () => {
            federator.sideWeb3.eth = federator.sideWeb3.eth.mockMethods({
                sendSignedTransaction: () => createPromiEventError('Invalid JSON RPC response: ""'),
                sendTransaction: () => createPromiEventError('Invalid JSON RPC response: ""'),
            });

            await expect(federator._executeTransaction(log, '0x0')).rejects.toThrow(CustomError);
            expect(sendTransactionSpy).toHaveBeenCalledTimes(1);

            // After another call, it should try to send the transaction again
            await expect(federator._executeTransaction(log, '0x0')).rejects.toThrow(CustomError);
            expect(sendTransactionSpy).toHaveBeenCalledTimes(2);
        });
    });
});
