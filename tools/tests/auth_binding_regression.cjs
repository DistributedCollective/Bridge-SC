"use strict";
// Exercise published ataraxia methods with controlled dependencies; no sockets or signatures.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const app = path.resolve(__dirname, "../../sovryn-token-bridge/federator");
const external = process.env.ATARAXIA_REVIEW_SOURCE_DIR;
function source(pkg, name) {
  if (external)
    return fs.readFileSync(path.join(external, `${pkg}-${name}.js`), "utf8");
  const entry = require.resolve(pkg, { paths: [app] });
  return fs.readFileSync(path.join(path.dirname(entry), `${name}.js`), "utf8");
}
function evaluate(text, mocks) {
  const module = { exports: {} };
  vm.runInNewContext(text, {
    module,
    exports: module.exports,
    require: (id) =>
      Object.prototype.hasOwnProperty.call(mocks, id) ? mocks[id] : require(id),
    Buffer,
    console: { log() {}, error() {} },
    setTimeout,
    clearTimeout,
    clearInterval,
    Promise,
  });
  return module.exports;
}
const reasons = { Error: 1, PingTimeout: 2, NegotiationFailed: 5 };
const AbstractPeer = evaluate(source("ataraxia-transport", "AbstractPeer"), {
  "adaptive-accrual-failure-detector": {},
  atvik: {},
  debug: {},
  "./auth": {},
  "./DisconnectReason": { DisconnectReason: reasons },
  "./ids": {},
  "./messages": { PeerMessageType: { Auth: 1 } },
}).AbstractPeer;
const StreamingPeer = evaluate(
  source("ataraxia-transport-streams", "StreamingPeer"),
  {
    "ataraxia-transport": { AbstractPeer, DisconnectReason: reasons },
    "./binaryStreams": {},
  }
).StreamingPeer;
class TCPTransport {
  addPeer(peer) {
    return peer;
  }
}
evaluate(
  fs.readFileSync(path.join(app, "src/vendors/RSKKeyedAuth.js"), "utf8"),
  {
    "ataraxia-transport": { DisconnectReason: reasons },
    "ataraxia-tcp": { TCPTransport },
    ethers: {},
    "ethers/lib/utils": {},
  }
);
let assertions = 0;
function peer(stream) {
  const p = Object.create(StreamingPeer.prototype);
  p.stream = stream;
  p.state = 0;
  p.debug = () => {};
  p.contexts = [];
  p.sent = 0;
  p.factoryCalls = 0;
  const provider = {
    id: "controlled-auth",
    createClientFlow(ctx) {
      p.factoryCalls++;
      p.contexts.push(ctx);
      return { initialMessage: async () => Buffer.from("auth") };
    },
    createServerFlow(ctx) {
      p.factoryCalls++;
      p.contexts.push(ctx);
      return { receiveInitial: async () => ({ type: "data" }) };
    },
  };
  p.remainingAuthProviders = [provider];
  p.authProviders = [provider];
  p.queueNegotiationTimeout = () => {};
  p.send = async () => {
    p.sent++;
  };
  p.handleSendingAuthReply = async () => {
    p.sent++;
  };
  new TCPTransport().addPeer(p);
  return p;
}
function socket(local, remote) {
  return {
    publicKey: local,
    remotePublicKey: remote,
    destroyed: 0,
    ended: 0,
    destroy() {
      this.destroyed++;
    },
    end(cb) {
      this.ended++;
      if (cb) cb();
    },
  };
}
async function turn() {
  await new Promise((resolve) => setImmediate(resolve));
}
(async () => {
  for (const [local, remote] of [
    [null, Buffer.alloc(32)],
    [Buffer.alloc(32), null],
    [Buffer.alloc(31), Buffer.alloc(32)],
    [Buffer.alloc(32), Buffer.alloc(33)],
  ]) {
    const stream = socket(local, remote);
    const p = peer(stream);
    assert.doesNotThrow(() => p.sendInitialAuth());
    assertions++;
    await turn();
    assert.strictEqual(stream.destroyed, 1);
    assertions++;
    assert.strictEqual(stream.ended, 0);
    assertions++;
    assert.strictEqual(p.factoryCalls, 0);
    assertions++;
    assert.strictEqual(p.stream, undefined);
    assertions++;
    const serverStream = socket(local, remote);
    const server = peer(serverStream);
    assert.doesNotThrow(() =>
      server.receiveAuth({ method: "controlled-auth", data: Buffer.from("x") })
    );
    assertions++;
    await turn();
    assert.strictEqual(serverStream.destroyed, 1);
    assertions++;
    assert.strictEqual(serverStream.ended, 0);
    assertions++;
    assert.strictEqual(server.factoryCalls, 0);
    assertions++;
  }
  const absent = peer(undefined);
  assert.doesNotThrow(() => absent.sendInitialAuth());
  assertions++;
  assert.strictEqual(absent.factoryCalls, 0);
  assertions++;
  const good = peer(socket(Buffer.alloc(32, 1), Buffer.alloc(32, 2)));
  good.sendInitialAuth();
  await turn();
  assert.strictEqual(good.sent, 1);
  assertions++;
  assert.strictEqual(good.factoryCalls, 1);
  assertions++;
  assert.ok(
    good.contexts[0].localPublicSecurity.equals(
      Buffer.concat([Buffer.alloc(32, 1), Buffer.alloc(32, 2)])
    )
  );
  assertions++;
  assert.ok(
    good.contexts[0].remotePublicSecurity.equals(
      Buffer.concat([Buffer.alloc(32, 2), Buffer.alloc(32, 1)])
    )
  );
  assertions++;
  assert.strictEqual(good.stream.destroyed, 0);
  assertions++;
  const server = peer(socket(Buffer.alloc(32, 3), Buffer.alloc(32, 4)));
  server.receiveAuth({ method: "controlled-auth", data: Buffer.from("x") });
  await turn();
  assert.strictEqual(server.factoryCalls, 1);
  assertions++;
  assert.strictEqual(server.sent, 1);
  assertions++;
  assert.strictEqual(server.stream.destroyed, 0);
  assertions++;
  const unexpected = peer(socket(Buffer.alloc(32), Buffer.alloc(32)));
  unexpected.remainingAuthProviders = [
    {
      createClientFlow() {
        throw Error("unrelated provider bug");
      },
    },
  ];
  assert.throws(() => unexpected.sendInitialAuth(), /unrelated provider bug/);
  assertions++;
  console.log(
    `auth binding regressions: ${assertions} assertions passed; published peer boundaries, no network/signing`
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
