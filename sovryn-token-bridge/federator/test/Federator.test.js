const fs = require('fs');
const path = require('path');

const Web3PromiEvent = require('web3-core-promievent');

const Federator = require('../src/lib/Federator');
const TransactionSender = require('../src/lib/TransactionSender');
const CustomError = require('../src/lib/CustomError');
const eth = require('./web3Mock/eth.js');
const web3Mock = require('./web3Mock');
const {ConfirmationTableReader} = require('../src/helpers/ConfirmationTableReader');

const configFile = fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8');
const config = JSON.parse(configFile);

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

function mockFederatorMethods(federator, methods) {
    federator.mainWeb3.eth = federator.mainWeb3.eth.mockMethods(methods);
}

function cleanUpTestPaths() {
    if(fs.existsSync(testPath)) {
        fs.unlinkSync(testPath);
    }
    if(fs.existsSync(testFailingTxIdsPath)) {
        fs.unlinkSync(testFailingTxIdsPath);
    }
}

function createPromiEventError(message) {
    const promiEvent = Web3PromiEvent();
    setTimeout(() => {
        promiEvent.reject(new Error(message));

    }, 10)
    return promiEvent.eventEmitter;
}

describe('Federator module tests', () => {
    beforeEach(async function () {
        jest.clearAllMocks();
        cleanUpTestPaths();
    });

    afterEach(() => {
        cleanUpTestPaths();
    });

    it('Runs the main federator process sucessfully', async () => {
        let federator = new Federator(testConfig, logger, web3Mock);
        let result = await federator.run();

        expect(result).toBeTruthy();
    });

    it('Runs the main federator process with pagination', async () => {
        const expectedConfirmations = 5760;
        const twoPages = 2002;
        const currentBlock = testConfig.mainchain.fromBlock + twoPages + expectedConfirmations;
        const federator = new Federator(testConfig, logger, web3Mock);
        mockFederatorMethods(federator, {
            getBlockNumber: () => Promise.resolve(currentBlock),
            getId: () => Promise.resolve(1)
        });
        const _processLogsSpy = jest.spyOn(federator, '_processLogs');

        let result = await federator.run();

        expect(result).toBeTruthy();
        let value = fs.readFileSync(testPath, 'utf8');
        expect(parseInt(value)).toEqual(currentBlock-expectedConfirmations);
        expect(_processLogsSpy).toHaveBeenCalledTimes(3);
    });

    it('Runs the main federator process with pagination limit', async () => {
        const expectedConfirmations = 5760;
        const onePage = 1001;
        const currentBlock = testConfig.mainchain.fromBlock + onePage + expectedConfirmations;
        const federator = new Federator(testConfig, logger, web3Mock);
        mockFederatorMethods(federator, {
            getBlockNumber: () => Promise.resolve(currentBlock),
            getId: () => Promise.resolve(1)
        });
        federator.mainWeb3.eth.getBlockNumber = () => Promise.resolve(currentBlock);
        federator.mainWeb3.eth.net.getId = () => Promise.resolve(1);
        const _processLogsSpy = jest.spyOn(federator, '_processLogs');

        let result = await federator.run();

        expect(result).toBeTruthy();
        let value = fs.readFileSync(testPath, 'utf8');
        expect(parseInt(value)).toEqual(currentBlock-expectedConfirmations);
        expect(_processLogsSpy).toHaveBeenCalledTimes(1);
    });

    it('Saves the progress in a file path', async () => {
        let federator = new Federator(testConfig, logger, web3Mock);

        federator._saveProgress(testPath, 'test');

        expect(fs.existsSync(testPath)).toBeTruthy();

        let value = fs.readFileSync(testPath, 'utf8');
        expect(value).toEqual('test');
    });

    it('Should no vote for empty log and receiver', async () => {
        eth.sendSignedTransaction = jest.fn().mockImplementation(() => { throw new Error("Some Error") });

        let federator = new Federator(testConfig, logger, web3Mock);
        try{
            await federator._voteTransaction(null, null);
            expect(false).toBeTruthy();
        } catch (err) {
            expect(err).not.toBeNull();
        }
        expect(fs.existsSync(testPath)).toBeFalsy();
    })

    it('Votes a transaction from a log entry', async () => {
        let federator = new Federator(testConfig, logger, web3Mock);
        let log = {
            logIndex: 2,
            blockNumber: 2557,
            blockHash:
                '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash:
                '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues:{
                '0': '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                '1': '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                '2': '1000000000000000000',
                '3': 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000000000000000000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461'
            },
            event: 'Cross',
            signature:
                '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data:
                    '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics:[
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826'
                ]
            }
        }

        let result = await federator._voteTransaction(log, '0x0');
        expect(result).toBeTruthy();
    });

    it('Should return undefined for a list of 1 confirmed log', async () => {
        let federator = new Federator(testConfig, logger, web3Mock);
        let logs = [{
            logIndex: 2,
            blockNumber: 10000,
            blockHash:
                '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash:
                '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues:{
                '0': '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                '1': '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                '2': '1000000000000000000',
                '3': 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '50',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461'
            },
            event: 'Cross',
            signature:
                '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data:
                    '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics:[
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826'
                ]
            }
        }]
        const ctr = new ConfirmationTableReader(3, testConfig.confirmationTable);

        let result = await federator._processLogs(ctr, logs);
        expect(result).toBeUndefined();
    });

    it('Should return the logBlockNumber for a list of 1 unconfirmed log', async () => {
        let federator = new Federator(testConfig, logger, web3Mock);
        const logBlockNumber = 2683000;
        let logs = [{
            logIndex: 2,
            blockNumber: logBlockNumber,
            blockHash:
                '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash:
                '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues:{
                '0': '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                '1': '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                '2': '1000000000000000000',
                '3': 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000000000000000000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461'
            },
            event: 'Cross',
            signature:
                '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data:
                    '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics:[
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826'
                ]
            }
        }]
        const ctr = new ConfirmationTableReader(3, testConfig.confirmationTable);

        let result = await federator._processLogs(ctr, logs);
        expect(result).toEqual(logBlockNumber - 1);
    });


    it('Should return the second logBlockNumber for a list of 2 log, only first confirmed', async () => {
        let federator = new Federator(testConfig, logger, web3Mock);
        const firstLogBlockNumber = 15000;
        const currentBlockNumber = 42000;
        const ctr = new ConfirmationTableReader(3, testConfig.confirmationTable);
        const secondLogBlockNumber = currentBlockNumber-ctr.getMinConfirmation();

        let logs = [{
            logIndex: 2,
            blockNumber: firstLogBlockNumber,
            blockHash:
                '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash:
                '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues:{
                '0': '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                '1': '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                '2': '1000000000000000000',
                '3': 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461'
            },
            event: 'Cross',
            signature:
                '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data:
                    '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics:[
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826'
                ]
            }
        }, {
            logIndex: 3,
            blockNumber: secondLogBlockNumber,
            blockHash:
                '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash:
                '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues:{
                '0': '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                '1': '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                '2': '1000000000000000000',
                '3': 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461'
            },
            event: 'Cross',
            signature:
                '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data:
                    '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics:[
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826'
                ]
            }
        }]

        let result = await federator._processLogs(ctr, logs);
        expect(result).toEqual(secondLogBlockNumber - 1);
    });

    describe('voteTransaction error cases', () => {
        const log = {
            logIndex: 2,
            blockNumber: 2557,
            blockHash:
                '0x5d3752d14223348e0df325ea0c3bd62f76195127762621314ff5788ccae87a7a',
            transactionHash:
                '0x79fcac96ebe7642c3258143f91a94be443e0dfc214199372542df940670166a6',
            transactionIndex: 0,
            address: '0x1eD614cd3443EFd9c70F04b6d777aed947A4b0c4',
            id: 'log_a755a817',
            returnValues:{
                '0': '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                '1': '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                '2': '1000000000000000000',
                '3': 'MAIN',
                _tokenAddress: '0x5159345aaB821172e795d56274D0f5FDFdC6aBD9',
                _to: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826',
                _amount: '1000000000000000000',
                _symbol: 'MAIN',
                _userData: '0x45787472612064617461'
            },
            event: 'Cross',
            signature:
                '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
            raw: {
                data:
                    '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000044d41494e00000000000000000000000000000000000000000000000000000000',
                topics:[
                    '0x958c783f2c825ef71ab3305ab602850535bb04833f5963c7a39a82a390642d47',
                    '0x0000000000000000000000005159345aab821172e795d56274d0f5fdfdc6abd9',
                    '0x000000000000000000000000cd2a3d9f938e13cd947ec05abc7fe734df8dd826'
                ]
            }
        };
        let federator;
        let sendTransactionSpy;

        beforeEach(() => {
            federator = new Federator(testConfig, logger, web3Mock);
            sendTransactionSpy = jest.spyOn(TransactionSender.prototype, 'sendTransaction');
        })

        it('Should handle reverted transactions gracefully', async () => {
            federator.sideWeb3.eth = federator.sideWeb3.eth.mockMethods({
                sendSignedTransaction: () => createPromiEventError('Transaction has been reverted by the EVM'),
                sendTransaction: () => createPromiEventError('Transaction has been reverted by the EVM'),
            });

            expect(sendTransactionSpy).toHaveBeenCalledTimes(0); // sanity check

            let result = await federator._voteTransaction(log, '0x0'); // should not throw
            expect(result).toBeFalsy();
            expect(sendTransactionSpy).toHaveBeenCalledTimes(1);

            // After another call, it should NOT try to send the transaction again
            result = await federator._voteTransaction(log, '0x0');
            expect(result).toBeFalsy();
            expect(sendTransactionSpy).toHaveBeenCalledTimes(1);
        });

        it('Should error and retry on other exceptions', async () => {
            federator.sideWeb3.eth = federator.sideWeb3.eth.mockMethods({
                sendSignedTransaction: () => createPromiEventError('Invalid JSON RPC response: ""'),
                sendTransaction: () => createPromiEventError('Invalid JSON RPC response: ""')
            });

            await expect(federator._voteTransaction(log, '0x0')).rejects.toThrow(CustomError);
            expect(sendTransactionSpy).toHaveBeenCalledTimes(1);

            // After another call, it should try to send the transaction again
            await expect(federator._voteTransaction(log, '0x0')).rejects.toThrow(CustomError);
            expect(sendTransactionSpy).toHaveBeenCalledTimes(2);
        });
    });
})
