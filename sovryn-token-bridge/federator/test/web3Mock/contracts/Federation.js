const Contract = require('./Contract');
const defaults = require('../defaults');

const methods = {};

methods.transactionCount = () => ({
    call: () => Promise.resolve(defaults.data.transactionCount),
});

methods.getTransactionId = () => ({
    call: () => Promise.resolve(defaults.data.transactionId),
});

methods.getTransactionIdU = () => ({
    call: () => Promise.resolve(defaults.data.transactionIdU),
});

methods.transactionWasProcessed = () => ({
    call: () => Promise.resolve(false),
});

methods.executeTransaction = () => ({
    encodeABI: () => '0x0',
});

methods.confirmations = () => ({
    call: () => Promise.resolve(defaults.data.confirmations),
});

methods.confirmTransaction = () => ({
    encodeABI: () => '0x0',
});

methods.submitTransaction = () => ({
    encodeABI: () => '0x0',
});

methods.hasVoted = () => ({
    call: () => false,
});

methods.executeTransactionAt = () => ({
    encodeABI: () => '0x0',
});

class MultiSig extends Contract {
    constructor() {
        super();
        this.methods = methods;
    }
}

module.exports = MultiSig;
