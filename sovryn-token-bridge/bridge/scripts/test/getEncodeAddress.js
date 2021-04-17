
const anotherAddress = process.argv[6];

// user data encoding another address to send to that address if needed
const userData = web3.eth.abi.encodeParameter("address", anotherAddress);

console.log(userData);