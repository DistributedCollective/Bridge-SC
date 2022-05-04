"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (_) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
exports.__esModule = true;
exports.RSKKeyedAuth = void 0;
/**
 * Peer-to-peer authentication logic with RSK signatures
 */
var ataraxia_transport_1 = require("ataraxia-transport");
var crypto_1 = require("crypto");
var ethers_1 = require("ethers");
var utils_1 = require("ethers/lib/utils");
var ataraxia_tcp_1 = require("ataraxia-tcp");
function encode(json) {
    return Buffer.from(JSON.stringify(json), 'utf-8');
}
function decode(data) {
    return JSON.parse(data.toString('utf-8'));
}
function createMessage(challenge, security) {
    return Buffer.concat([challenge, Buffer.from(security)]);
}
/**
 * Monkey-patch the peer so that the public key pairs are supplied into the
 * challenge.
 */
var originalAddPeer = ataraxia_tcp_1.TCPTransport.prototype.addPeer;
ataraxia_tcp_1.TCPTransport.prototype.addPeer = function (peer) {
    peer.localPublicSecurity = function () {
        return Buffer.concat([this.stream.publicKey, this.stream.remotePublicKey]);
    };
    peer.remotePublicSecurity = function () {
        return Buffer.concat([this.stream.remotePublicKey, this.stream.publicKey]);
    };
    return originalAddPeer.apply(this, [peer]);
};
/**
 * RSKKeyedAuth. Allows entering the network if the node controls
 * one of the trusted private keys.
 **/
