const fs = require("fs");
const {dirname} = require("path");

/**
 * A container that stores a list of string values both in the file system and in memory
 */
module.exports = class AppendOnlyFileStorage {
    constructor(path) {
        this.path = path;
        this.data = null;
    }

    load(force = false) {
        if(force || this.data === null) {
            const dirPath = dirname(this.path);
            if (!fs.existsSync(dirPath)) {
                fs.mkdirSync(dirPath);
            }
            if (fs.existsSync(this.path)) {
                const rawData = fs.readFileSync(this.path, 'utf-8');
                this.data = rawData.split('\n');
                if (this.data[this.data.length - 1] === '') {
                    // file ends with newline -- remove it
                    this.data = this.data.slice(0, -1);
                }
            } else {
                fs.appendFileSync(this.path, '', 'utf-8');
                this.data = [];
            }
        }
    }

    contains(value) {
        this.load();
        return this.data.indexOf(value) !== -1;
    }

    append(value) {
        this.load();
        this.data.push(value);
        fs.appendFileSync(this.path, `${value}\n`, 'utf-8');
    }
}