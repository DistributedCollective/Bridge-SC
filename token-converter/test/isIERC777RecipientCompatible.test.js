const ConverterContract = artifacts.require("Converter");

contract(
    "Converter IERC777 compatible",
    ([_, operator, from, to]) => {
        describe("has implemented tokensReceived", async () => {
            it("call to tokensReceived should not fail", async () => {
                const converter = await ConverterContract.deployed();
                const data = Buffer.from("");
                await converter.tokensReceived(operator, from, to, 10, data, data)
            })
        });
    }
);
