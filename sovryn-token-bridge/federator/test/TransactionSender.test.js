const fs = require('fs');
const path = require('path');
var globals = require('../src/lib/Globals');
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
var web3Mock = jest.fn();

const disableEtherscanGasPrices = (sender) => {
    sender.gasPriceEstimator.getGasPrice = jest.fn().mockRejectedValue(
        new Error('expected etherscan error')
    );
}

describe('TransactionSender module tests', () => {
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

    it('should get Gas Price from Globals', async () => {
        const from = "0x12D90403733b6DD1f88240C773a6613331e60bCF";
        const to = "0xD8bc75a79f6d63fE6E1307139d3BfDc0Bd090e35";
        const data = "0xfff";
        const value = "0x00f";
        const pk = "0xaaf";

        globals.currentEthGasBasePrice = 95;
        globals.currentEthGasPriceAvg = 98;
        let expected = '213';
        let expectedGas = '70000';
        web3Mock.eth.getTransactionCount = jest.fn().mockReturnValue(Promise.resolve(expected));
        web3Mock.eth.estimateGas = jest.fn().mockReturnValue(Promise.resolve(expectedGas));

        const sender = new TransactionSender(web3Mock, logger, config, '4');
        const rawTx =  await sender.createRawTransaction(from, to, data, value, pk);
        const result = sender.numberToHexString(rawTx.maxFeePerGas);
        let expectedmaxFeePerGas = sender.numberToHexString(( 95 + 2 ) * 1.3 * 1000000000);
        expect(result).toEqual(expectedmaxFeePerGas);
    });

    it('should throw custom Error for too low currentGasPrice', async () => {
        const from = "0x12D90403733b6DD1f88240C773a6613331e60bCF";
        const to = "0xD8bc75a79f6d63fE6E1307139d3BfDc0Bd090e35";
        const data = "0xfff";
        const value = "0x00f";
        const pk = "0xaaf";

        globals.currentEthGasBasePrice = 100;
        globals.currentEthGasPriceAvg = 98;
        let expected = '213';
        let expectedGas = '70000';
        web3Mock.eth.getTransactionCount = jest.fn().mockReturnValue(Promise.resolve(expected));
        web3Mock.eth.estimateGas = jest.fn().mockReturnValue(Promise.resolve(expectedGas));

        const sender = new TransactionSender(web3Mock, logger, config, '4');
        await expect(sender.createRawTransaction(from, to, data, value, pk)).rejects.toThrow(CustomError);
    });

    it('should getGasPrice Rsk', async () => {
        let gasPrice = 111;
        web3Mock.eth.getBlock = jest.fn().mockReturnValue(Promise.resolve({minimumGasPrice: gasPrice}));
        let sender = new TransactionSender(web3Mock, logger, {}, '31');
        let result = await sender.getGasPrice(31); //Rsk Testnet 
        expect(result).toEqual(Math.round(gasPrice*1.05));
        result = await sender.getGasPrice(30); //Rsk mainnet
        expect(result).toEqual(Math.round(gasPrice*1.05));

        web3Mock.eth.getBlock = jest.fn().mockReturnValue(Promise.resolve({minimumGasPrice: 0}));
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

        web3Mock.eth.getAccounts = jest.fn().mockReturnValue(Promise.resolve([expectedAddr.toLocaleLowerCase()]));
        sender = new TransactionSender(web3Mock, logger, {}, '');
        result = await sender.getAddress('');
        expect(result).toEqual(expectedAddr.toLocaleLowerCase());
        result = await sender.getAddress(undefined);
        expect(result).toEqual(expectedAddr.toLocaleLowerCase());
    });

});