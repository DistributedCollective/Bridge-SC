const contractMapping = require('./contractMapping');
const defaults = require('./defaults');
var Web3PromiEvent = require('web3-core-promievent');

let eth = {};

eth.getBlockNumber = () => defaults.data.blockNumber;
eth.getAccounts = () => defaults.data.accounts;
eth.getTransactionCount = () => defaults.data.ethTransactionCount;
eth.getGasPrice = () => defaults.data.gasPrice;
eth.estimateGas = () => defaults.data.estimatedGas;
eth.getNonce = () => defaults.data.ethTransactionCount;
eth.getTransaction = () => defaults.data.receipt; // not the same return type but close

let promiseSend = function () {
    var promiEvent = Web3PromiEvent();

    setTimeout(function () {
        promiEvent.eventEmitter.emit('transactionHash', defaults.data.receipt.transactionHash);
        promiEvent.resolve(defaults.data.receipt);
    }, 10);

    return promiEvent.eventEmitter;
};
eth.sendSignedTransaction = promiseSend;
eth.sendTransaction = promiseSend;

eth.Contract = contractMapping;

eth.net = {
    getId: () => defaults.data.netId,
};

eth.mockMethods = (methods) => {
    return {
        ...eth,
        ...methods,
    };
};

module.exports = eth;
