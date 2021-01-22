const { confirmationTable: defaultConfirmationTable } = require('../../config/config')

class ConfirmationTableReader {

    constructor(chainId, _confirmationTable = defaultConfirmationTable) {
        this._validateTable(JSON.parse(JSON.stringify(_confirmationTable)));
        if (!Object.keys(_confirmationTable).includes(chainId.toString()))
            throw new Error("Invalid chainId");
        this.confirmationTable = _confirmationTable[chainId];
    }

    getConfirmations(token, amount) {
        if (amount < 0)
            throw new Error("Negative amount");

        const confirmationArray = this.confirmationTable[token];

        if (!confirmationArray)
            return this.confirmationTable.default;

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

    _validateTable(confirmationTable) {
        for (const [chainId, table] of Object.entries(confirmationTable)) {
            if (parseInt(chainId) < 0)
                throw new Error(`ChainId (${chainId}) must be positive`);

            if (!table.default)
                throw new Error("The table must have a default value");

            const minConfirmation = table.minConfirmation;
            if (!minConfirmation)
                throw new Error(`minConfirmation is not defined for chainId ${chainId}`);

            delete table.minConfirmation

            for (const [, confirmationArray] of Object.entries(table)) {
                const arrayMin = confirmationArray
                    .reduce((prev, curr) => prev.confirmations < curr.confirmations ? prev : curr);

                if (arrayMin.confirmations < minConfirmation)
                    throw new Error("minConfirmation attribute is not the minimum confirmation in the table");
            }
        }
    }
}

module.exports = {
    ConfirmationTableReader
}
