module.exports = class GasPriceAvg {
    constructor() {
        this.arr = [];
    }

    calcAvg(_avgGasCount, elem) {
        this.arr.push(elem);

        if (this.arr.length > _avgGasCount) {
            this.arr.shift();
        }
        let total = 0;
        for (var i = 0; i < this.arr.length; i++) {
            total += Number(this.arr[i]);
        }
        let avgGas = total / this.arr.length;
        return avgGas;
    }
};
