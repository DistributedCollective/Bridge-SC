////
//// npx truffle exec scripts/storeFederationState.js --network rsktestnet
////
//const web3 = require('web3');
const fs = require('fs');
const federationAbi = require("../../abis/Federation.json");
const federationAbi_v5 = require("../../abis/Federation_v5.json");

//  const bscBSCBridge_v5 = require("../../../federator-env/testnet-BSC-RSK/btestnet_v5.json");
//  const rskBSCBridge_v5 = require("../../../federator-env/testnet-BSC-RSK/rsktestnet_v5.json");
//  const bscBSCBridge = require("../../../federator-env/testnet-BSC-RSK/btestnet.json");
//  const rskBSCBridge = require("../../../federator-env/testnet-BSC-RSK/rsktestnet.json");

const ethETHBridge_v5 = require("../../../federator-env/testnet-ETH-RSK/ropsten_v5.json");
const ethETHBridge = require("../../../federator-env/testnet-ETH-RSK/ropsten.json");
// const rskETHBridge_v5 = require("../../../federator-env/testnet-ETH-RSK/rsktestnet_v5.json");
// const rskETHBridge = require("../../../federator-env/testnet-ETH-RSK/rsktestnet.json");

// const ethETHBridge_v5 = require("../../../federator-env/mainnet-ETH-RSK/mainnet_v5.json");
// const ethETHBridge = require("../../../federator-env/mainnet-ETH-RSK/mainnet.json");
// const rskETHBridge_v5 = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet_v5.json");
// const rskETHBridge = require("../../../federator-env/mainnet-ETH-RSK/rskmainnet.json");

// const bscBSCBridge_v5 = require("../../../federator-env/mainnet-BSC-RSK/bmainnet_v5.json");
// const bscBSCBridge = require("../../../federator-env/mainnet-BSC-RSK/bmainnet.json");
// const rskBSCBridge_v5 = require("../../../federator-env/mainnet-BSC-RSK/rskmainnet_v5.json");
// const rskBSCBridge = require("../../../federator-env/mainnet-BSC-RSK/rskmainnet.json");

let fromPageBlock

////Testnet:
 const deployer = "0x12D90403733b6DD1f88240C773a6613331e60bCF";
////Mainnet:
//const deployer = "0xdc83580AbF622Ec75f69B56DDF945Dd6CDBF53D2";

//fromPageBlock = ethETHBridge.fromBlock;
//ethETHBridge_v5.federation Creation Block
// Mainnet bridge creation block
// fromPageBlock = 12110034
//fromPageBlock = 13041698; //ETHmainnnetMY
//fromPageBlock = 13043151

// Ropsten bridge creation block
// fromPageBlock = 9998777;
// const federationAddress = ethETHBridge.federation;
// const federation_v5Address = ethETHBridge_v5.federation;

//BSC Bridge rsktestnet
// Creation block
// fromPageBlock = 1884421;
// const federationAddress = rskBSCBridge.federation;
// const federation_v5Address = rskBSCBridge_v5.federation;
// Creation block
// fromPageBlock = 			12945603								;
// toPageBlock = 				12945813				   		;
// const federationAddress = bscBSCBridge.federation;
// const federation_v5Address = bscBSCBridge_v5.federation;

//BSC Bridge rskmainnet
// Creation block
// fromPageBlock = 3398643;
// const federationAddress = rskBSCBridge.federation;
// const federation_v5Address = rskBSCBridge_v5.federation;
// const federationAddress = rskBSCBridge.federation;
// const federation_v5Address = rskBSCBridge_v5.federation;

//BSC Bridge bmainnet
// Creation block
// fromPageBlock = 7912333;
// const federationAddress = bscBSCBridge.federation;
// const federation_v5Address = bscBSCBridge_v5.federation;

// fromPageBlock = rskETHBridge.fromBlock;
// //ethETHBridge_v5.federation Creation Block
// RSKMainnet bridge creation block
// fromPageBlock = 3258718;
//fromPageBlock = 3424935;
// fromPageBlock =3609478  //  latest rskmainnet block to update from <---
// fromPageBlock = 3385920; // update till i = 900
// const toPagedBlock = 3268718  // update till i = 900

// Ropsten bridge creation block
// fromPageBlock = 1745628;

//rskETHBridge_v5.federation creation_block: 2088922
//fromPageBlock = 2088922;
// const federationAddress = rskETHBridge.federation;
// const federation_v5Address = rskETHBridge_v5.federation;

