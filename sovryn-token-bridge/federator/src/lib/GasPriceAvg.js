
module.exports = class GasPriceAvg {
    constructor() {
        this.arr = [];
    }
 
    async calcAvg(_avgGasCount, elem) {
        this.arr.push(elem);
        if (this.arr.length >= _avgGasCount){
            this.arr.shift();
        }
        const total = this.arr.reduce((acc, c) => acc + c, 0);
        return total / this.arr.length;
    }
};