const { createLogger, format, transports, config } = require('winston')
const Web3 = require('web3')

const ethThreshold = 0.8
const bnbThreshold = 0.1
const rbtcThreshold = 0.001

var ethWallets = ['0xa420512B06B23d14Beb25Bae524a9B5F8789c45C', '0xcd1b561207e20a7ccbcf004bb0a4bc897ba8f2ee', '0x778898877A3277F7306b19879F426A86d078E115', '0x66d0a5238340bD1589eF56b1e39F73Df32815285', '0x5E7847e22DFb937672815Cdfe28724bbdf5773fd']
var bscWallets = ['0xf963C7B3D8f6dAB6d1176702B94Ecdb75916770A', '0x4b03E69D6962649573f2747c04F2dd9aB5494Cdb', '0x642aA4Ab1F29c0E8877A99312494E2A0b623a682', '0x43e9FDa4dAA6040AC528aEba48D318b62Cf09377', '0x81Bc3b08FC3531211AFd95B6011375F808b861cF']
var rskWallets = ethWallets.concat(bscWallets)

const ethWeb3 = new Web3(new Web3.providers.HttpProvider('https://mainnet.infura.io/v3/728946296ea64626941bb3d120d16333'))
const bscWeb3 = new Web3(new Web3.providers.HttpProvider('https://bsc-dataseed.binance.org/'))
const rskWeb3 = new Web3(new Web3.providers.HttpProvider('https://mainnet.sovryn.app/'))

FgRed = '\x1b[31m'
FgWhite = '\x1b[37m'
const checkerlogger = createLogger({
	transports: [new transports.Console()],
})

const checkWalletsBalance = (wallets, web3object, blockchainToken, tokenThreshold) => {
	wallets.forEach(function (wallet) {
		web3object.eth.getBalance(wallet, function (err, result) {
			if (err) {
				console.log(err)
			} else {
				const amount = web3object.utils.fromWei(result, 'ether')
				checkerlogger.info('checking ' + blockchainToken + ' wallet: ' + wallet + ' funds left: ' + amount + ' threshold = ' + tokenThreshold)
				if (Math.round(amount * 1000) < Math.round(tokenThreshold * 1000)) {
					console.log(FgRed + 'ERROR: wallet has ' + amount + ' ' + blockchainToken + ', ' + wallet + ' - lack of funds' + FgWhite)
				}
			}
		})
	})
}

checkWalletsBalance(ethWallets, ethWeb3, 'ETH', ethThreshold)
checkWalletsBalance(bscWallets, bscWeb3, 'BNB', bnbThreshold)
checkWalletsBalance(rskWallets, rskWeb3, 'RBTC', rbtcThreshold)
