// This instructions must be executed 1 by 1 in truffle console
// Truffle console MUST BE opened from sovryn-token-bridge/bridge path
// numOrder holds the last order made, it could happen this order does not exists because it was completed
// To view the orders, the sellOrdersIds/sellOrdersAmounts INDEX can be edited
// To purchase a specific order the amountToBuy variable can be edited
// The tokensReceiverAddress can also be edited to a known address in eth network


// Bring all the configuration data
const constantsHelper = require("./scripts/test/_constants_helper");

// Define an account
const account1 = accounts[0];

// Instanciate the converter
const converter = new web3.eth.Contract(constantsHelper.abisObject.converterABI, constantsHelper.rskConfig.converter);

// get last NumOrder
const lastNumOrder = await converter.methods.numOrder().call();

// get order ids and amounts
sellOrders = await converter.methods.getSellOrders(from = 1, lastNumOrder).call();
console.log(sellOrders);

// slice the response to print it 
sellOrdersIds = sellOrders[0].slice();
sellOrdersAmounts = sellOrders[1].slice();

// See order 1
console.log('\nOrder ID: ' + sellOrdersIds[0].toString() + ' || Amount: ' + sellOrdersAmounts[0].toString());
// See order 2
console.log('\nOrder ID: ' + sellOrdersIds[1].toString() + ' || Amount: ' + sellOrdersAmounts[1].toString());

// Build the extradata
const extraData = Buffer.from('');

// Select the order to purchase
const orderId = 1;

// Set the amount
const amountToBuy = '20000000000000000';

// Set the receiever
const tokensReceiverAddress = accounts[5];

// Perform the transaction
converter.methods.takeSellOrder(orderId, amountToBuy, tokensReceiverAddress, extraData).send({ value: amountToBuy, from: account1});