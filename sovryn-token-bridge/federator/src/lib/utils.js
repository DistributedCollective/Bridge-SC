const ethUtils = require('ethereumjs-util');
const Web3 = require('web3');

async function waitBlocks(client, numberOfBlocks) {
    var startBlock = await client.eth.getBlockNumber();
    var currentBlock = startBlock;
    while (numberOfBlocks > currentBlock - startBlock) {
        var newBlock = await client.eth.getBlockNumber();
        if (newBlock != currentBlock) {
            currentBlock = newBlock;
        } else {
            await sleep(20000);
        }
    }
}

async function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function exponentialSleep(attempt = 0, opts = {}) {
    const { maxSleepMs = 256000, initialSleepMs = 1000, logger = null } = opts;
    let sleepMs = initialSleepMs * 2 ** attempt;
    sleepMs = Math.min(sleepMs, maxSleepMs);
    if (logger) {
        logger.debug(`Sleeping ${sleepMs} ms`);
    }
    return await sleep(sleepMs);
}

async function sleepRandomNumberOfBlocks(chainId, opts = {}) {
    const { minBlocks = 0, maxBlocks = 7, logger = null } = opts;
    chainId = parseInt(chainId);
    let blockTime = 13; // ethereum
    if (chainId === 30 || chainId === 31) {
        // rsk
        blockTime = 30;
    } else if (chainId === 56 || chainId === 97) {
        // bsc
        blockTime = 5;
    }

    const numBlocks = Math.floor(Math.random() * (maxBlocks - minBlocks) + minBlocks);
    const sleepMs = blockTime * numBlocks * 1000;
    if (logger) {
        logger.info(`Sleeping ~${numBlocks} blocks with block time ${blockTime} s = ${sleepMs} ms`);
    }
    return await sleep(sleepMs);
}

async function waitForReceipt(txHash) {
    let timeElapsed = 0;
    let interval = 10000;
    return new Promise((resolve, reject) => {
        const checkInterval = setInterval(async () => {
            timeElapsed += interval;
            let receipt = await web3.eth.getTransactionReceipt(txHash);
            if (receipt != null) {
                clearInterval(checkInterval);
                resolve(receipt);
            }
            if (timeElapsed > 70000) {
                reject(
                    `Operation took too long <a target="_blank" href="${config.explorer}/tx/${txHash}">check Tx on the explorer</a>`
                );
            }
        }, interval);
    });
}

function hexStringToBuffer(hexString) {
    return ethUtils.toBuffer(ethUtils.addHexPrefix(hexString));
}

function stripHexPrefix(str) {
    return str.indexOf('0x') == 0 ? str.slice(2) : str;
}

function privateToAddress(privateKey) {
    return ethUtils.bufferToHex(ethUtils.privateToAddress(this.hexStringToBuffer(privateKey)));
}

// Returns current memory allocated in MB
function memoryUsage() {
    let { heapUsed } = process.memoryUsage();
    return Math.round(heapUsed / (1024 * 1024));
}

function calculatePrefixesSuffixes(nodes) {
    const prefixes = [];
    const suffixes = [];
    const ns = [];

    for (let i = 0; i < nodes.length; i++) {
        nodes[i] = stripHexPrefix(nodes[i]);
    }

    for (let k = 0, l = nodes.length; k < l; k++) {
        if (k + 1 < l && nodes[k + 1].indexOf(nodes[k]) >= 0) continue;

        ns.push(nodes[k]);
    }

    let hash = Web3.utils.sha3(Buffer.from(ns[0], 'hex'));
    hash = stripHexPrefix(hash);

    prefixes.push('0x');
    suffixes.push('0x');

    for (let k = 1, l = ns.length; k < l; k++) {
        const p = ns[k].indexOf(hash);

        prefixes.push(ethUtils.addHexPrefix(ns[k].substring(0, p)));
        suffixes.push(ethUtils.addHexPrefix(ns[k].substring(p + hash.length)));

        hash = Web3.utils.sha3(Buffer.from(ns[k], 'hex'));
        hash = stripHexPrefix(hash);
    }

    return { prefixes: prefixes, suffixes: suffixes };
}

function eliminateDuplicates(arrays) {
    const set = new Set();
    arrays.forEach((array) => array.forEach((item) => set.add(item)));
    return Array.from(set);
}

function createTimestamp(secondsOffset) {
    return Math.floor(Date.now() / 1000) + secondsOffset;
}

function validateDeadline(deadline, bufferSeconds = 0) {
    const currentTimestamp = Math.floor(Date.now() / 1000);
    return deadline >= currentTimestamp + bufferSeconds;
}

module.exports = {
    waitBlocks: waitBlocks,
    sleep: sleep,
    exponentialSleep: exponentialSleep,
    sleepRandomNumberOfBlocks: sleepRandomNumberOfBlocks,
    hexStringToBuffer: hexStringToBuffer,
    privateToAddress: privateToAddress,
    stripHexPrefix: stripHexPrefix,
    memoryUsage: memoryUsage,
    calculatePrefixesSuffixes: calculatePrefixesSuffixes,
    zeroHash: '0x0000000000000000000000000000000000000000000000000000000000000000',
    waitForReceipt: waitForReceipt,
    eliminateDuplicates: eliminateDuplicates,
    createTimestamp,
    validateDeadline,
};
