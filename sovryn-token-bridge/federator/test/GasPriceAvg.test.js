const gasPriceAvg = require("../src/lib/GasPriceAvg");
let averageT; 

describe('GasPriceAvg', () => {

    beforeEach(() => {
        averageT = new gasPriceAvg({ });
    });

    describe('#calcAvg', function () {
        it('Calc Avergae Gas price', async () => {
            //initial average = 90 
            let averagePrice = await averageT.calcAvg(4,91);
            let tempAvg = averagePrice.toFixed(2);
            // (91)/1 = 91.00
            //expect(tempAvg).toBeCloseTo(90.5, 0.0001);
            expect(tempAvg).toEqual("91.00");
            
            averagePrice = await averageT.calcAvg(4,112);
            tempAvg = averagePrice.toFixed(2);
            // (91+112)/2 = 101.50
            expect(tempAvg).toEqual("101.50");

            // expect(tempAvg).toBeCloseTo(97.67, 0.0001);

            averagePrice = await averageT.calcAvg(4,110);
            tempAvg = averagePrice.toFixed(2);
            // (91+112+110)/3 = 104.33
            expect(tempAvg).toEqual("104.33");
            
            averagePrice = await averageT.calcAvg(4,99);
            tempAvg = averagePrice.toFixed(2);
            // (91+112+110+99)/4 = 103
            expect(tempAvg).toEqual("103.00");
            // expect(tempAvg).toBeCloseTo(103, 0.0001);

            averagePrice = await averageT.calcAvg(4,88);
            tempAvg = averagePrice.toFixed(2);
            // (112+110+99+88)/4 = 102.25
            expect(tempAvg).toEqual("102.25");

        });
    });
});