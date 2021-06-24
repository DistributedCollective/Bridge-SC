//const MultiSigWallet = artifacts.require("MultiSigWallet");
const AllowTokens = artifacts.require("AllowTokens");

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            //const multiSig = await MultiSigWallet.deployed();
           // deployer = accounts[0];
            const multiSigAddress = "0x314d9163dd122368b3c6329b081d2400a9f238d1";
           // const multiSig = new web3.eth.Contract(multisigAbi, multiSigAddress, {from: deployer});
        
           return deployer.deploy(AllowTokens, multiSigAddress);
        });
};