//const web3 = require('web3');
const fs = require('fs');
const federationAbi = require("../../abis/Federation.json");

const bscBSCBridge_v3 = require("../../../federator-env/testnet-BSC-RSK/btestnet.json");
const rskBSCBridge_v3 = require("../../../federator-env/testnet-BSC-RSK/rsktestnet.json");
const rskETHBridge_v3 = require("../../../federator-env/testnet-ETH-RSK/rsktestnet.json");
const ethETHBridge_v3 = require("../../../federator-env/testnet-ETH-RSK/ropsten_v3.json");

const ethETHBridge = require("../../../federator-env/testnet-ETH-RSK/ropsten.json");

module.exports = async callback => {
    try {
        await getState();

    } catch (e) {
        callback(e);
      }
      callback();
      console.log('All done.')
};    


async function getState() {    
    const fromPageBlock = 10222073;
    const toPagedBlock = await web3.eth.getBlockNumber()

    const federation_v3Address = ethETHBridge_v3.federation;
    console.log("federation_v3Address: "+ federation_v3Address);
    
    const federationAddress = ethETHBridge.federation;
    console.log("federationAddress: "+ federationAddress);

    const federation_v3 = new web3.eth.Contract(federationAbi, federation_v3Address);
    const federation = new web3.eth.Contract(federationAbi, federationAddress);

    const logs = await federation_v3.getPastEvents(
        "Executed",
        {                            
            fromBlock: fromPageBlock,
            toBlock: toPagedBlock
        },
    );
    
    const logsLength = await logs.length;
    console.log("logsLength: " + logsLength) ;    
    
    for (i=0 ; i < logsLength ; i++) {
        console.log(logs[i].transactionHash);
        const results = await federation.methods.initStoreOldFederation(logs[i].transactionHash);
        console.log('results:', results);
    }

}