var RSKKeyedAuth = /** @class */ (function () {
    function RSKKeyedAuth(options) {
        this.id = 'rsk-keyed-auth';
        this.prefixString = 'fastbtc-p2p-auth:';
        this.signer = options.signer;
        // TODO: we could enable some caching for this
        this.getPeerAddresses = options.getPeerAddresses;
    }
    RSKKeyedAuth.prototype.createClientFlow = function (context) {
        var challenge = (0, crypto_1.randomBytes)(32);
        var prefix = Buffer.from(this.prefixString, 'utf-8');
        var that = this;
        var remotePublicSecurity = context.remotePublicSecurity;
        if (!remotePublicSecurity) {
            throw Error('Remote public security tag not provided');
        }
        var localPublicSecurity = context.localPublicSecurity;
        if (!localPublicSecurity) {
            throw Error('Local public security tag not provided');
        }
        return {
            initialMessage: function () {
                return __awaiter(this, void 0, void 0, function () {
                    return __generator(this, function (_a) {
                        console.log('preparing challenge to server');
                        return [2 /*return*/, encode({
                                version: 1,
                                challenge: (0, utils_1.hexlify)(challenge)
                            })];
                    });
                });
            },
            receiveData: function (data) {
                return __awaiter(this, void 0, void 0, function () {
                    var payload, serverChallenge, serverResponse, serverMessage, recoveredAddress, peerAddresses, clientMessage, _a, e_1;
                    var _b, _c;
                    return __generator(this, function (_d) {
                        switch (_d.label) {
                            case 0:
                                _d.trys.push([0, 3, , 4]);
                                payload = decode(Buffer.from(data));
                                if (payload.version !== 1) {
                                    console.error("Invalid payload version ".concat(payload.version, " received from server"));
                                    return [2 /*return*/, {
                                            type: ataraxia_transport_1.AuthClientReplyType.Reject
                                        }];
                                }
                                serverChallenge = Buffer.from((0, utils_1.arrayify)(payload.challenge));
                                serverResponse = payload.response;
                                serverMessage = createMessage(Buffer.concat([prefix, challenge]), remotePublicSecurity);
                                recoveredAddress = ethers_1.ethers.utils.verifyMessage(ethers_1.ethers.utils.arrayify(serverMessage), serverResponse);
                                return [4 /*yield*/, that.getPeerAddresses()];
                            case 1:
                                peerAddresses = _d.sent();
                                console.log("DEBUG: ".concat(peerAddresses.indexOf(recoveredAddress) === -1));
                                if (peerAddresses.indexOf(recoveredAddress) === -1) {
                                    console.error("Invalid signature from server, recovered address " +
                                        "".concat(recoveredAddress, " does not match any configured peer address"));
                                    return [2 /*return*/, {
                                            type: ataraxia_transport_1.AuthClientReplyType.Reject
                                        }];
                                }
                                clientMessage = createMessage(Buffer.concat([prefix, serverChallenge]), localPublicSecurity);
                                console.log("successful server challenge from ".concat(recoveredAddress));
                                _b = {
                                    type: ataraxia_transport_1.AuthClientReplyType.Data
                                };
                                _a = encode;
                                _c = {};
                                return [4 /*yield*/, that.signer.signMessage(clientMessage)];
                            case 2: return [2 /*return*/, (_b.data = _a.apply(void 0, [(_c.response = _d.sent(),
                                        _c)]),
                                    _b)];
                            case 3:
                                e_1 = _d.sent();
                                console.log(e_1);
                                throw e_1;
                            case 4: return [2 /*return*/];
                        }
                    });
                });
            },
            destroy: function () {
                return Promise.resolve();
            }
        };
    };
    RSKKeyedAuth.prototype.createServerFlow = function (context) {
        var challenge = (0, crypto_1.randomBytes)(32);
        var prefix = Buffer.from(this.prefixString, 'utf-8');
        var that = this;
        var remotePublicSecurity = context.remotePublicSecurity;
        if (!remotePublicSecurity) {
            throw Error('Remote public security tag not provided');
        }
        var localPublicSecurity = context.localPublicSecurity;
        if (!localPublicSecurity) {
            throw Error('Local public security tag not provided');
        }
        return {
            receiveInitial: function (data) {
                return __awaiter(this, void 0, void 0, function () {
                    var payload, serverMessage, _a, e_2;
                    var _b, _c;
                    return __generator(this, function (_d) {
                        switch (_d.label) {
                            case 0:
                                console.log('received client authentication handshake');
                                _d.label = 1;
                            case 1:
                                _d.trys.push([1, 3, , 4]);
                                payload = decode(Buffer.from(data));
                                if (payload.version !== 1) {
                                    console.error("Invalid payload version ".concat(payload.version, " received from client"));
                                    return [2 /*return*/, {
                                            type: ataraxia_transport_1.AuthServerReplyType.Reject
                                        }];
                                }
                                serverMessage = createMessage(Buffer.concat([
                                    prefix,
                                    Buffer.from((0, utils_1.arrayify)(payload.challenge)),
                                ]), localPublicSecurity);
                                _b = {
                                    type: ataraxia_transport_1.AuthServerReplyType.Data
                                };
                                _a = encode;
                                _c = {};
                                return [4 /*yield*/, that.signer.signMessage(serverMessage)];
                            case 2: return [2 /*return*/, (_b.data = _a.apply(void 0, [(_c.response = _d.sent(),
                                        _c.challenge = (0, utils_1.hexlify)(challenge),
                                        _c.version = 1,
                                        _c)]),
                                    _b)];
                            case 3:
                                e_2 = _d.sent();
                                console.error(e_2);
                                throw e_2;
                            case 4: return [2 /*return*/];
                        }
                    });
                });
            },
            receiveData: function (data) {
                return __awaiter(this, void 0, void 0, function () {
                    var payload, clientMessage, recoveredAddress, peerAddresses;
                    return __generator(this, function (_a) {
                        switch (_a.label) {
                            case 0:
                                payload = decode(Buffer.from(data));
                                clientMessage = createMessage(Buffer.concat([prefix, challenge]), remotePublicSecurity);
                                recoveredAddress = ethers_1.ethers.utils.verifyMessage(ethers_1.ethers.utils.arrayify(clientMessage), payload.response);
                                return [4 /*yield*/, that.getPeerAddresses()];
                            case 1:
                                peerAddresses = _a.sent();
                                console.log("DEBUG: ".concat(peerAddresses.indexOf(recoveredAddress) === -1));
                                if (peerAddresses.indexOf(recoveredAddress) === -1) {
                                    console.error("Invalid signature from client, recovered address " +
                                        "".concat(recoveredAddress, " does not match any configured peer address"));
                                    return [2 /*return*/, {
                                            type: ataraxia_transport_1.AuthServerReplyType.Reject
                                        }];
                                }
                                console.log("authentication successfully completed with ".concat(recoveredAddress));
                                return [2 /*return*/, {
                                        type: ataraxia_transport_1.AuthServerReplyType.Ok
                                    }];
                        }
                    });
                });
            },
            destroy: function () {
                return Promise.resolve();
            }
        };
    };
    return RSKKeyedAuth;
}());
exports.RSKKeyedAuth = RSKKeyedAuth;
