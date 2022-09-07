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
    sidechain: require('./bmainnet.json'), //the json containing the smart contract addresses in eth
    runEvery: 2, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/federator.key`, 'utf8').trim(),
    storagePath: './db',
    minimumPeerAmount: 3,
    port: 30303,
    federatorInstanceId: 'federatorInstanceId_replace_this',
	telegramBot: {
		token: telegramToken,
		groupId: -543088999,
    },
    confirmationTable: {
        "1": {
            "default": 400,
            "minConfirmation": 10,
            "BUSD": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
            "BUSDes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 4
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
                    "confirmations": 4
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
                    "confirmations": 4
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
                    "confirmations": 4
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
                    "confirmations": 4
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
                    "confirmations": 4
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
            "RBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 500000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 50
                }
            ],
            "bRBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 500000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 50
                }
            ],
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
            "bSOV": [
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
            "BUSD": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
            "BNB": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 20
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
            "BUSDes": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
            "BUSDbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHbs": [
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
            "BNBbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 20
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
                    "confirmations": 4
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
                    "confirmations": 4
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
                    "confirmations": 4
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
            "BNB": [
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
                    "confirmations": 4
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
                    "confirmations": 4
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
                    "confirmations": 4
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
               "default": 3,
               "minConfirmation": 3,
        },  
        "56": {
            "default": 400,
            "minConfirmation": 10,
            "RBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 500000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 50
                }
            ],
            "bRBTC": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 50000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 500000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 1000000000000000000,
                    "confirmations": 50
                }
            ],
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
            "bSOV": [
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
            "BUSD": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
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
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
            "BNB": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 20
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
            "BUSDbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
            "DAIbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDCbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
	        "USDTbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 2000000000000000000000,
                    "confirmations": 20
                },
                {
                    "amount": 20000000000000000000000,
                    "confirmations": 30
                },
                {
                    "amount": 200000000000000000000000,
                    "confirmations": 50
                }
            ],
            "ETHbs": [
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
            "BNBbs": [
                {
                    "amount": 0,
                    "confirmations": 10
                },
                {
                    "amount": 5000000000000000000,
                    "confirmations": 20
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

