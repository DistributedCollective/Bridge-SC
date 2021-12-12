
module.exports = class GasPriceAvg {
    constructor() {
        this.arr = [90];
    }
 
    async calcAvg(_avgGasCount, elem) {
        this.arr.push(elem);
        // console.log("elem: " +elem);
        // console.log("_avgGasCount: " +_avgGasCount);
        // console.log("this.arr[0]: " +this.arr[0]);     
        //    console.log("this.arr[1]: " +this.arr[1]);

        // console.log("this.arr.length: " +this.arr.length);

        if (this.arr.length >= _avgGasCount){
            this.arr.shift();
        }

        let total = 0;
        for(var i = 0; i < this.arr.length; i++) {
            total +=  parseInt(this.arr[i], 10);
        }
        //let avgGas = Math.floor(total / this.arr.length);
        let avgGas = total / this.arr.length;

        //let total = this.arr.reduce((acc, c) => acc + c, 0);
        //console.log("total: " + total );
        //let avgGas = total / this.arr.length;
        //console.log("avgGas: " + avgGas );
        return avgGas;
    }
};