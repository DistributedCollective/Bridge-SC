const web3 = require('web3');
const Contract = require('./Contract');
const defaults = require('../defaults');

class Bridge extends Contract {
    constructor() {
        super();

        this._processedTransactions = {};
        this.methods = {
            acceptTransfer: () => ({
                encodeABI: () => Promise.resolve('0x0')
            }),
            getTransactionId: (
                _blockHash,
                _transactionHash,
                _receiver,
                _amount,
                _logIndex
            ) => ({
                call: () => Promise.resolve(
                    web3.utils.keccak256(
                        web3.utils.encodePacked(
                            _blockHash,
                            _transactionHash,
                            _receiver,
                            _amount,
                            _logIndex
                        )
                    )
                ),
            }),
            processed: (_transactionId) => ({
                call: () => Promise.resolve(
                    !!this._processedTransactions[_transactionId]
                ),
            }),
        };
    }

    getPastEvents(type, options) {
        let pastEvents = defaults.data.pastEvent;
        if (options.fromBlock)
            pastEvents = pastEvents.filter(log => options.fromBlock <= log.blockNumber);

        if (options.toBlock)
            pastEvents = pastEvents.filter(log => log.blockNumber < options.toBlock);

        return Promise.resolve(pastEvents);
    }

    // Utility methods for testing, not part of contract ABI
    resetState() {
        this._processedTransactions = {};
    }
    setProcessedTransaction(transactionId, processed) {
        this._processedTransactions[transactionId] = processed;
    }
}

module.exports = Bridge;
