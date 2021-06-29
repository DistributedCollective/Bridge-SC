const Federation = artifacts.require("Federation");

// Uncomment relevant 'const multisigAddress' before deploymnet

// /////////////////////
// // Testnet  /////////
// /////////////////////

// // ETH bridge ropsten
// const multiSigAddress = "0x75Ea52aC8219a8F16a2DC6778874943ef2c24C45";
// // ETH bridge rsktestnet
// const multiSigAddress = "0x34055C3f23bFE1d8A45c9ABA53b66ffcA4353600";
const feds = [
    "0xD8bc75a79f6d63fE6E1307139d3BfDc0Bd090e35",
    "0x5fC4D8b1F96A916683954272721Cfe96ED5a3953"
    ];

// // BSC bridge btestnet
// const multiSigAddress = "0x1d8cb60d35fcd42a8bd18d027386be9c0f9c509b";
// // BSC bridge rsktestnet
// const multiSigAddress = "0x7db96fcc37b652ceefa2523c3d25f55d9b9e9973";
// //
// // ETH bridge ropstenDEV
// const multiSigAddress = "0x314d9163dd122368b3c6329b081d2400a9f238d1";
// const feds = [
//     "0xD8bc75a79f6d63fE6E1307139d3BfDc0Bd090e35",
//     "0x5fC4D8b1F96A916683954272721Cfe96ED5a3953"
//     ];

// /////////////////////
// // Mainnet  /////////
// /////////////////////

// // ETH bridge mainnet
// const multiSigAddress = "0x062c74f9d27b1178bb76186c1756128ccb3ccd2e";
// // ETH bridge rskmainnet
// const multiSigAddress = "0xB64322e10b5aE1BE121B8Bb0dead560c53d9Dbc3";
// const feds = [
        // "0xa420512B06B23d14Beb25Bae524a9B5F8789c45C",
        // "0xcd1b561207e20a7ccbcf004bb0a4bc897ba8f2ee",
        // "0x778898877A3277F7306b19879F426A86d078E115",
        // "0x66d0a5238340bD1589eF56b1e39F73Df32815285",
        // "0x5E7847e22DFb937672815Cdfe28724bbdf5773fd"
        // ];


// // BSC bridge bmainnet
// const multiSigAddress = "0xec3fabc3517e64e07669dd1d2d673f466f93a328";
// // BSC bridge rskmainnet
// const multiSigAddress = "0xee9ea57555d9533d71f6f77e0e480961f068a6c5";
// const feds = [
        // "0xf963C7B3D8f6dAB6d1176702B94Ecdb75916770A",
        // "0x4b03E69D6962649573f2747c04F2dd9aB5494Cdb",
        // "0x642aA4Ab1F29c0E8877A99312494E2A0b623a682",
        // "0x43e9FDa4dAA6040AC528aEba48D318b62Cf09377",
        // "0x81Bc3b08FC3531211AFd95B6011375F808b861cF"
        // ];

let federation;

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
        if(networkName == "mainnet" || networkName == "bmainnet" ||networkName == "rskmainnet") {
            federation = await deployer.deploy(Federation, [feds[0], feds[1], feds[2], feds[3], feds[4]], 1);
        }
        else if(networkName == "ropsten" || networkName == "rsktestnet" || networkName == "btestnet") {
            federation = await deployer.deploy(Federation, [accounts[0], feds[0], feds[1]], 1);
        }
        else {
            federation = await deployer.deploy(Federation, [accounts[0]], 1);
        }
// TransferOwnership moved to Upgrade script (to execute getFederationState.js before multisig ownership)
        //await federation.transferOwnership(multiSigAddress);
        });
};
