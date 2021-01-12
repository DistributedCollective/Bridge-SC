const UtilsLib = artifacts.require('./Utils');
const MainToken = artifacts.require('./MainToken');
const AlternativeERC20Detailed = artifacts.require('./AlternativeERC20Detailed');
const SideToken = artifacts.require('./SideToken');

const BN = web3.utils.BN;
const utils = require('./utils');
const { expectThrow } = require('./utils');

contract('Utils Lib', async function (accounts) {
    const owner = accounts[0];

    beforeEach(async function () {
        this.utilsLib = await UtilsLib.new();
    });

    describe('decimals conversion', async function () {
        it('decimals to granularity', async function () {
            let resultGranularity = await this.utilsLib.decimalsToGranularity(18);
            assert.equal(resultGranularity.toString(), '1');
            resultGranularity = await this.utilsLib.decimalsToGranularity(9);
            assert.equal(resultGranularity.toString(), '1000000000');
            resultGranularity = await this.utilsLib.decimalsToGranularity(6);
            assert.equal(resultGranularity.toString(), '1000000000000');
            resultGranularity = await this.utilsLib.decimalsToGranularity(0);
            assert.equal(resultGranularity.toString(), new BN('1000000000000000000').toString());
        });

        it('decimals to granularity should fail over 18 decimals', async function () {
            await expectThrow(this.utilsLib.decimalsToGranularity(19));
        });

        it('granularity to decimals', async function () {
            for(var i = 0; i < 19; i++) {
                let resultDecimals = await this.utilsLib.granularityToDecimals((10**i).toString());
                assert.equal(resultDecimals.toString(), (18-i).toString());
            }
        });

        it('granularity to decimals should fail over 18 decimals', async function () {
            await expectThrow(this.utilsLib.granularityToDecimals((10**19).toString()));
        });
    });
    describe('getDecimals', async function () {
        it('from uint8', async function () {
            let token = await MainToken.new("MAIN", "MAIN", 18, web3.utils.toWei('10000'), { from: owner });
            let resultDecimals = await this.utilsLib.getDecimals(token.address);
            assert.equal(resultDecimals, 18);
            token = await MainToken.new("MAIN", "MAIN", 0, web3.utils.toWei('10000'), { from: owner });
            resultDecimals = await this.utilsLib.getDecimals(token.address);
            assert.equal(resultDecimals, 0);
        });

        it('Throw if is not a contract', async function () {
            await utils.expectThrow(this.utilsLib.getDecimals(owner));
        });

        it('Throw if does not have decimals()', async function () {
            await utils.expectThrow(this.utilsLib.getDecimals(this.utilsLib.address));
        });

        it('Throw if bigger than 18', async function () {
            let token = await MainToken.new("MAIN", "MAIN", 19, web3.utils.toWei('10000'), { from: owner });
            await utils.expectThrow(this.utilsLib.getDecimals(token.address));
        });

        it('from  uint256', async function () {
            let token = await AlternativeERC20Detailed.new("ALT", utils.ascii_to_hexa("ALT"), 18, web3.utils.toWei('10000'), { from: owner });
            let resultGranularity = await this.utilsLib.getDecimals(token.address);
            assert.equal(resultGranularity, 18);
            token = await AlternativeERC20Detailed.new("ALT", utils.ascii_to_hexa("ALT"), 0, web3.utils.toWei('10000'), { from: owner });
            resultGranularity = await this.utilsLib.getDecimals(token.address);
            assert.equal(resultGranularity, 0);
        });
    });

    describe('getSymbol', async function () {
        it('from string', async function () {
            let symbol = "MAIN"
            let token = await MainToken.new("MAIN", symbol, 18, web3.utils.toWei('10000'), { from: owner });
            let resultSymbol = await this.utilsLib.getSymbol(token.address);
            assert.equal(resultSymbol, symbol);
        });

        it('Throw if is not a contract', async function () {
            await utils.expectThrow(this.utilsLib.getSymbol(owner));
        });

        it('Throw if does not have symbol()', async function () {
            await utils.expectThrow(this.utilsLib.getSymbol(this.utilsLib.address));
        });

        it('Throw if empty', async function () {
            let token = await MainToken.new("MAIN", "", 18, web3.utils.toWei('10000'), { from: owner });
            await utils.expectThrow(this.utilsLib.getSymbol(token.address));
        });

        it('from  bytes32', async function () {
            let symbol = "ALT";
            let token = await AlternativeERC20Detailed.new("ALT", utils.ascii_to_hexa(symbol), 18, web3.utils.toWei('10000'), { from: owner });
            let resultSymbol = await this.utilsLib.getSymbol(token.address);
            assert.equal(resultSymbol, symbol);
        });
    });

    describe('getGranularity', async function () {
        it('from ERC777', async function () {
            let granularity = '1';
            let token = await SideToken.new("SIDE", "SIDE", owner, granularity);
            let resultGranularity = await this.utilsLib.getGranularity(token.address);
            assert.equal(resultGranularity.toString(), granularity);

            granularity = '1000000000000000000';
            token = await SideToken.new("SIDE", "SIDE", owner, granularity);
            resultGranularity = await this.utilsLib.getGranularity(token.address);
            assert.equal(resultGranularity.toString(), granularity);
        });

        it('granularity = 1 if does not have granularity()', async function () {
            let result = await this.utilsLib.getGranularity(this.utilsLib.address);
            assert.equal(result, '1');
        });

        it('Throw if bigger than 18 decimals', async function () {
            let granularity = '10000000000000000000';
            let token = await SideToken.new("SIDE", "SIDE", owner, granularity);
            await utils.expectThrow(this.utilsLib.getGranularity(token.address));
        });

        it('from  ERC20 gives 1', async function () {
            let token = await MainToken.new("MAIN", "MAIN", 9, web3.utils.toWei('1000000'), { from: owner });
            let resultGranularity = await this.utilsLib.getGranularity(token.address);
            assert.equal(resultGranularity, '1');
        });
    });

    it('should calculate granularity and amount ERC20', async function () {
        let decimals = 9;
        let amount = 1000;
        let granularity = '1';

        let result = await this.utilsLib.calculateGranularityAndAmount(decimals, granularity, amount);

        assert.equal(result.calculatedGranularity.toString(), (10**decimals).toString());
        assert.equal(result.formattedAmount.toString(), (amount*(10**(18-decimals))).toString());
    });

    it('should calculate granularity and amount ERC777', async function () {
        let decimals = 18;
        let amount = 1000;
        let granularity = 100;

        let result = await this.utilsLib.calculateGranularityAndAmount(decimals, granularity, amount);

        assert.equal(result.calculatedGranularity.toString(), granularity);
        assert.equal(result.formattedAmount.toString(), amount.toString());
    });

    it('should calculate Decimals and amount', async function () {
        let decimals = 16;
        let amount = 10000;
        let granularity = 100;
        let token = await MainToken.new("MAIN", "MAIN", decimals, web3.utils.toWei('1000000'), { from: owner });

        let result = await this.utilsLib.calculateDecimalsAndAmount(token.address, granularity, amount);

        assert.equal(result.calculatedDecimals.toString(), decimals.toString());
        assert.equal(result.formattedAmount.toString(), (amount / granularity).toString());
    });

    it('should fail calculate Decimals and amount', async function () {
        let decimals = 16;
        let amount = 10000;
        let granularity = 10000;
        let token = await MainToken.new("MAIN", "MAIN", decimals, web3.utils.toWei('1000000'), { from: owner });

        utils.expectThrow(this.utilsLib.calculateDecimalsAndAmount(token.address, granularity, amount));
    });

});
