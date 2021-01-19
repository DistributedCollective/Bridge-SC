const { execSync } = require('child_process');
const { networks } = require('../../bridge/truffle-config')

const sideChainConfig = networks.development
execSync(
    `npx ganache-cli \
        -p ${sideChainConfig.port} \
        -i 5777 \
        --chainId 5777 \
        -g ${sideChainConfig.gasPrice} \
        -l ${sideChainConfig.gas} \
        -b 0.1`,
    { stdio: 'inherit' }
);

