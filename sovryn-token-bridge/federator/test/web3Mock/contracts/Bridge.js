const Contract = require('./Contract');
const defaults = require('../defaults');

const methods = {};

methods.acceptTransfer = () => ({
    encodeABI: () => Promise.resolve('0x0')
});

methods.transactionWasProcessed = () => ({
    call: () => Promise.resolve(false)
});

class Bridge extends Contract {
    constructor() {
        super();
        this.methods = methods;
    }

    getPastEvents(type, options) {
        let pastEvents = defaults.data.pastEvent;
        if (options.fromBlock)
            pastEvents = pastEvents.filter(log => options.fromBlock <= log.blockNumber);

        if (options.toBlock)
            pastEvents = pastEvents.filter(log => log.blockNumber < options.toBlock);

        return Promise.resolve(pastEvents);
    }
}

module.exports = Bridge;
