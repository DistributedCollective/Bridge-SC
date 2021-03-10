// This instructions must be executed 1 by 1 in truffle console
// Truffle console MUST BE opened from sovryn-token-bridge/bridge path
// TOKEN can be change by editing the following line:
// ==>>>> const rskToken = new web3.eth.Contract(constantsHelper.abisObject.bridgeABI, constantsHelper.rskTokens.rRENBTC_TOKEN["31"].address);
// The available tokens are located in:
// ./_constants_helper.js

// Bring all the configuration data
const constantsHelper = require("./scripts/test/_constants_helper");

// Define an account
const account1 = accounts[0];

// Instanciate the bridge
bridge = new web3.eth.Contract(constantsHelper.abisObject.bridgeABI, constantsHelper.rskConfig.bridge);

// Instanciate the token
rskToken = new web3.eth.Contract(constantsHelper.abisObject.tokenABI, constantsHelper.rskTokens.rRENBTC_TOKEN["31"].address);

// set the decimals 
rskTokenDecimals = await rskToken.methods.decimals().call();

// se the amount to cross: THIS CAN BE EDITED
amountToCross = 1 * 10 ** parseInt(rskTokenDecimals);

// another address to receive on the eth network
anotherAddress = '0x02c3e04E90DE8B5ba93C6f1fec8124F2c177ba8A';

// user data encoding another address to send to that address if needed
userData = web3.eth.abi.encodeParameter("address", anotherAddress);

// Receive tokens in a different address
rskToken.methods.approve(constantsHelper.rskConfig.bridge, amountToCross.toString()).send({ from: account1 });
bridge.methods.receiveTokensAt(rskToken._address, amountToCross.toString(), anotherAddress, userData).send({ from: account1 });
