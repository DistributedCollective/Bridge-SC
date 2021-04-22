const { Telegram } = require('telegraf');

class TelegramBot {
    constructor(token, groupId, logger) {
        if(!token || !groupId) {
            throw new Error('Both token and groupId are required');
        }
        this.groupId = groupId;
        this.telegram = new Telegram(token);
        this.logger = logger || console;
    }

    async sendMessage(msg) {
        try {
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