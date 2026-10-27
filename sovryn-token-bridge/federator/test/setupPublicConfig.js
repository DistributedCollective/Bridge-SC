// Public test configuration only; never load an operator configuration or signing key.
jest.mock('../config/config', () => require('./fixtures/public-confirmation-config.json'), {
    virtual: true,
});
