const fs = require('fs');
let telegramToken;
try {
    telegramToken = fs.readFileSync(`${__dirname}/telegram.key`, 'utf8').trim();
} catch (e) {
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
    fedAddress: '',
    mainchain: require('./local-a.json'), //the json containing the smart contract addresses in rsk
    sidechain: require('./local-b.json'), //the json containing the smart contract addresses in eth
    minimumPeerAmount: 2,
    port: 30303,
    runEvery: 0.166666667, // In minutes,
    confirmations: 120, // Number of blocks before processing it, if working with ganache set as 0
    privateKey: fs.readFileSync(`${__dirname}/test-federator1.key`, 'utf8').trim(),
    signaturesTTL: 120,
    storagePath: './db',
    federatorInstanceId: '',
    etherscanApiKey: etherscanApiKey,
    telegramBot: {
        token: telegramToken,
        groupId: 0, // Telegram group id to send the messages to
    },
    confirmationTable: {
        1: {
            default: 5760,
            minConfirmation: 10,
            WETH: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            WBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            DAI: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            renBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            TST: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 10,
                },
                {
                    amount: 0.5,
                    confirmations: 10,
                },
            ],
        },
        3: {
            default: 5760,
            minConfirmation: 10,
            WETH: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            WBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            DAI: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            renBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            TST: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 10,
                },
                {
                    amount: 0.5,
                    confirmations: 10,
                },
            ],
        },
        30: {
            default: 2880,
            minConfirmation: 10,
            WETH: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            WBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            DAI: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            renBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
        },
        31: {
            default: 10,
            minConfirmation: 10,
            WETH: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            WBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            DAI: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            renBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
        },
        42: {
            default: 10,
            minConfirmation: 10,
            WETH: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            WBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
            DAI: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 50,
                    confirmations: 30,
                },
                {
                    amount: 100,
                    confirmations: 50,
                },
            ],
            renBTC: [
                {
                    amount: 0,
                    confirmations: 10,
                },
                {
                    amount: 0.2,
                    confirmations: 30,
                },
                {
                    amount: 0.5,
                    confirmations: 50,
                },
            ],
        },
    },
    // peers: [
    //     {
    //         ip: 'federator1',
    //         port: 30303,
    //         address: '0x8c981fEa9Fa5eD6248a50da281ffD7fB87D0ee16',
    //     },
    //     {
    //         ip: 'federator2',
    //         port: 30304,
    //         address: '0xA59f8360a2BDB46104E601c5106eb0aA128d494B',
    //     },
    //     {
    //         ip: 'federator3',
    //         port: 30305,
    //         address: '0x189Ec9a470F38Ee8Dc732b8fCC9d03624cD0d6A0',
    //     },
    // ],
};
