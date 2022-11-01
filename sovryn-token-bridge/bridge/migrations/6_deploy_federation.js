const Federation = artifacts.require("Federation");

module.exports = function(deployer, networkName, accounts) {
    deployer
        .then(async () => {
            const federators = [accounts[2], accounts[3], accounts[4]];
            const required = 2;
            return deployer.deploy(Federation, federators, required);

            // Replace with below line to use multiple federators
            // return deployer.deploy(Federation, [accounts[0], accounts[1], accounts[2]], 3);
        });
};