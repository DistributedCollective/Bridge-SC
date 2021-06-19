const Erc777Converter = artifacts.require("Erc777Converter");

contract(
    "Erc777Converter IERC777 compatible",
    ([_, operator, from, to]) => {
        describe("has implemented tokensReceived", async () => {
            it("call to tokensReceived should not fail", async () => {
                const converter = await Erc777Converter.deployed();
                const data = Buffer.from("");
                await converter.tokensReceived(operator, from, to, 10, data, data)
            })
        });
    }
);
