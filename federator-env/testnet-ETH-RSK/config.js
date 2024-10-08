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
} catch (e) {
    console.debug(
        `Cannot load Etherscan API key from ${__dirname}/etherscan.key, lower rate limits apply`
    );
    etherscanApiKey = '';
}

module.exports = {
    mainchain: require('./rsktestnet.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./sepolia.json'), //the json containing the smart contract addresses in eth
    gasApiRunEvery: 5, // In Seconds,
    avgGasRunEvery: 10, // In Seconds,
    periodAvgGas: 4, // In minutes,
    sleepOnGas: 2, // In Seconds
    maxSleepOnGas: 3, // Count
    minimumPeerAmount: 2,
    port: 30303,
    runEvery: 2, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    signaturesTTL: 24 * 60 * 60, // In seconds
    signatureRequestTimeoutMs: 2 * 60 * 1000, // In milliseconds
    storagePath: './db',
    ethGasPriceThresholdGwei: 10,
    federatorInstanceId: 'federatorInstanceId_replace_this',
    federatorAddress: 'federatorAddress_replace_this',
    etherscanApiKey: etherscanApiKey,
	telegramBot: {
		token: telegramToken,
		groupId: -572987924,
    },
	confirmationTable: {
        "1": {
            "default": 5760,
            "minConfirmation": 10,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "eSOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50,
                    "confirmations": 30
                },
                {
                    "amount": 500,
                    "confirmations": 50
                }
            ],
        },
        "3": {
            "default": 5,
            "minConfirmation": 5,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
            "eSOV": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 50,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 50,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                }
            ],
            "esETH": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 50,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                }
            ],
        },
        "30": {
            "default": 2880,
            "minConfirmation": 10,
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "DAIbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "USDCbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDTbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "SOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50,
                    "confirmations": 30
                },
                {
                    "amount": 500,
                    "confirmations": 50
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50,
                    "confirmations": 30
                },
                {
                    "amount": 500,
                    "confirmations": 50
                }
            ],
        },
        "31": {
            "default": 5,
            "minConfirmation": 5,
            "SEPUSDes": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
            "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
            "DAIbs": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
            "USDCbs": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
	        "USDTbs": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ],
            "SOV": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 50,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                }
            ],
            "esETH": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 50,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 50,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                }
            ],
          },
	    "97": {
               "default": 10,
               "minConfirmation": 10,
               "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "bSOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50,
                    "confirmations": 30
                },
                {
                    "amount": 500,
                    "confirmations": 50
                }
            ],
        },
        "56": {
            "default": 10,
            "minConfirmation": 10,
        "DAI": [
             {
                 "amount": 0,
                 "confirmations": 10
             },
             {
                 "amount": 500,
                 "confirmations": 30
             },
             {
                 "amount": 2500,
                 "confirmations": 50
             }
         ],
         "USDC": [
             {
                 "amount": 0,
                 "confirmations": 10
             },
             {
                 "amount": 500,
                 "confirmations": 30
             },
             {
                 "amount": 2500,
                 "confirmations": 50
             }
         ],
         "USDT": [
             {
                 "amount": 0,
                 "confirmations": 10
             },
             {
                 "amount": 500,
                 "confirmations": 30
             },
             {
                 "amount": 2500,
                 "confirmations": 50
             }
         ],
         "bSOV": [
             {
                 "amount": 0,
                 "confirmations": 10
             },
             {
                 "amount": 50,
                 "confirmations": 30
             },
             {
                 "amount": 500,
                 "confirmations": 50
             }
         ],
        },
        "42": {
            "default": 10,
            "minConfirmation": 10,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 500,
                    "confirmations": 30
                },
                {
                    "amount": 2500,
                    "confirmations": 50
                }
            ],
            "eSOV": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50,
                    "confirmations": 30
                },
                {
                    "amount": 500,
                    "confirmations": 50
                }
            ],
        },
        "11155111": {
            "default": 5,
            "minConfirmation": 5,
            "SEPUSD": [
                {
                    "amount": 0,
                    "confirmations": 5
                },
                {
                    "amount": 500,
                    "confirmations": 5
                },
                {
                    "amount": 2500,
                    "confirmations": 5
                }
            ]
        }
    }
}
