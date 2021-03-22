const AlternativeERC20Detailed = artifacts.require("AlternativeERC20Detailed.sol");

module.exports = async callback => {
    try {
        console.log('Deploying tokens ...')
        const tokens = [
            ['Doc Stablecoin', 'DOCF', 18, '100000'],
            //['Dai Stablecoin', 'DAI', 18, '10000000000000000'],
            //['Wrapped Ether', 'WETH', 18, '10000000000000000'],
            //['Wrapped BTC', 'WBTC', 8, '10000000000000000'],
            //['RenBTC', 'renBTC', 8, '10000000000000000'],
            ['Tether USD', 'USDTF', 6, '100000'],
        ];

        const deployer = (await web3.eth.getAccounts())[0];
        console.log(`Deployer address ${deployer} will receive all total supply for each token`)
        const securityPercentage = 1.3;

        const contractPromises = tokens.map(async args => {
            const [name, symbol, decimals, totalSupply] = args;
            const contractArgs = [name, web3.utils.utf8ToHex(symbol), decimals, web3.utils.toWei(totalSupply)];
            const estimatedGas = (await AlternativeERC20Detailed.new.estimateGas(...contractArgs)) * securityPercentage;
            const gas = parseInt(estimatedGas, 10);
            const contract = await AlternativeERC20Detailed.new(...contractArgs, { from: deployer, gas })
            return { token: name, address: contract.address };
        });

        const addresses = await Promise.all(contractPromises);
        console.table(addresses);
    } catch (e) {
        callback(e);
    }
    callback();
}
