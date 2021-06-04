const EtherscanGasPriceEstimator = require("../src/lib/EtherscanGasPriceEstimator");
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
describe('EtherscanGasPriceestimator', () => {
    let estimator;
    let estimatorWithoutApiKey;
    let _savedHttpsGet;
    let _savedDateNow;

    beforeEach(() => {
        _savedHttpsGet = https.get;
        _savedDateNow = Date.now;
        jest.clearAllMocks();
        estimator = new EtherscanGasPriceEstimator({
            apiKey: 'f00',
            apiBaseUrl: 'https://example.invalid/api',
            chainId: 1,
            logger: fauxLogger,
        });
        estimatorWithoutApiKey = new EtherscanGasPriceEstimator({
            apiBaseUrl: 'https://example.invalid/api',
            chainId: 1,
            logger: fauxLogger,
        });
    });

    afterEach(() => {
        https.get = _savedHttpsGet;
        Date.now = _savedDateNow;
    })

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
        it('gets gas price', async () => {
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
            const gasPrice = await estimator.getGasPrice();
            expect(gasPrice).toEqual(20 * 1000000000);
        });

        it('gets gas price without api key', async () => {
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
            const gasPrice = await estimatorWithoutApiKey.getGasPrice();
            expect(gasPrice).toEqual(20 * 1000000000);
        });

        it('uses cached gas price', async () => {
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
            let gasPrice = await estimator.getGasPrice();
            expect(https.get.mock.calls.length).toBe(1);
            expect(gasPrice).toEqual(20 * 1000000000);
            gasPrice = await estimator.getGasPrice();
            expect(https.get.mock.calls.length).toBe(1); // cached
            expect(gasPrice).toEqual(20 * 1000000000);

            mockDateNow(Date.now() + estimator.cacheTimeMs + 10);
            gasPrice = await estimator.getGasPrice();
            expect(https.get.mock.calls.length).toBe(2); // new call
            expect(gasPrice).toEqual(20 * 1000000000);
        });

        it('errors on etherscan error', async () => {
            mockHttpsGet({
                statusCode: 200,
                responseJson: {
                    "status": "0",
                    "message": "NOTOK",
                }
            })
            await expect(estimator.getGasPrice()).rejects.toThrow(CustomError);
        });

        it('errors on invalid HTTP status', async () => {
            mockHttpsGet({
                statusCode: 400,
                responseJson: {
                    "what": "ever",
                }
            })
            await expect(estimator.getGasPrice()).rejects.toThrow(CustomError);
        });
    });

    describe('#isEnabledForChain', () => {
        it('is enabled for configured chain', () => {
            expect(estimator.isEnabledForChain(1)).toBeTruthy();
        });

        it('is not enabled for other chains', () => {
            expect(estimator.isEnabledForChain(2)).toBeFalsy();
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