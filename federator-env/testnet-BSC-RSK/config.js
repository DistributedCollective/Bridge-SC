const fs = require("fs");
let telegramToken;
try {
  telegramToken = fs.readFileSync(`${__dirname}/telegram.key`, "utf8").trim();
} catch (e) {
  console.debug(`Cannot load telegram token from ${__dirname}/telegram.key, bot disabled`);
  telegramToken = "";
}
module.exports = {
  mainchain: require("./rsktestnet.json"), //the json containing the smart contract addresses in rsk
  sidechain: require("./btestnet.json"), //the json containing the smart contract addresses in bsc
  runEvery: 2, // In minutes,
  confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
  privateKey: fs.readFileSync(`${__dirname}/federator.key`, "utf8").trim(),
  storagePath: "./db",
  federatorInstanceId: "federatorInstanceId_replace_this",
  federatorAddress: 'federatorAddress_replace_this',
  telegramBot: {
    token: telegramToken,
    groupId: -572987924,
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
                "confirmations": 2
            },
            {
                "amount": 5000000000000000000,
                "confirmations": 4
            }
        ],
        "ETHbs": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 1000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 5000000000000000000,
                "confirmations": 4
            }
        ],
      },
    "97": {
        "default": 4,
        "minConfirmation": 2,
        "DAI": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 2000000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 10000000000000000000000,
                "confirmations": 4
            }
        ],
        "USDC": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 2000000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 10000000000000000000000,
                "confirmations": 4
            }
        ],
        "USDT": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 2000000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 10000000000000000000000,
                "confirmations": 4
            }
        ],
        "ETH": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 1000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 5000000000000000000,
                "confirmations": 4
            }
        ],
        "DAIbs": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 2000000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 10000000000000000000000,
                "confirmations": 4
            }
        ],
        "USDCbs": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 2000000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 10000000000000000000000,
                "confirmations": 4
            }
        ],
        "USDTbs": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 2000000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 10000000000000000000000,
                "confirmations": 4
            }
        ],
        "ETHbs": [
            {
                "amount": 0,
                "confirmations": 2
            },
            {
                "amount": 1000000000000000000,
                "confirmations": 2
            },
            {
                "amount": 5000000000000000000,
                "confirmations": 4
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