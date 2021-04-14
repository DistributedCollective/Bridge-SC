const fs = require('fs');
module.exports = {
    mainchain: require('./rskmainnet.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./mainnet.json'), //the json containing the smart contract addresses in eth
    runEvery: 2, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    storagePath: './db',
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
                    "amount": 0.2,
                    "confirmations": 30
                },
                {
                    "amount": 0.5,
                    "confirmations": 50
                }
            ],
	        "USDC": [
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
            "DAIes": [
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
            "USDCes": [
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
	        "USDTes": [
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
            "USDC": [
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

