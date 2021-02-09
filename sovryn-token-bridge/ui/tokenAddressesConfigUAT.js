const uatAddresses = () => {
    const DAI_TOKEN = { token: 'DAI', name: 'Dai Stablecoin', icon: 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0x6B175474E89094C44Da98b954EedeAC495271d0F/logo.png',
        31:{symbol:'rDAI', address:'0x1116dd716e8039b2860697e847a4200b0114ee2e', decimals:18},
        42:{symbol:'DAI', address:'0x832915943cc51c0620f32dfbaf8b9addb0db25e1', decimals:18}
    };

    const WETH_TOKEN = { token: 'WETH', name: 'Wrapped Ether', icon: 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2/logo.png',
        31:{symbol:'rWETH', address:'0x3746b916f20bce7d105bffff7fcd0363d371734f', decimals:18},
        42:{symbol:'WETH', address:'0xc5cdbf9c69f80fdf0c94aafd0b6b18cec771d7e9', decimals:18},
    };

    const USDT_TOKEN = { token: 'USDT', name: 'Tether USD', icon: 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/0xdAC17F958D2ee523a2206206994597C13D831ec7/logo.png',
        31:{symbol:'rUSDT', address:'0x655154d491bfda302b999554bdcdbfe8d9197d87', decimals:18},
        42:{symbol:'USDT', address:'0x755de969cbc0e7df97eac28933c6a2385c087ca1', decimals:6},
    };

    const RENBTC_TOKEN = { token: 'RenBTC', name: 'Ren BTC', icon:'https://etherscan.io/token/images/renbtc_32.png',
        31:{symbol: 'rRenBTC', address: '0x2de4112ba32f41ae94abf5f4b41c1617709539e0', decimals: 18},
        42:{symbol: 'RenBTC', address: '0xe59ea5df422a143a5a9b86042ec1b0d3e8ce543a', decimals: 8},
    };

    const WBTC_TOKEN = { token: 'WBTC', name: 'Wrapped BTC', icon:'https://etherscan.io/token/images/wbtc_28.png?v=1',
        31:{symbol: 'rWBTC', address: '0xece41dd6ad76da2bc5553c3093f2a55f8d0d2f36', decimals: 18},
        42:{symbol: 'WBTC', address: '0xd871ce15efa071b06104dac4225540f5461d17de', decimals: 8},
    };

    return [DAI_TOKEN, RENBTC_TOKEN, USDT_TOKEN, WBTC_TOKEN, WETH_TOKEN];
}

module.exports = {
    uatAddresses
}
