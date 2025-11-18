const fs = require('fs');
let telegramToken;
try {
    telegramToken = fs.readFileSync(`${__dirname}/telegram.key`, 'utf8').trim();
} catch(e) {
    console.debug(`Cannot load telegram token from ${__dirname}/telegram.key, bot disabled`);
    telegramToken = '';
}
let etherscanApiKey;
try {
    etherscanApiKey = fs.readFileSync(`${__dirname}/etherscan.key`, 'utf8').trim();
} catch(e) {
    console.debug(`Cannot load Etherscan API key from ${__dirname}/etherscan.key, lower rate limits apply`);
    etherscanApiKey = '';
}

module.exports = {
    mainchain: require('./rskmainnet.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./mainnet.json'), //the json containing the smart contract addresses in eth
    runEvery: 2, // In minutes,
    gasApiRunEvery: 5, // In Seconds,
    avgGasRunEvery: 10, // In Seconds,
    periodAvgGas: 240, // In minutes,
    sleepOnGas: 10, // In Seconds
    maxSleepOnGas: 9, // Count
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    storagePath: './db',
    minimumPeerAmount: 2,
    port: 30303,
    signaturesTTL: 24 * 60 * 60, // In seconds
    signatureRequestTimeoutMs: 2 * 60 * 1000, // In milliseconds
    ethGasPriceThresholdGwei: 10,
    federatorInstanceId: 'federatorInstanceId_replace_this',
    federatorAddress: 'federatorAddress_replace_this',
    etherscanApiKey: etherscanApiKey,
	telegramBot: {
		token: telegramToken,
        groupId: -543088999,
    },
    confirmationTable: {
        "1": {
            "default": 400,
            "minConfirmation": 10,
            "SOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 500000000000000000000,
                    "confirmations": 50
                }
            ],
            "eSOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 500000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "eDLLR": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "DLLR": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
            "BOS": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
            "BOSes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
        },
        "3": {
            "default": 4,
            "minConfirmation": 2,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 4
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 4
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 50
                }
            ],
        },
        "30": {
            "default": 100,
            "minConfirmation": 10,
            "SOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 500000000000000000000,
                    "confirmations": 50
                }
            ],
            "eSOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 500000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "eDLLR": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "DLLR": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
            "BOS": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
            "BOSes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 10000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 100000000000000000000,
                    "confirmations": 50
                }
            ],
        },
        "31": {
            "default": 4,
            "minConfirmation": 2,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 4
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 4
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 50
                }
            ],
          },
	    "97": {
               "default": 10,
               "minConfirmation": 10,
        },    
        "42": {
            "default": 4,
            "minConfirmation": 2,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 4
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 10000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 4
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 50
                }
            ],
        }
    }
}

