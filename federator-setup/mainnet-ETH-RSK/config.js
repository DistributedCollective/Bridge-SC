const fs = require('fs');
let telegramToken;
try {
    telegramToken = fs.readFileSync(`${__dirname}/telegram.key`, 'utf8').trim();
} catch(e) {
    console.debug(`Cannot load telegram token from ${__dirname}/telegram.key, bot disabled`);
    telegramToken = '';
}
module.exports = {
    mainchain: require('./rskmainnet.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./mainnet.json'), //the json containing the smart contract addresses in eth
    runEvery: 2, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    storagePath: './db',
    federatorInstanceId: 'federatorInstanceId_replace_this',
	telegramBot: {
		token: telegramToken,
        groupId: -543088999,
    },
    confirmationTable: {
        "1": {
            "default": 400,
            "minConfirmation": 10,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1,
                    "confirmations": 30
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1,
                    "confirmations": 30
                },
                {
                    "amount": 5,
                    "confirmations": 60
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
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1,
                    "confirmations": 4
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1,
                    "confirmations": 4
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
        },
        "30": {
            "default": 100,
            "minConfirmation": 10,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1,
                    "confirmations": 30
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 1,
                    "confirmations": 30
                },
                {
                    "amount": 5,
                    "confirmations": 60
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
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1,
                    "confirmations": 4
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1,
                    "confirmations": 4
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
          },
	    "97": {
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
            "USDT": [
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
            "default": 4,
            "minConfirmation": 2,
            "DAI": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDC": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDT": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETH": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1,
                    "confirmations": 4
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
            "DAIes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDCes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
	        "USDTes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 2000,
                    "confirmations": 30
                },
                {
                    "amount": 10000,
                    "confirmations": 60
                }
            ],
            "ETHes": [
                {
                    "amount": 0,
                    "confirmations": 2
                },
                {
                    "amount": 1,
                    "confirmations": 4
                },
                {
                    "amount": 5,
                    "confirmations": 60
                }
            ],
        }
    }
}

