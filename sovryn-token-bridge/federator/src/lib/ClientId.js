var constants = require('./Constants');

const web3 = require('web3');
module.exports = class ClientId {
    
    constructor(logger, config, Web3 = web3) {
        this.config = config;
        this.logger = logger;

        this.mainWeb3 = new Web3(this.config.mainchain.host);
        this.sideWeb3 = new Web3(this.config.sidechain.host);
    }

    async isEthereumChain() {
        const chainIdSide = await this.sideWeb3.eth.net.getId();
        const chainIdMain = await this.mainWeb3.eth.net.getId();
        console.log("chainIdSide: " + chainIdSide);
        console.log("chainIdMain: " + chainIdMain);
        console.log("constants.ETHERSCAN_CHAIN_ID: " + constants.ETHERSCAN_CHAIN_ID);
        return (parseInt(chainIdSide) === parseInt(constants.ETHERSCAN_CHAIN_ID) || parseInt(chainIdMain) === parseInt(constants.ETHERSCAN_CHAIN_ID));
    }
}