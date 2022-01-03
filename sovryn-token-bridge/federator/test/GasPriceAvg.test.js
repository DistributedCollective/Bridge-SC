const gasPriceAvg = require("../src/lib/GasPriceAvg");

describe('GasPriceAvg', () => {

    beforeEach(() => {
        averageT = new gasPriceAvg({ });
    });

    describe('#calcAvg', function () {
        it('Calc Avergae Gas price', async () => {
            //initial average = 90 
            let averagePrice = await averageT.calcAvg(4,91);
            let tempAvg = averagePrice.toFixed(2);
            console.log("tempAvg: "+ tempAvg);
            // (90+91)/2 = 90.5
            expect(tempAvg === (90.5));
            
            averagePrice = await averageT.calcAvg(4,112);
            tempAvg = averagePrice.toFixed(2);
            console.log("tempAvg: "+ tempAvg);
            // (90+91+112)/3 = 97.67
            expect(tempAvg === (97.67));

            averagePrice = await averageT.calcAvg(4,110);
            tempAvg = averagePrice.toFixed(2);
            console.log("tempAvg: "+ tempAvg);
            // (90+91+112+110)/4 = 100.75
            expect(tempAvg === (100.75));
            
            averagePrice = await averageT.calcAvg(4,99);
            tempAvg = averagePrice.toFixed(2);
            console.log("tempAvg: "+ tempAvg);
            // (91+112+110+99)/4 = 103
            expect(tempAvg === (103));
        });
    });
});