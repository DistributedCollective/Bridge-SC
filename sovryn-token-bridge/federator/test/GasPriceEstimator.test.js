const EtherscanGasPriceEstimator = require("../src/lib/GasPriceEstimator");
const CustomError = require("../src/lib/CustomError");
const EventEmitter = require('events');
const https = require('https');

const fauxLogger = {
    debug: () => {},
    info: () => {},
    log: () => {},
    warn: (...args) => console.log(...args ),
    error: (...args) => console.error(...args ),
}
describe('GasPriceEstimator', () => {
    let estimator;
    let estimatorWithoutApiKey;
    let web3Mock;
    let mockedGasPrice = 0;
    let mockedBlockMinimumGasPrice = 0;
    let _savedHttpsGet;
    let _savedDateNow;

    beforeEach(() => {
        _savedHttpsGet = https.get;
        _savedDateNow = Date.now;
        jest.clearAllMocks();

        web3Mock = {
            eth: {
                getGasPrice: () => mockedGasPrice,
                getBlock: () => ({
                    minimumGasPrice: mockedBlockMinimumGasPrice,
                })
            }
        }
        estimator = new EtherscanGasPriceEstimator({
            web3: web3Mock,
            etherscanApiKey: 'f00',
            etherscanApiBaseUrl: 'https://example.invalid/api',
            etherscanChainId: 1,
            logger: fauxLogger,
        });
        estimatorWithoutApiKey = new EtherscanGasPriceEstimator({
            web3: web3Mock,
            etherscanApiBaseUrl: 'https://example.invalid/api',
            etherscanChainId: 1,
            logger: fauxLogger,
        });
    });

    afterEach(() => {
        https.get = _savedHttpsGet;
        Date.now = _savedDateNow;
    })

    const mockWeb3GasPrice = (gasPriceGwei) => {
        mockedGasPrice = gasPriceGwei * 1000000000;
    }

    const mockWeb3BlockMinimumGasPrice = (gasPriceGwei) => {
        mockedBlockMinimumGasPrice = gasPriceGwei * 1000000000;
    }

    const mockHttpsGet = ({
        statusCode,
        responseJson,
        expectedUrl,
    }) => {

        https.get = jest.fn().mockImplementation((url, callback) => {
            if (expectedUrl) {
                expect(url).toEqual(expectedUrl);
            }
            const emitter = new EventEmitter();
            emitter.statusCode = statusCode;
            emitter.setEncoding = () => {};
            emitter.resume = () => {};

            setTimeout(() => {
                emitter.emit('data', JSON.stringify(responseJson));
                emitter.emit('end');
            }, 1);
            callback(emitter);
            return {
                on: () => {},
            }
        });
        return https.get;
    }

    const mockDateNow = (value) => {
        Date.now = jest.fn().mockReturnValue(value);
    }

    describe('#getGasPrice', function () {
        it('uses propose gas price with buffer if web3 gas price and fast gas price are smaller', async () => {
            mockWeb3GasPrice(10);
            mockHttpsGet({
                expectedUrl: 'https://example.invalid/api?module=gastracker&action=gasoracle&apikey=f00',
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "24"
                    }
                }
            })
            const gasPrice = await estimator.getGasPrice(1);
            // 20 * 1.25 > 24 so we use that
            expect(gasPrice).toEqual(20 * 1.25 * 1000000000);
        });

        it('uses fast gas price with buffer if web3 gas price and propose gas price (with buffer) are smaller', async () => {
            mockWeb3GasPrice(10);
            mockHttpsGet({
                expectedUrl: 'https://example.invalid/api?module=gastracker&action=gasoracle&apikey=f00',
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "27"
                    }
                }
            })
            const gasPrice = await estimator.getGasPrice(1);
            // 20 * 1.25 > 24 so we use that
            expect(gasPrice).toEqual(27 * 1000000000);
        });

        it('uses average of web3 and propose gas price if web3 gas price is greater', async () => {
            mockWeb3GasPrice(30);
            mockHttpsGet({
                expectedUrl: 'https://example.invalid/api?module=gastracker&action=gasoracle&apikey=f00',
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "24"
                    }
                }
            })
            const gasPrice = await estimator.getGasPrice(1);
            expect(gasPrice).toEqual((20 + 30) / 2 * 1000000000);
        });

        it('gets gas price without api key', async () => {
            mockWeb3GasPrice(22);
            mockHttpsGet({
                expectedUrl: 'https://example.invalid/api?module=gastracker&action=gasoracle',
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK-Missing/Invalid API Key, rate limit of 1/5sec applied",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "24"
                    }
                }
            })
            const gasPrice = await estimatorWithoutApiKey.getGasPrice(1);
            expect(gasPrice).toEqual(21 * 1000000000);
        });

        it('uses rsk gas price for rsk chains', async () => {
            mockWeb3BlockMinimumGasPrice(11);
            mockHttpsGet({
                expectedUrl: 'https://example.invalid/api?module=gastracker&action=gasoracle',
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK-Missing/Invalid API Key, rate limit of 1/5sec applied",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "24"
                    }
                }
            })
            for (let chainId of [30, 31]) {
                const gasPrice = await estimatorWithoutApiKey.getGasPrice(chainId);
                expect(gasPrice).toEqual(11 * 1.05 * 1000000000);
            }
        });

        it('gets gas price for non-mainnet chain', async () => {
            mockWeb3GasPrice(10);
            mockHttpsGet({
                expectedUrl: 'https://example.invalid/api?module=gastracker&action=gasoracle&apikey=f00',
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "27"
                    }
                }
            })
            const gasPrice = await estimator.getGasPrice(2);
            // 20 * 1.25 > 24 so we use that
            expect(gasPrice).toEqual(10 * 1.5 * 1000000000);
        });

        it('uses cached gas price', async () => {
            mockWeb3GasPrice(22);
            const getMock = mockHttpsGet({
                statusCode: 200,
                responseJson: {
                    "status": "1",
                    "message": "OK",
                    "result": {
                        "LastBlock": "12564406",
                        "SafeGasPrice": "12",
                        "ProposeGasPrice": "20",
                        "FastGasPrice": "24"
                    }
                }
            })
            let gasPrice = await estimator.getGasPrice(1);
            expect(https.get.mock.calls.length).toBe(1);
            expect(gasPrice).toEqual(21 * 1000000000);
            gasPrice = await estimator.getGasPrice(1);
            expect(https.get.mock.calls.length).toBe(1); // cached
            expect(gasPrice).toEqual(21 * 1000000000);

            mockDateNow(Date.now() + estimator.cacheTimeMs + 10);
            gasPrice = await estimator.getGasPrice(1);
            expect(https.get.mock.calls.length).toBe(2); // new call
            expect(gasPrice).toEqual(21 * 1000000000);
        });

        it('uses fallback gas price on etherscan error', async () => {
            mockWeb3GasPrice(10);
            mockHttpsGet({
                statusCode: 200,
                responseJson: {
                    "status": "0",
                    "message": "NOTOK",
                }
            })
            const gasPrice = await estimator.getGasPrice(1);
            expect(gasPrice).toEqual(15 * 1000000000);
        });

        it('uses fallback gas price on etherscan error', async () => {
            mockWeb3GasPrice(10);
            mockHttpsGet({
                statusCode: 400,
                responseJson: {
                    "what": "ever",
                }
            })
            const gasPrice = await estimator.getGasPrice(1);
            expect(gasPrice).toEqual(15 * 1000000000);
        });
    });

    describe('#getEthersanGasPrices', () => {
        it('errors on etherscan error', async () => {
            mockHttpsGet({
                statusCode: 200,
                responseJson: {
                    "status": "0",
                    "message": "NOTOK",
                }
            })
            await expect(estimator.getEtherscanGasPrices(1)).rejects.toThrow(CustomError);
        });

        it('errors on invalid HTTP status', async () => {
            mockHttpsGet({
                statusCode: 400,
                responseJson: {
                    "what": "ever",
                }
            })
            await expect(estimator.getEtherscanGasPrices()).rejects.toThrow(CustomError);
        });
    });

    describe('default cacheTimeMs', () => {
        it('is enough for 1 request / 200 ms if api key is given', () => {
            expect(estimator.cacheTimeMs).toEqual(200);
        });

        it('is enough for 1 request / 5 s if api key is NOT given', () => {
            expect(estimatorWithoutApiKey.cacheTimeMs).toEqual(5000);
        });
    })

});