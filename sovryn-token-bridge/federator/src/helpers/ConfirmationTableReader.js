const defaultConfirmationTable = require('../../config/confirmation_table.json')

class ConfirmationTableReader {

    constructor(chainId, _confirmationTable = defaultConfirmationTable) {
        this.confirmationTable = _confirmationTable[chainId];
    }

    getConfirmations(token, amount) {
        const confirmationArray = this.confirmationTable[token];

        if (!confirmationArray)
            throw Error("Invalid token");

        confirmationArray.sort((a, b) => a.amount - b.amount)

        let confirmations = this.getMinConfirmation();
        let i = 0;
        while (i < confirmationArray.length && confirmationArray[i].amount <= amount) {
            confirmations = confirmationArray[i].confirmations;
            i++;
        }

        return confirmations;
    }

    getMinConfirmation() {
        return this.confirmationTable.minConfirmation;
    }

}

module.exports = {
    ConfirmationTableReader
}
