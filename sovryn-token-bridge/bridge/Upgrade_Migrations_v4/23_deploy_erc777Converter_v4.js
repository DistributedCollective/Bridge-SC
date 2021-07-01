const Erc777Converter = artifacts.require("Erc777Converter");

// Uncomment relevant 'const multisigAddress' before deploymnet

// /////////////////////
// // Testnet  /////////
// /////////////////////
// // ETH bridge ropsten
 const multiSigAddress = "0x75Ea52aC8219a8F16a2DC6778874943ef2c24C45";
// // ETH bridge rsktestnet
// const multiSigAddress = "0x34055C3f23bFE1d8A45c9ABA53b66ffcA4353600";
// //
// // BSC bridge btestnet
// const multiSigAddress = "0x1d8cb60d35fcd42a8bd18d027386be9c0f9c509b";
// // BSC bridge rsktestnet
// const multiSigAddress = "0x7db96fcc37b652ceefa2523c3d25f55d9b9e9973";
// //
// // ETH bridge ropstenDEV
// const multiSigAddress = "0x314d9163dd122368b3c6329b081d2400a9f238d1";

// /////////////////////
// // Mainnet  /////////
// /////////////////////
// // ETH bridge mainnet
// const multiSigAddress = "0x062c74f9d27b1178bb76186c1756128ccb3ccd2e";
// // ETH bridge rskmainnet
// const multiSigAddress = "0xB64322e10b5aE1BE121B8Bb0dead560c53d9Dbc3";
// //
// // BSC bridge bmainnet
// const multiSigAddress = "0xec3fabc3517e64e07669dd1d2d673f466f93a328";
// // BSC bridge rskmainnet
// const multiSigAddress = "0xee9ea57555d9533d71f6f77e0e480961f068a6c5";

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const erc777Converter = await deployer.deploy(Erc777Converter);
            // Moved to upgradeBridge_v4.js script
            // await erc777Converter.transferOwnership(multiSigAddress);
        });
};
