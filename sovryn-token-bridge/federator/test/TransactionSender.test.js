const fs = require('fs');
const path = require('path');
var globals = require('../src/lib/globals');
const CustomError = require('../src/lib/CustomError');
const TransactionSender = require('../src/lib/TransactionSender');

const configFile = fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8');
const config = JSON.parse(configFile);

const logger = {
    trace: jest.fn(),
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
};

const from = '0x12D90403733b6DD1f88240C773a6613331e60bCF';
const to = '0xD8bc75a79f6d63fE6E1307139d3BfDc0Bd090e35';
const data = '0xfff';
const value = '0x00f';

describe('TransactionSender module tests', () => {
    let web3Mock = jest.fn();

    beforeEach(async function () {
        jest.clearAllMocks();
        web3Mock.eth = jest.fn();
    });

    it('should getNonce', async () => {
        let expected = '213';
        web3Mock.eth.getTransactionCount = jest.fn().mockReturnValue(Promise.resolve(expected));
        let sender = new TransactionSender(web3Mock, logger, {}, '4');
        let result = await sender.getNonce();
        expect(result).toEqual(expected);
    });

    it('should get gas price for ethereum network', async () => {
        globals.currentEthGasBasePrice = 95;
        globals.currentEthGasPriceAvg = 98;
        web3Mock.eth.getTransactionCount = jest.fn().mockReturnValue(Promise.resolve('213'));
        web3Mock.eth.estimateGas = jest.fn().mockReturnValue(Promise.resolve('70000'));

        const sender = new TransactionSender(web3Mock, logger, config, '4');
        const rawTx = await sender.createRawTransaction(from, to, data, value);
        const result = sender.numberToHexString(rawTx.maxFeePerGas);
        // Formula from TransactionSender.createETHRawTransaction
        const expectedmaxFeePerGas = sender.numberToHexString((95 + 2) * 1.3 * 1000000000);
        expect(result).toEqual(expectedmaxFeePerGas);
    });

    it('should throw custom error for too low currentGasPrice', async () => {
        globals.currentEthGasBasePrice = 100;
        globals.currentEthGasPriceAvg = 98;
        web3Mock.eth.getTransactionCount = jest.fn().mockReturnValue(Promise.resolve('213'));
        web3Mock.eth.estimateGas = jest.fn().mockReturnValue(Promise.resolve('70000'));

        const configNoSleep = { ...config, sleepOnGas: 0 };

        const sender = new TransactionSender(web3Mock, logger, configNoSleep, '4');
        await expect(sender.createRawTransaction(from, to, data, value)).rejects.toThrow(
            CustomError
        );
    });

    it('should operate normally if the base price lower than the threshold and too low currentGasPrice', async () => {
        globals.currentEthGasBasePrice = 100;
        globals.currentEthGasPriceAvg = 98;
        web3Mock.eth.getTransactionCount = jest.fn().mockReturnValue(Promise.resolve('213'));
        web3Mock.eth.estimateGas = jest.fn().mockReturnValue(Promise.resolve('70000'));

        const alteredConfig = { ...config, sleepOnGas: 0, ethGasPriceThresholdGwei: 150 };

        const sender = new TransactionSender(web3Mock, logger, alteredConfig, '4');
        const rawTx = await sender.createRawTransaction(from, to, data, value);
        const result = sender.numberToHexString(rawTx.maxFeePerGas);
        const expectedmaxFeePerGas = sender.numberToHexString((globals.currentEthGasBasePrice + 2) * 1.3 * 1000000000);
        expect(result).toEqual(expectedmaxFeePerGas);
    });

    it('should getGasPrice Rsk', async () => {
        const gasPrice = 111;
        web3Mock.eth.getBlock = jest
            .fn()
            .mockReturnValue(Promise.resolve({ minimumGasPrice: gasPrice }));
        let sender = new TransactionSender(web3Mock, logger, {}, '31');
        let result = await sender.getGasPrice(31); //Rsk Testnet
        // Formula from GasPriceEstimator.getGasPrice
        expect(result).toEqual(Math.round(gasPrice * 1.05));
        result = await sender.getGasPrice(30); //Rsk mainnet
        expect(result).toEqual(Math.round(gasPrice * 1.05));

        web3Mock.eth.getBlock = jest.fn().mockReturnValue(Promise.resolve({ minimumGasPrice: 0 }));
        sender = new TransactionSender(web3Mock, logger, {}, '31');
        result = await sender.getGasPrice(30);
        expect(result).toEqual(Math.round(1));
    });

    it('should getAddress From privateKey', async () => {
        const pk = '3f28f888373e9ad1651a1227a5efdc0d7ea55bce6de3b5448de56c8588c6bd4d';
        const expectedAddr = '0x3444f14CbC7081ADEd7203E32E65304D17fe3bdA';
        let sender = new TransactionSender(web3Mock, logger, {}, '');
        let result = await sender.getAddress(pk); //Rsk Testnet
        expect(result).toEqual(expectedAddr.toLocaleLowerCase());

        web3Mock.eth.getAccounts = jest
            .fn()
            .mockReturnValue(Promise.resolve([expectedAddr.toLocaleLowerCase()]));
        sender = new TransactionSender(web3Mock, logger, {}, '');
        result = await sender.getAddress('');
        expect(result).toEqual(expectedAddr.toLocaleLowerCase());
        result = await sender.getAddress(undefined);
        expect(result).toEqual(expectedAddr.toLocaleLowerCase());
    });
});