//ethETHBridge_v5.federation creation_block: 10842155 
// fromPageBlock = 10842155 ;
fromPageBlock = 12252955 ;
const federationAddress = ethETHBridge.federation;
const federation_v5Address = ethETHBridge_v5.federation;

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
//     const batchLogs = await federation_v5.getPastEvents(
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

    const toPageBlock = await web3.eth.getBlockNumber()
    //console.log("from Block TO Block: " + fromPageBlock + " TO " + toPagedBlock);
    console.log("federation_v5Address: "+ federation_v5Address);
    console.log("federationAddress: "+ federationAddress);

    const federation_v5 = new web3.eth.Contract(federationAbi_v5, federation_v5Address);
    const federation = new web3.eth.Contract(federationAbi, federationAddress);


    const fromBlock = fromPageBlock;
    //  const toBlock = await web3.eth.getBlockNumber();  
    
     const toBlock = toPageBlock;
    //const toBlock = 3636444; //  BSC RSKmainnet last block that it's tx was stored
    //const toBlock = 10471035; // BSC bmainnet last block that it's tx was stored
    
    const batchSize = 500;
    console.log("from Block TO Block: " + fromBlock + " TO " + toBlock);

    const logs = [];
    let batchFromBlock = fromBlock;
    while (batchFromBlock <= toBlock) {
        const batchToBlock = Math.min(batchFromBlock + batchSize, toBlock);
        console.log("fetching from", batchFromBlock, "to", batchToBlock);
        const batchLogs = await federation_v5.getPastEvents(
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
    



    // const logs = await federation_v5.getPastEvents(
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
    
let TXArrF = ["0x3ef2524d13d2a9848938f56ff9bd108dac56975ba49f8a023b1543cb90740742","0xfd0a04ce28ebe6ba745ac4e4727df19e8c92881991a7528d95a441f9da1f4b09","0xaa7045419dd919e112dcb7e37d31124ad7f00ef811743324c1180d3824cafc82","0xc30d62f0aaa919ab0f03ae405c79e743b1491db5427fd6e9fce63eb98bdc411e","0x610637dd7233150c20c0191f1f2dcf8f599debcdd6d3721c9e687f2b8fa22e37","0x98bacd0bb9272ea2a61374505da38129da2af610a7f806b2fd289335f3859016","0xb402541ec5ad80e7ab236de301b23830e6379ee44020b8ed8453634f24d3497e","0x62bb7b4a93a0f146aad9f451e4d94d848a4c20fbc5c73041219fb55efd3eccc7","0xa630c1f2a5a8afffba9e9c4a4ba448f8e30baa99d1094dbc248c2588d6d7faeb","0x783878a7eef4321caf42c8a4a7aee7f2536218c0ab8ed097c41bb733c1c19309","0x8f92f28010c7fc0b395ca23f0a76dc8e25b3cacb29ca66e66830bf2b3d7729a0","0x73563f0568d070187d1e5eaf48daffce5dae25306bfc950167d28c4de25b699e","0x7b9957773d3af93508872f058b7b65466e93c3942e381cf7a27076b1a53c3f42","0x0a16296acbb9123db9757b65982d6cb0ca13e378a6fbf16457fad9bac529731b","0x0593ac3ebe47e78c662f0b34c0b9dbb6cdc11b8e2693d5a8314390c3c787d215","0xb8207a5ba06319a81d752cbe55a2e4a079c7e513b4a18112d87e8f2d643dd873","0x552051648defc6deeeadb44ba8bffc87c4deeb1c092277791ce7f59e47da2ff0","0xa69b85664c6c221020d2c3d6e99cd92cc1ba0129ca75ff9861c248c9432602f1","0xd6a0a366852819eacaaa4bd3f246dfa907d15031a4a5436d5fa2c01969da57b4","0x0a80a26b09eaa4ce695a8ce9c8910c7325bcfdafddde43211a8caeb6c6bd2ffe","0x5951074624cc58187b6bb98d6d0e68cef95def6cbd2482c0a064e1b5bd7a924d","0xaec5b4ec1ab0244c82f10a46aad1955a476c7f1f5fd49130eaa6abf16dc3517c","0x1751b407314525d3ac48ad9a4f8513ca9b42b9ec5f3764b90be6b2995cc51415","0x230b66786c895ceb16e3b637ced0aedb566ce2adde91bcac9a085e3e032f89f0","0x8a1a1774d4f94b8bf713218045258e9c3697203f75e0790ac73c82a745f76273","0x3abe02848bba0083ccce99f3e2b763c4af1b7a6d5b3874ee024dd06a8580b4a0","0xd173d06663766075cc0c8b762fcd2dd51aae94e1a9c6f89c3f7eb0c52ed107ff","0xd78565ea23290a6ca51a97fc4711baced56a320bdd5f552f4f3a8acb1dfabd37","0xdff6bf88e1cd3d079805b59b0980944f87cbfe2a75438d5dde8743349a5f848e","0x6700d8700040be6ff1211c6d70b8d07d16f525b396003a2509642b3ac3cd0a5c","0x9a48b39c7d9c4f9f98d1954630e2c19ab8ff8a7e9ee6ebca1a7828fe74b6e42f","0x5768be0479d5716bf905c67ed853cd6c7a7208c95c98f3a623696d5f49200098","0x8e30d8df66bd002d5ad8e114400917b1184c5d9615b0dd46eaa324748a1aa565","0x2c2676339ecbf73a86557b6c90bb346007073459f0b57f6dde4f7ae86430e721","0xe9deb14ad7de1ac54c539dcf7773c7cd7906b5a0f3660beef0f498badb180717","0xc998e0cadf3e16fa1cbe654ad9a9f6f980c5f4389fee058793da127e29e4e4b0","0x53ab361d1ae3e05bd0319691a196214b93b127165516153c7d36b77f24f14826","0xa3912fa8b923663897cc1e0633c8ab1c3f39efbe8435493ef07037de39d10798","0x0ec656bf2938691fcd017661c819818920c32f01a9d6865ea01077ce56cc36f6","0x10b9fcbf918713d1ad3235734029eccfafd5baeef9acf1bc5d922518f736a445","0x05747ed9841fe0298032c63231a31b5c5f24d10e675489db9617a1d9a573bbc2","0xdb2503c648d887e7a6b69bf3f3413cb3141f2de38e9d2736658baa4e1b717f39","0xdcfc6132c4a16291b8d128ac633ee675914538759d1404b2e975aa70d75b64fd","0x3576e89308a5398c6412dda1396ba099194b221b3d28b75abfb91a91e9531ef2","0x8299f8feccb3d7b7326e48e7b61ae0fa04ed6f006f3606e408599840525ca9b8","0xd34b36d4af84346410d25e6a747007e346b022d517c36340ddf8d346a5fad7e7","0xa6b9f82dc47de32df710a7e7f407687c4c13a89c9832bf13fc005be8207390a3","0xaff4096935c3fe43779ed41825117c8052b34e497660a65e2afeeedd97a81db2","0x964136486342d4830a625e11c56ba7decc7d9ed5e44a22323e911ea574816e47","0x1426b0d16fb6a6bb38908424b6f225819608b0e871b9005760d78303092c232d","0x9e148e27384cf728494b0dde4a070aa2799285cd7778080783c5db1ba68c4415","0xeec0b9e3225b8834f889bd9431f36efcee686b3bd4461307d86e75cbed256d16","0x17a75cae01d79b10a71b7f3fa83643945cf1e615ed67c769f129e4b47bc29748","0xb6e0f9e1fa29302a326708526f846623d9d1c7187b3a97de6444526b30598517","0xe4b9f8a12fda96674412ff03e0d2254fb606425665cb8bb8cbf24fb32afd7e2e","0xbc4a61cfe1f32944a5aad57d511a29257607ed979eb635b7b7d4a466009cc324","0xd0b3dc952fb5d95863dccaaaf1f611b558085860b59a7c12b3102cf593d2e18a","0x204c9c31e22f7d48ab4e4f6a910b8bfd69b30ef20994473c68f7753e9b2680c9","0xe58856c5810597c5a907090f1df95a685b8dc4163363c433f27c1ed23c1e3e06","0x7ad720f78424866c83933e62580958617a8fa568fb84f7e5ec3bc19e915f18c4","0x0e304ce9b1799555dd59521032946c93b5146180b0b0cea404cacc3b5f7ec2ef","0x48107078ffefd570bc20e0f373fcd1e6dd5a9d92f1f98cf2145b67153ffbc0a2","0x655265c9f6049549f4d3a6c710d950ad8a0dd280c53d542f66a8948f8b93236e","0xf9ee667f7dbe8fcb3008813ecdd6cdc00d124169f38c04ef7e28538ff7635dec","0x746a31a93ff5e0ef03c801ab74e4ac8e83db49ce5367eb8617edcd97f6ef852d","0xccebba1ad19f8b2cca7d44ab37cdfde600cc4dec17e88110c0b6b959f62c199d","0xc4d19f90ee08563c580fe9133377dc195ef9e2e8ea449980307c98c4542ac5cc","0x51240104f8a1d78c541df85565f5bbbac7d592d66684f3217ef2a9c1f6c45cbb","0x7ca91183861d47902281f517e946883b1521ac974e051b4a90c96aef62a50518","0x3781b9afa06ab9105051427675bfc58667ded7a1347fd1c68132421e4a9492f4","0x2be6eb97859d708deaf013bf409e4e9fdc36b6fe2771c17d749cc97d138020b2","0x6ea60ec05bc6fedc27136d89edb128aa2a2b57e7df19e2cf081553fe127a0ae2","0xb4e4a8021a067e25091aab3fc24c7d059547e9ea11e6699ee383a18c676a9695","0xb95b257d7b43103ac39fb53c4436c530d96d8b9f676b6aa38153bdf6b2a23d0f","0xc7ad548bd0a66ed899703ca872640735e35af83bf8786ffb51d6cd0fa72937db","0x3cbc4096da383c97ef198d93052733703677c194645540d72d9687095fe62bc8","0x50f8f50f2b4f9d4940e72cc68189a19cd5bd00a77beda8b63131907b4b12f7f6","0x2abcaa5cb15020b0b2de7fa6a6560946f1886fe1d134568a0eb1d8685609f701","0xebe1595cac3720893846a35b22342b65de299034105933f2bafb52733fae8409","0x542d52d4d15f489918b423a14d03a5b779a33ed191c64f21f50da8b41871c958","0x15937632c43710afc5435993491a01ec5a4bf0cbd4254c7a2df4757b64c4dbe6","0xe417e3be87bd7650ff72eaa79538f420c84a79d8c694513f7696136df34a5cbb","0xd9ed9ff882701dbfb3690bf956883f5a650f8788c8371e2a4ea24af31bfc0874","0xf252151fb0bdb42655dd6c7a49f78825b0abfcf6133c9b77048017cb4db706c3","0xb555a0d142ce000b8804420727879fd3f7aefccc577bcb4c6a05ab01288ace7f","0x60e957fbf8dc0d2507389ff43f697a0fee022b0f21f646f8f8666635004ecad3","0xf10be2914d076976b2a9d0bd1441e91a5d6eb1cc0c5496196bc786450f18b072","0xb9a8c6dd85ea77e66e6b5e3f3d7b303ca42293b62f804d81119a7fa9a552b057","0xb2d02dd0eefc8dc114972bfe2080e23a42d2c42cd8176b7025b23ac25addd540","0xd349878ad159ae98af7db22c0f8e3e2dce982842ca70db1c00954bc05a1a6a5e","0x7033615efb3ab4166378a19bf54d1e147bbd433d32426cfe38e3782fcea9016a","0x0207048caf2734a8c46881200d327cb923e5eb1c6fe0892d5fe040e294a4cc29","0xbcbbee8bc5fd85663c86ce4c353bc6264111f640ffb5a571ac159cedbfc6583b","0x6b1f5bdfedb8ea41222905f046768b23523d68bd14cc5653a14224f9a406c5c7","0x326b04cc1bf34269921a2c010f96759e1859f60be790db80761c3cec9f26114c","0xacbda9c82db88dea633dcd1f1af63c3ee73359fb1551a4902a0caa8af6cd05e8","0x697212323452435fa74468f782070c2273e54388c5280148b4536d75ec7e1f8d","0xf86ac2f0ea1d685edd08d48736fca8a56dfcc42bcfeaafff032325699a83a931","0xe69f1c7f8e6e369e91c901de0f56d15b3cefbd0be644f131292d77af2d31e345","0xf8cbc0be9147644e2d067d16193a88bbd948a0cf38bfa6d8a01a008dde4c0f45","0xea90f725e7469c7fa889b6ea5370b3277135740f006eff5abe50aff60329929d","0x3d45fb1f7088c69661bb3f73158c4f052014461ee09d25c949fb7e4caaad8ba1","0xffd32b4186b890bf53e65e270c25ce578472b61abf8ba4fbcd14ae9319cae8a3","0x18e3b999c0240c03948ea1db6c45e20159145782bd885d826fcb34b5792831ea","0x88117ebd7cc8aa6222d8f78aabdc6ae87b7a51c59788677baa7f633cecd65264","0x0365bfaa4dca151853682c4a3936785e669e1fd3d5e16780b3e18d7c6105c61e","0x32e0dcc62a80a335f9066a2af0fe5b64e9d0592dfeb48853f0605ea8db16905b","0xdc1d3dd56e300eaa668f54cf7f9233dfa2f6e55f6c3bec8dbda466120b09f930"];
        console.log("TXArrF: \n" + TXArrF);
        await federation.methods.initStoreOldFederation(TXArrF).send({
            from: deployer, gasPrice: gasPriceNow  
            //from: deployer, 
         })




}
