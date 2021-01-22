const {describe, it, beforeEach, expect} = global;

const testConfig = require("../config.json")

const {ConfirmationTableReader} = require("../../src/helpers/ConfirmationTableReader");

describe("ConfirmationTableReader module tests", () => {
    describe("creation tests", () => {
        it("should work if the chainId is in the table", () => {
            const validChainId = 1;
            const ctr = new ConfirmationTableReader(validChainId, testConfig.confirmationTable);
            expect(ctr).toBeDefined();
        });

        it("should fail if the chainId is not in the table", () => {
            const invalidChainId = 9545;
            expect(() => {
                new ConfirmationTableReader(invalidChainId, testConfig.confirmationTable)
            }).toThrow();
        });

        it("should fail if the table have a malformed minConfirmation", () => {
            const validChainId = 1;

            const malformedTable = JSON.parse(JSON.stringify(testConfig.confirmationTable));
            malformedTable[validChainId]["minConfirmation"] = 15000;

            expect(() => {
                new ConfirmationTableReader(validChainId, malformedTable)
            }).toThrow();
        });

        it("should fail if the table doesn't have a minConfirmation attribute", () => {
            const validChainId = 1;

            const malformedTable = JSON.parse(JSON.stringify(testConfig.confirmationTable));
            delete malformedTable[validChainId]["minConfirmation"];

            expect(() => {
                new ConfirmationTableReader(validChainId, malformedTable)
            }).toThrow();
        });

        it("should fail if the table doesn't have a default attribute", () => {
            const validChainId = 1;

            const malformedTable = JSON.parse(JSON.stringify(testConfig.confirmationTable));
            delete malformedTable[validChainId]["default"];

            expect(() => {
                new ConfirmationTableReader(validChainId, malformedTable)
            }).toThrow();
        });
    });

    describe("getMinConfirmation tests", () => {
        const chainId = 42;
        const confirmationTable = testConfig.confirmationTable;
        let ctr;

        beforeEach(() => {
            ctr = new ConfirmationTableReader(chainId, confirmationTable);
        });

        it("should return the minimum value of the table", () => {
            const expectedMinVal = 10;
            const minVal = ctr.getMinConfirmation();

            expect(minVal).toEqual(expectedMinVal);
        });
    });

    describe("getConfirmations tests", () => {
        const chainId = 42;
        const symbol = "TEST"
        const confirmationTable = testConfig.confirmationTable;
        let ctr;

        beforeEach(() => {
            ctr = new ConfirmationTableReader(chainId, confirmationTable);
        });

        it("should return the minimum value of the table if the amount is 0", () => {
            const expectedMinVal = 500;
            const amount = 0;
            const confirmations = ctr.getConfirmations(symbol, amount);

            expect(confirmations).toEqual(expectedMinVal);
        });

        it("should throw error if the amount is negative", () => {
            expect(() => {
                const negativeAmount = -20;
                ctr.getConfirmations(symbol, negativeAmount);
            }).toThrow();
        });

        it("should return the maximum value of the table if the amount and the max amount are the same", () => {
            const expectedMaxConfirmation = 8000;
            const maxAmount = 100;
            const confirmations = ctr.getConfirmations(symbol, maxAmount);

            expect(confirmations).toEqual(expectedMaxConfirmation);
        });

        it("should return the maximum value of the table if the amount higher than max amount", () => {
            const expectedMaxConfirmation = 8000;
            const maxAmount = 100;
            const confirmations = ctr.getConfirmations(symbol, maxAmount + 20);

            expect(confirmations).toEqual(expectedMaxConfirmation);
        });

        it("should return the range confirmation if the amount is between", () => {
            const expectedConfirmation = 500;
            const amount = 20;
            const confirmations = ctr.getConfirmations(symbol, amount);

            expect(confirmations).toEqual(expectedConfirmation);
        });

        it("should return the default attribute if the symbol is not in the table", () => {
            const amount = 20;
            const invalidSymbol = "NOTEST";
            const expectedDefaultConfirmation = testConfig.confirmationTable[chainId].default;
            const confirmations = ctr.getConfirmations(invalidSymbol, amount);
            expect(confirmations).toEqual(expectedDefaultConfirmation);
        });
    });
});
