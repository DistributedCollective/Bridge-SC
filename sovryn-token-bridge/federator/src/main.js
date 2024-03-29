const log4js = require('log4js');
const web3 = require('web3');

const P2p = require('./lib/p2p');
const { eliminateDuplicates } = require('./lib/utils');
const {
    MAIN_FEDERATOR,
    SIDE_FEDERATOR,
    MAIN_SIGNATURE_REQUEST,
    SIDE_SIGNATURE_REQUEST,
    MAIN_SIGNATURE_SUBMISSION,
    SIDE_SIGNATURE_SUBMISSION,
} = require('./lib/constants');

// Configurations
const config = require('../config/config.js');
const logConfig = require('../config/log-config.json');
log4js.configure(logConfig);
const peersConfig = require('../config/peers.config.js');

// Services
const Scheduler = require('./services/Scheduler.js');

//GasPriceFetcher
const Federator = require('./lib/Federator.js');
const { TelegramBot, NullBot } = require('./lib/chatBots.js');
const ClientId = require('./lib/ClientId.js');
// const GasPriceFetcher = require('./lib/GasPriceFetcher.js');
// const GasPriceAvg = require('./lib/GasPriceAvg.js');
const GasServices = require('./lib/GasServices.js');

// Global GasPrice Variables
// let currentEthGasBasePrice;
// let currentEthGasPriceAvg;

const logger = log4js.getLogger('Federators');
logger.info('RSK Host', config.mainchain.host);
logger.info('ETH Host', config.sidechain.host);

this.logger = logger;

if (!config.mainchain || !config.sidechain) {
    logger.error('Mainchain and Sidechain configuration are required');
    process.exit();
}

let chatBot;
if (config.telegramBot && config.telegramBot.token && config.telegramBot.groupId) {
    chatBot = new TelegramBot(
        config.telegramBot.token,
        config.telegramBot.groupId,
        log4js.getLogger('CHATBOT'),
        config.federatorInstanceId
    );
} else {
    chatBot = new NullBot(log4js.getLogger('CHATBOT'));
}

if (process.argv[2]) config.port = parseInt(process.argv[2]);
if (process.argv[3]) config.privateKey = process.argv[3];

const p2pNode = new P2p(logger);

const clientId = new ClientId(log4js.getLogger('Get-Client-Id'), config, web3);

const gasServices = new GasServices(log4js.getLogger('ETH-GasServices'), config, web3);

// const gasPriceFetcher = new GasPriceFetcher(
//     log4js.getLogger('ETH-MAINNET-GasPriceFetcher'),
// );

// const gasPriceAvg = new GasPriceAvg(
//     log4js.getLogger('ETH-MAINNET-GasPriceFetAvg'),
// );

const mainFederator = new Federator(
    MAIN_FEDERATOR,
    config,
    log4js.getLogger('MAIN-FEDERATOR'),
    p2pNode,
    web3,
    chatBot
);

const sideFederator = new Federator(
    SIDE_FEDERATOR,
    {
        ...config,
        mainchain: config.sidechain,
        sidechain: config.mainchain,
        storagePath: `${config.storagePath}/side-fed`,
    },
    log4js.getLogger('SIDE-FEDERATOR'),
    p2pNode,
    web3,
    chatBot
);

function initiateP2pListener() {
    p2pNode.net.onMessage(async (msg) => {
        if (msg.type === MAIN_SIGNATURE_REQUEST) {
            await handleRequest(msg, mainFederator, MAIN_SIGNATURE_SUBMISSION);
        } else if (msg.type === SIDE_SIGNATURE_REQUEST) {
            await handleRequest(msg, sideFederator, SIDE_SIGNATURE_SUBMISSION);
        }
    });
}

async function handleRequest(msg, federator, submissionType) {
    logger.info(
        `A signature request has been received from ${msg.source.id} for event ${msg.data.log.id}`
    );
    try {
        const { blockNumber, id } = msg.data.log;
        const signature = await federator.signTransaction({
            blockNumber,
            id,
        });
        msg.source.send(submissionType, signature);
    } catch (err) {
        logger.warn(err);
    }
}

let pollingInterval = config.runEvery * 1000 * 60; // Minutes
// let gasApiPollingInterval = config.gasApiRunEvery * 1000 ; // Seconds
// let avgGasPollingInterval = config.avgGasRunEvery * 1000 ; // Seconds
// let avgGasPeriodInterval = config.periodAvgGas * 1000 * 60 ; // Minutes
// let avgGasCount;

let scheduler = new Scheduler(pollingInterval, logger, { run: () => run() });

startServices().catch((err) => {
    console.error('Error starting services:', err);
});

async function startServices() {
    let isEth;
    try {
        isEth = await clientId.isEthereumChain();
        console.log('isEth: ' + isEth);
    } catch (err) {
        logger.error('Unhandled Error on isEthereumChain()', err);
        process.exit();
    }

    if (isEth) {
        try {
            await gasServices.startGasServices();
        } catch (err) {
            logger.error('Cannnot start ETH gas services()', err);
            process.exit();
        }
    }


    let fedAddress = config.federatorAddress;
    let peers = peersConfig.peers
    let peersFiltered = peers.filter(
        peer => (
            (peer.address || '').toLowerCase() !== (fedAddress || '').toLowerCase()
        )
    );
    console.log(peersFiltered);

    try {
        await mainFederator.populateMemberAddresses();
        await sideFederator.populateMemberAddresses();
        const membersAddresses = eliminateDuplicates([
            await mainFederator.getMemberAddresses(),
            await sideFederator.getMemberAddresses(),
        ]);

        p2pNode.initiateP2pNetwork(
            'bridge-federators',
            config.port,
            peersFiltered,
            membersAddresses,
            config.privateKey
        );

        initiateP2pListener();
        await p2pNode.start();
    } catch (err) {
        logger.error("Couldn't start P2P network", err);
        setTimeout(() => startServices(), 2000);
        return;
    }

    scheduler.start().catch((err) => {
        logger.error('Unhandled Error on start()', err);
    });
}

async function run() {
    const numOtherPeers = p2pNode.getPeerAmount();
    let nodeId = '';
    let leaderId = '';
    try {
        nodeId = p2pNode.net.networkId;
        leaderId = p2pNode.getLeaderId();
    } catch (e) {
        // just ignore now, this is only for debugging
    }
    if (numOtherPeers < config.minimumPeerAmount) {
        logger.info(`Waiting for enough peers (now ${numOtherPeers}. node ${nodeId}, leader ${leaderId})`);
        return;
    }

    if (p2pNode.isLeader()) {
        console.log(`This node is a leader -- handling iteration. (${numOtherPeers} other peers, node ${nodeId}, leader ${leaderId})`);
        try {
            console.log('before mainfed');
            await mainFederator.run();
            console.log('before sidefed');
            await sideFederator.run();
        } catch (err) {
            logger.error('Unhandled Error on run()', err);
            process.exit();
        }
    } else {
        console.log(`Not leader, just chilling. (${numOtherPeers} other peers, node ${nodeId}, leader ${leaderId})`)
    }
}

async function exitHandler() {
    try {
        await p2pNode.stop();
    } catch (err) {
        throw new Error(err);
    }
    process.exit();
}

// catches ctrl+c event
process.on('SIGINT', exitHandler);

// catches "kill pid" (for example: nodemon restart)
process.on('SIGUSR1', exitHandler);
process.on('SIGUSR2', exitHandler);

// export so we can test it
module.exports = { scheduler };
