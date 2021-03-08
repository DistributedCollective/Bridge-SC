// This instructions must be executed 1 by 1 in truffle console
// Truffle console MUST BE opened from sovryn-token-bridge/bridge path
// TOKEN can be change by editing the following line:
// ==>>>> const kovanToken = new web3.eth.Contract(constantsHelper.abisObject.bridgeABI, constantsHelper.kovanTokens.RENBTC_TOKEN["42"].address);
// The available tokens are located in:
// ./_constants_helper.js

// Bring all the configuration data
const constantsHelper = require("./scripts/test/_constants_helper");

// Define an account
const account1 = accounts[0];

// Instanciate the bridge
const bridge = new web3.eth.Contract(constantsHelper.abisObject.bridgeABI, constantsHelper.kovanConfig.bridge);

// Instanciate the token
const kovanToken = new web3.eth.Contract(constantsHelper.abisObject.tokenABI, constantsHelper.kovanTokens.RENBTC_TOKEN["42"].address);

// set the decimals 
const kovanTokenDecimals = await kovanToken.methods.decimals().call();

// se the amount to cross: THIS CAN BE EDITED
const amountToCross = 10 * 10 ** parseInt(kovanTokenDecimals);

// another address to receive on the rsk network
const anotherAddress = accounts[3];

// user data encoding another address to send to that address if needed
const userData = web3.eth.abi.encodeParameter("address", anotherAddress);

// Create sell Order by puting the converter as destination
kovanToken.methods.approve(constantsHelper.kovanConfig.bridge, amountToCross.toString()).send({ from: account1 });
bridge.methods.receiveTokensAt(kovanToken._address, amountToCross.toString(), constantsHelper.kovanConfig.converter, userData).send({ from: account1 });

// Receive tokens in a different address
kovanToken.methods.approve(constantsHelper.kovanConfig.bridge, amountToCross.toString()).send({ from: account1 });
bridge.methods.receiveTokensAt(kovanToken._address, amountToCross.toString(), anotherAddress, userData).send({ from: account1 });
