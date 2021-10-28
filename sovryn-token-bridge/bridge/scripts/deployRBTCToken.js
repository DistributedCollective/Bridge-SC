const AlternativeERC20Detailed = artifacts.require("AlternativeERC20Detailed.sol");

module.exports = async callback => {
    try {
        console.log('Deploying tokens ...')
        const tokens = [
            ['RBTC Wrapper', 'WRBTC', 18, '0']
        ];
        const net = process.argv[5];
        console.log("net is:"+ net);

        const gasPrice = await web3.eth.getGasPrice();
        console.log("gas price is: " + gasPrice);
        let gasPriceNow = gasPrice;
        if (net == "mainnet") {
            gasPriceNow = Number.parseInt(gasPrice * 1.5);
        }
        console.log("gas price now is: " + gasPriceNow); 

        const deployer = (await web3.eth.getAccounts())[0];
        console.log(`Deployer address ${deployer} will receive all total supply for each token`)
        const securityPercentage = 1.3;

        const contractPromises = tokens.map(async args => {
            const [name, symbol, decimals, totalSupply] = args;
            const contractArgs = [name, web3.utils.utf8ToHex(symbol), decimals, web3.utils.toWei(totalSupply)];
            const estimatedGas = (await AlternativeERC20Detailed.new.estimateGas(...contractArgs)) * securityPercentage;
            const gas = parseInt(estimatedGas, 10);
            const contract = await AlternativeERC20Detailed.new(...contractArgs, { from: deployer, gas, gasPrice: gasPriceNow  })
            return { token: name, address: contract.address };
        });

        const addresses = await Promise.all(contractPromises);
        console.table(addresses);
    } catch (e) {
        callback(e);
    }
    callback();
}
