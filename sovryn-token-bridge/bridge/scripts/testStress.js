const MultiSigWallet = artifacts.require("MultiSigWallet");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v3 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const Deployer = process.argv[6];
        if (!Deployer)
            console.error('You need to pass Deployer arg');
        
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v3 = new web3.eth.Contract(Bridge_v3.abi, bridgeAddress);

        const deployer = (await web3.eth.getAccounts())[Deployer];

        console.log(`Run Stress Test by deployer ${deployer}`);
        const extraData = Buffer.from('');
        const amountToSend = '10000000000000000';

        console.log('Bridge address', bridgeAddress);
        let sendEth;
        for (let i = 0;i < 25; i++) { 
            sendEth = await bridge_v3.methods.recieveEthAt(deployer, extraData).send({from: deployer, value: amountToSend});
            console.log('sendEth: ' + i );
        };    
        
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
