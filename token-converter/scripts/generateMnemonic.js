const bip39 = require('bip39');
const fs = require('fs');

const newMnemonic = bip39.generateMnemonic();

fs.writeFile('mnemonic.key', newMnemonic, function (err) {
    if (err) throw err;
    console.log(`Mnemonic: ${newMnemonic} saved in ./mnemonic.key`);
});
