const web3 = require('web3');

module.exports = class ClientId {
    constructor(logger, config, Web3 = web3) {
        this.config = config;
        this.logger = logger;
        EtherScanChainId = 1;

        this.mainWeb3 = new Web3(this.config.mainchain.host);
        this.sideWeb3 = new Web3(this.config.sidechain.host);
    }

    async _getChainId() {
        this.client = this.sideWeb3
        const chainIdSide = await this.client.eth.net.getId();
        
        this.client = this.mainWeb3
        const chainIdMain = await this.client.eth.net.getId();
        
        if (chainIdSide == EtherScanChainId || chainIdMain == EtherScanChainId) {
            return true
        } 
    }
}