////
//// npx truffle exec scripts/storeFederationState.js --network rsktestnet
////
//const web3 = require('web3');
const fs = require('fs');
const federationAbi = require("../../abis/Federation.json");
const federationAbi_v2 = require("../../abis/Federation_v2.json");

 const bscBSCBridge_v2 = require("../../../federator-env/testnet-BSC-RSK/btestnet_v2.json");
 const rskBSCBridge_v2 = require("../../../federator-env/testnet-BSC-RSK/rsktestnet_v2.json");
 const bscBSCBridge = require("../../../federator-env/testnet-BSC-RSK/btestnet.json");
 const rskBSCBridge = require("../../../federator-env/testnet-BSC-RSK/rsktestnet.json");

// const ethETHBridge_v2 = require("../../../federator-env/testnet-ETH-RSK/ropsten_v2.json");
// const ethETHBridge = require("../../../federator-env/testnet-ETH-RSK/ropsten.json");
// const rskETHBridge_v2 = require("../../../federator-env/testnet-ETH-RSK/rsktestnet_v2.json");
// const rskETHBridge = require("../../../federator-env/testnet-ETH-RSK/rsktestnet.json");

// const ethETHBridge_v2 = require("../../../federator-env/mainnet-ETH-RSK/mainnet_v2.json");
// const ethETHBridge = require("../../../federator-env/mainnet-ETH-RSK/mainnet.json");
// const rskETHBridge_v2 = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet_v2.json");
// const rskETHBridge = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet.json");

// const bscBSCBridge_v2 = require("../../../federator-env/mainnet-BSC-RSK/bmainnet_v2.json");
// const bscBSCBridge = require("../../../federator-env/mainnet-BSC-RSK/bmainnet.json");
// const rskBSCBridge_v2 = require("../../../federator-env/mainnet-BSC-RSK/rskmainnet_v2.json");
// const rskBSCBridge = require("../../../federator-env/mainnet-BSC-RSK/rskmainnet.json");

let fromPageBlock

////Testnet:
 const deployer = "0x12D90403733b6DD1f88240C773a6613331e60bCF";
////Mainnet:
//const deployer = "0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2";

//fromPageBlock = ethETHBridge.fromBlock;
//ethETHBridge_v2.federation Creation Block
// Mainnet bridge creation block
// fromPageBlock = 12110034
//fromPageBlock = 13041698; //ETHmainnnetMY
//fromPageBlock = 13043151

// Ropsten bridge creation block
// fromPageBlock = 9998777;
// const federationAddress = ethETHBridge.federation;
// const federation_v2Address = ethETHBridge_v2.federation;

//BSC Bridge rsktestnet
// Creation block
// fromPageBlock = 1884421;
// const federationAddress = rskBSCBridge.federation;
// const federation_v2Address = rskBSCBridge_v2.federation;
// Creation block
fromPageBlock = 			12945603								;
toPageBlock = 				12945813				   		;
const federationAddress = bscBSCBridge.federation;
const federation_v2Address = bscBSCBridge_v2.federation;

//BSC Bridge rskmainnet
// Creation block
// fromPageBlock = 3398643;
// const federationAddress = rskBSCBridge.federation;
// const federation_v2Address = rskBSCBridge_v2.federation;
// const federationAddress = rskBSCBridge.federation;
// const federation_v2Address = rskBSCBridge_v2.federation;

//BSC Bridge bmainnet
// Creation block
// fromPageBlock = 7912333;
// const federationAddress = bscBSCBridge.federation;
// const federation_v2Address = bscBSCBridge_v2.federation;

// fromPageBlock = rskETHBridge.fromBlock;
// //ethETHBridge_v2.federation Creation Block
// RSKMainnet bridge creation block
// fromPageBlock = 3258718;
//fromPageBlock = 3424935;
// fromPageBlock =3609478  //  latest rskmainnet block to update from <---
// fromPageBlock = 3385920; // update till i = 900
// const toPagedBlock = 3268718  // update till i = 900

// Ropsten bridge creation block
// fromPageBlock = 1745628;
// const federationAddress = rskETHBridge.federation;
// const federation_v2Address = rskETHBridge_v2.federation;

module.exports = async callback => {
    try {
        await getState();

    } catch (e) {
        callback(e);
      }
      callback();
      console.log('All done.')
};    

/////
// const fromBlock = fromPageBlock;
// const toBlock = await web3.eth.getBlockNumber();
// const batchSize = 100;

// const logs = [];
// let batchFromBlock = fromBlock;
// while (batchFromBlock <= toBlock) {
//     const batchToBlock = Math.min(batchFromBlock + batchSize, toBlock);
//     const batchLogs = await federation_v2.getPastEvents(
//         "Executed",
//         {
//             fromBlock: batchFromBlock,
//             toBlock: batchToBlock,
//         },
//     );
//     logs.push(...batchLogs);
//     batchFromBlock = batchToBlock + 1;
// }


///
async function getState() {    
    const net = process.argv[5];
    console.log("net is:"+ net);

    //const toPagedBlock = await web3.eth.getBlockNumber()
    // console.log("from Block TO Block: " + fromPageBlock + " TO " + toPagedBlock);
    console.log("federation_v2Address: "+ federation_v2Address);
    console.log("federationAddress: "+ federationAddress);

    const federation_v2 = new web3.eth.Contract(federationAbi_v2, federation_v2Address);
    const federation = new web3.eth.Contract(federationAbi, federationAddress);


    const fromBlock = fromPageBlock;
    //  const toBlock = await web3.eth.getBlockNumber();  
    
     const toBlock = toPageBlock;
    //const toBlock = 3636444; //  BSC RSKmainnet last block that it's tx was stored
    //const toBlock = 10471035; // BSC bmainnet last block that it's tx was stored
    
    const batchSize = 100;
    console.log("from Block TO Block: " + fromBlock + " TO " + toBlock);

    const logs = [];
    let batchFromBlock = fromBlock;
    while (batchFromBlock <= toBlock) {
        const batchToBlock = Math.min(batchFromBlock + batchSize, toBlock);
        console.log("fetching from", batchFromBlock, "to", batchToBlock);
        const batchLogs = await federation_v2.getPastEvents(
            "Executed",
            {
                fromBlock: batchFromBlock,
                toBlock: batchToBlock,
            },
        );
        console.log("found", batchLogs.length, "logs");
        logs.push(...batchLogs);
        batchFromBlock = batchToBlock + 1;
    }
    



    // const logs = await federation_v2.getPastEvents(
    //     "Executed",
    //     {                            
    //         fromBlock: fromPageBlock,
    //         toBlock: toPagedBlock
    //     },
    // );
    
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
            from: deployer, gasPrice: gasPriceNow  
            //from: deployer, 
         })
        i = i + arrSize;
        console.log("index: " + i);
    }
    

}
