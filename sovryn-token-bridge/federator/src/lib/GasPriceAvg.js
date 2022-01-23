
module.exports = class GasPriceAvg {
    constructor() {
        this.arr = [];
    }
 
    calcAvg(_avgGasCount, elem) {
        this.arr.push(elem);

        if (this.arr.length > _avgGasCount){
            this.arr.shift();
        }
        let total = 0;
        for(var i = 0; i < this.arr.length; i++) {
            total +=  parseInt(this.arr[i], 10);
        }
        let avgGas = total / this.arr.length;
        return avgGas;
    }
};