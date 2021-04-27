const fs = require('fs');
let telegramToken;
try {
    telegramToken = fs.readFileSync(`${__dirname}/telegram.key`, 'utf8').trim();
} catch(e) {
    console.debug(`Cannot load telegram token from ${__dirname}/telegram.key, bot disabled`);
    telegramToken = '';
}
module.exports = {
    mainchain: require('./rsktestnet.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./ropsten.json'), //the json containing the smart contract addresses in eth
    runEvery: 2, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    storagePath: './db',
    federatorInstanceId: 'federatorInstanceId_replace_this',
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
            "eSOV": [
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
            "eSOV": [
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
            "DAIbs": [
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
            "USDCbs": [
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
	        "USDTbs": [
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
            "SOV": [
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
            "DAIbs": [
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
            "USDCbs": [
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
	        "USDTbs": [
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
            "SOV": [
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
            "bSOV": [
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
        "56": {
            "default": 10,
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
         "bSOV": [
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
            "eSOV": [
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