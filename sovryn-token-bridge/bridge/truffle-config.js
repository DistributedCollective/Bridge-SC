/*
 * NB: since truffle-hdwallet-provider 0.0.5 you must wrap HDWallet providers in a
 * function when declaring them. Failure to do so will cause commands to hang. ex:
 * ```
 * mainnet: {
 *     provider: function() {
 *       return new HDWalletProvider(mnemonic, 'https://mainnet.infura.io/<infura-key>')
 *     },
 *     network_id: '1',
 *     gas: 4500000,
 *     gasPrice: 10000000000,
 *   },
 */
const HDWalletProvider = require('@truffle/hdwallet-provider');
const fs = require('fs');
const Web3 = require('web3');

let MNEMONIC = fs.existsSync('../../../../bridgeKey/mnemonic.key')
    ? fs.readFileSync('../../../../bridgeKey/mnemonic.key', { encoding: 'utf8' }).trim()
    : ''; // Your metamask's recovery words
const INFURA_API_KEY = fs.existsSync('../../../../bridgeKey/infura.key')
    ? fs.readFileSync('../../../../bridgeKey/infura.key', { encoding: 'utf8' }).trim()
    : ''; // Your Infura API Key after its registration
const secrets = fs.existsSync('../../../../bridgeKeyMain/.secrets')
    ? JSON.parse(
          fs
              .readFileSync('../../../../bridgeKeyMain/.secrets')
              .toString()
              .trim(),
      )
    : '';

module.exports = {
    // See <http://truffleframework.com/docs/advanced/configuration>
    // to customize your Truffle configuration!met
    networks: {
        //Ganache
        development: {
            host: '127.0.0.1',
            port: 8545,
            network_id: '*',
            gas: 6721975,
            gasPrice: 200000000,
        },
        //RSK
        rskregtest: {
            host: '127.0.0.1',
            port: 4444,
            network_id: '33',
            gas: 6300000,
            gasPrice: 60000000, // 0.06 gwei
        },
        soliditycoverage: {
            host: 'localhost',
            network_id: '*',
            port: 8555, // <-- If you change this, also set the port option in .solcover.js.
            gas: 0xfffffffffff, // <-- Use this high gas value
            gasPrice: 0x01, // <-- Use this low gas price
        },
        rsktestnet: {
            provider: () =>
                //new HDWalletProvider(MNEMONIC, "http://45.79.214.38"),
                new HDWalletProvider(MNEMONIC, 'wss://testnet.sovryn.app/websocket'),
            network_id: 31,
            gas: 6300000,
            gasPrice: 70000000, // 0.07 gwei
            skipDryRun: true,
        },
        rskmainnet: {
            provider: () =>
            //  new HDWalletProvider(MNEMONIC, "https://public-node.rsk.co"),
            // new HDWalletProvider(secrets.seed, "wss://mainnet.sovryn.app/ws"),
            new HDWalletProvider(secrets.seed, "http://18.221.155.102:4444/"),
            // new HDWalletProvider(secrets.seed, "https://mainnet.sovryn.app/rpc"),
            //  new HDWalletProvider(secrets.seed, "https://mainnet2.sovryn.app/rpc"),
            //new HDWalletProvider(secrets.seed, new Web3.providers.WebSocketProvider("wss://mainnet.sovryn.app/ws")),
            network_id: 30,
            gas: 6800000,
            gasPrice: 65500000, // 0.065 gwei
            skipDryRun: true
          },
              //Ethereum
        sepolia: {
            provider: () =>
                new HDWalletProvider(MNEMONIC, 'wss://sepolia.infura.io/ws/v3/' + INFURA_API_KEY),
            //provider: () => new HDWalletProvider(MNEMONIC, "wss://ropsten.infura.io/ws/v3/" + INFURA_API_KEY),
            network_id: 11155111,
            networkCheckTimeout: 1e9,
            timeoutBlocks: 500000,
            gas: 6300000,
            //gasPrice: 10000000000,
            gasPrice: 70,
            skipDryRun: true,
        },
        ropsten: {
            provider: () =>
                new HDWalletProvider(MNEMONIC, 'wss://ropsten.infura.io/ws/v3/' + INFURA_API_KEY),
            //provider: () => new HDWalletProvider(MNEMONIC, "wss://ropsten.infura.io/ws/v3/" + INFURA_API_KEY),
            network_id: 3,
            networkCheckTimeout: 1e9,
            timeoutBlocks: 500000,
            gas: 6300000,
            gasPrice: 10000000000,
            skipDryRun: true,
        },
        kovan: {
            provider: () =>
                new HDWalletProvider(MNEMONIC, 'https://kovan.infura.io/v3/' + INFURA_API_KEY),
            network_id: 42,
            gas: 6300000,
            gasPrice: 10000000000,
            skipDryRun: true,
        },
        rinkeby: {
            provider: () =>
                new HDWalletProvider(MNEMONIC, 'https://rinkeby.infura.io/v3/' + INFURA_API_KEY),
            network_id: 4,
            gas: 6300000,
            gasPrice: 10000000000,
            skipDryRun: true,
        },
        mainnet: {
            //provider: () => new HDWalletProvider(MNEMONIC, "https://mainnet.infura.io/v3/" + INFURA_API_KEY),
            //provider: () => new HDWalletProvider(secrets.seed, "https://mainnet.infura.io/v3/" + secrets.projectId),
            provider: () =>
                new HDWalletProvider(
                    secrets.seed,
                    'wss://mainnet.infura.io/ws/v3/' + secrets.projectId,
                ),
            network_id: 1,
            networkCheckTimeout: 1e9,
            timeoutBlocks: 500000,
            gas: 6700000,
            gasPrice: 50000000000, //50 GWei
            skipDryRun: true,
        },
        //Binance
        btestnet: {
            //provider: () => new HDWalletProvider(MNEMONIC, "https://data-seed-prebsc-1-s1.binance.org:8545/"),
            provider: () =>
                new HDWalletProvider(MNEMONIC, 'https://data-seed-prebsc-2-s3.binance.org:8545/'),
            network_id: 97,
            gas: 6300000,
            confirmations: 3,
            timeoutBlocks: 200,
            skipDryRun: true,
        },
        bmainnet: {
            //provider: () => new HDWalletProvider(secrets.seed, `https://bsc-dataseed1.binance.org`),
            //provider: () => new HDWalletProvider(secrets.seed, `https://bsc-dataseed1.defibit.io/`),
            provider: () => new HDWalletProvider(secrets.seed, `http://bscmainnet1.sovryn.app:8545/`),
            network_id: 56,
            gas: 6300000,
            confirmations: 6,
            timeoutBlocks: 200,
            skipDryRun: true
          },      
        localA: {
            host: '127.0.0.1',
            port: 8545,
            network_id: '*',
        },
        localB: {
            host: '127.0.0.1',
            port: 8546,
            network_id: '*',
        },
    },
    plugins: ['truffle-contract-size', 'solidity-coverage'],
    mocha: {
        // reporter: 'eth-gas-reporter',
        //reporterOptions : { ... } // See options below
    },
    compilers: {
        solc: {
            version: '0.5.17',
            settings: {
                evmVersion: 'istanbul',
                optimizer: {
                    enabled: true,
                    // Optimize for how many times you intend to run the code.
                    // Lower values will optimize more for initial deployment cost, higher
                    // values will optimize more for high-frequency usage.
                    runs: 200,
                },
            },
        },
    },
};
