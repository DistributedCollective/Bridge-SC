const { Telegram } = require('telegraf');

class TelegramBot {
    constructor(token, groupId, logger, prefix) {
        if(!token || !groupId) {
            throw new Error('Both token and groupId are required');
        }
        this.groupId = groupId;
        this.telegram = new Telegram(token);
        this.logger = logger || console;
        this.prefix = prefix || '';
    }

    async sendMessage(msg) {
        try {
            if(this.prefix) {
                msg = `[${this.prefix}] ${msg}`;
            }
            await this.telegram.sendMessage(this.groupId, msg);
        } catch(err) {
            this.logger.error(err);
        }
    }
}

class NullBot {
    constructor(logger) {
        this.logger = logger || console;
    }

    async sendMessage(msg) {
        this.logger.debug(msg);
    }
}

module.exports = {
    TelegramBot,
    NullBot,
};