const MultiSigWallet = artifacts.require("MultiSigWallet");
const AllowTokens = artifacts.require("AllowTokens");
const Bridge = artifacts.require("Bridge_v0");
const Bridge_v3 = artifacts.require("Bridge");

module.exports = async callback => {
    try {
        const token = process.argv[6];
        const feeArg = process.argv[7];
        const minArg = process.argv[8];
        if (!token || !feeArg || !minArg)
            console.error('need to pass token address, fee, min. Example: npx truffle exec ./scripts/setFeePerToken.js --network ropsten <token address> <fee in token decimal units> <min in token decimal units>');

        //const fee = web3.utils.toBN(feeArg);
        const fee = feeArg;
            console.log('Fee is: ' + fee);

        const minAmount = minArg;
        console.log('Min is: ' + minAmount);
        

        const net = process.argv[5];
        console.log("net is:"+ net);

        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (net == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 

        //const allowTokens = await AllowTokens.deployed();
        const bridge_v0 = await Bridge.deployed();
        const bridgeAddress = bridge_v0.address;
        const bridge_v3 = new web3.eth.Contract(Bridge_v3.abi, bridgeAddress);

        const deployer = (await web3.eth.getAccounts())[0];

        console.log(await bridge_v3.methods.allowTokens().call());
        const allowTokensAddress = await bridge_v3.methods.allowTokens().call();
        const allowTokens = await AllowTokens.at(allowTokensAddress);
        console.log(`Configuring AllowTokens contract ${allowTokens.address}`);

        const multiSigAddress = await allowTokens.contract.methods.owner().call();
        const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multiSigAddress);

        console.log(`Configuring fee ${fee} and minAmount ${minAmount} for token ${token} from address ${deployer}`);
        console.log('Bridge address', bridgeAddress);
        const setFeeAndMinMethodData = allowTokens.contract.methods.setFeeAndMinPerToken(token,fee,minAmount).encodeABI();
        
        //const multisigAddress = await bridge_v3.methods.owner().call();
        //const multiSig = new web3.eth.Contract(MultiSigWallet.abi, multisigAddress);
        console.log('MultiSig address', multiSigAddress);
        const result = await multiSig.methods.submitTransaction(allowTokens.address, 0, setFeeAndMinMethodData).send({ from: deployer, gas: 300000 , gasPrice: gasPriceNow});

        console.log('Fee And Min per token were updated');
        console.log(result)
    } catch (e) {
        console.error(e);
        callback(e);
    }
    callback();
};
