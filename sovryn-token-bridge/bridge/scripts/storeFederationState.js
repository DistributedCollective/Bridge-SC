////
//// npx truffle exec scripts/storeFederationState.js --network rsktestnet
////
//const web3 = require('web3');
const fs = require('fs');
const federationAbi = require("../../abis/Federation.json");

// const bscBSCBridge_v2 = require("../../../federator-env/testnet-BSC-RSK/btestnet_v2.json");
// const rskBSCBridge_v2 = require("../../../federator-env/testnet-BSC-RSK/rsktestnet_v2.json");

// const ethETHBridge_v2 = require("../../../federator-env/testnet-ETH-RSK/ropsten_v2.json");
// const ethETHBridge = require("../../../federator-env/testnet-ETH-RSK/ropsten.json");
// const rskETHBridge_v2 = require("../../../federator-env/testnet-ETH-RSK/rsktestnet_v2.json");
// const rskETHBridge = require("../../../federator-env/testnet-ETH-RSK/rsktestnet.json");

const ethETHBridge_v2 = require("../../../federator-env/mainnet-ETH-RSK/mainnet_v2.json");
const ethETHBridge = require("../../../federator-env/mainnet-ETH-RSK/mainnet.json");
const rskETHBridge_v2 = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet_v2.json");
const rskETHBridge = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet.json");

let fromPageBlock

////Testnet:
// const deployer = "0x12D90403733b6DD1f88240C773a6613331e60bCF";
////Mainnet:
const deployer = "0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2";

//fromPageBlock = ethETHBridge.fromBlock;
//ethETHBridge_v2.federation Creation Block
// Mainnet bridge creation block
// fromPageBlock = 12110034
// Ropsten bridge creation block
// fromPageBlock = 9998777;
// const federationAddress = ethETHBridge.federation;
// const federation_v2Address = ethETHBridge_v2.federation;

// fromPageBlock = rskETHBridge.fromBlock;
// //ethETHBridge_v2.federation Creation Block
// RSKMainnet bridge creation block
fromPageBlock = 3258718
// Ropsten bridge creation block
// fromPageBlock = 1745628;
const federationAddress = rskETHBridge.federation;
const federation_v2Address = rskETHBridge_v2.federation;

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
    const net = process.argv[5];
    console.log("net is:"+ net);

    const toPagedBlock = await web3.eth.getBlockNumber()
    console.log("from Block TO Block: " + fromPageBlock + " TO " + toPagedBlock);
    console.log("federation_v2Address: "+ federation_v2Address);
    console.log("federationAddress: "+ federationAddress);

    const federation_v2 = new web3.eth.Contract(federationAbi, federation_v2Address);
    const federation = new web3.eth.Contract(federationAbi, federationAddress);

    const logs = await federation_v2.getPastEvents(
        "Executed",
        {                            
            fromBlock: fromPageBlock,
            toBlock: toPagedBlock
        },
    );
    
    const gasPrice = await web3.eth.getGasPrice();
    console.log("gas price is: " + gasPrice);
    let gasPriceNow = gasPrice;
    if (net == "mainnet") {
        gasPriceNow = Number.parseInt(gasPrice * 1.5);
    }
    console.log("gas price now is: " + gasPriceNow); 


    const logsLength = await logs.length;
    console.log("logsLength: " + logsLength) ; 
    // let arrSize = 200;
    // let i = 0;
    let arrSize = 150;
    let i = 0;

    while(i < logsLength){
        if((i+arrSize) > logsLength){
            arrSize = logsLength - i ;
        }
        let TXArr = [];
        for (j=0 ; j < arrSize ; j++) {
            transactionId = logs[i+j].returnValues.transactionId;
            blockNumber = logs[i+j].blockNumber;
            console.log(transactionId + " ; " + blockNumber);    
            TXArr.push(transactionId);
        }
        console.log("TXArr: \n" + TXArr);
        await federation.methods.initStoreOldFederation(TXArr).send({
            //from: deployer, gasPrice: gasPriceNow  
            from: deployer, 
         })
        i = i + arrSize;
        console.log("index: " + i);
    }
    

}
