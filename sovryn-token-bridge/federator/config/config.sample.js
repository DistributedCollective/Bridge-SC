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
    mainchain: require('./rsktestnet-kovan.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./kovan.json'), //the json containing the smart contract addresses in eth
    runEvery: 2, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    storagePath: './db',
    federatorInstanceId: '',
    etherscanApiKey: etherscanApiKey,
    enableEtherscanGasPriceEstimator: false, // set to true to enable estimator for sidechain
    telegramBot: {
        token: telegramToken,
        groupId: 0, // Telegram group id to send the messages to
    },
    confirmationTable: {
        "1": {
            "default": 5760,
            "minConfirmation": 10,
            "WETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "WBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "renBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
        },
        "3": {
            "default": 5760,
            "minConfirmation": 10,
            "WETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "WBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "renBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
        },
        "30": {
            "default": 2880,
            "minConfirmation": 10,
            "WETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "WBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "renBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
        },
        "31": {
            "default": 10,
            "minConfirmation": 10,
            "WETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "WBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "renBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
        },
        "42": {
            "default": 10,
            "minConfirmation": 10,
            "WETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "WBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50,
                    "confirmations": 30
                },
                {
                    "amount": 100,
                    "confirmations": 50
                }
            ],
            "renBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
        }
    }
}
