class CustomError extends Error {
    constructor(message, err) {
        super(message);
        if (err !== undefined) {
            this.stack += '\n Internal ' + err.stack;
        }
    }
}

module.exports = CustomError;