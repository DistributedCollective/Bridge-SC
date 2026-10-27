"use strict";
// Isolated Node assertions: real fee/oracle code, controlled transport/module boundaries.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { EventEmitter } = require("events");
let assertions = 0;
for (const name of ["strictEqual", "rejects", "ok"]) {
  const original = assert[name];
  assert[name] = (...args) => {
    assertions++;
    return original(...args);
  };
}
const root = path.resolve(
  __dirname,
  "../../sovryn-token-bridge/federator/src/lib"
);
function load(name, overrides = {}, globals = {}) {
  const module = { exports: {} };
  const actualRequire = require;
  const req = (id) => {
    if (Object.prototype.hasOwnProperty.call(overrides, id))
      return overrides[id];
    if (id.startsWith("./")) return require(path.join(root, id));
    return actualRequire(id);
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(root, name), "utf8"),
    {
      require: req,
      module,
      exports: module.exports,
      Buffer,
      console,
      setTimeout,
      clearTimeout,
      URL,
      BigInt,
      Date,
      __dirname: root,
      ...globals,
    },
    { filename: name }
  );
  return module.exports;
}
const logger = { info() {}, debug() {}, warn() {}, error() {} };
function sender(block) {
  const globals = { currentEthGasBasePrice: 0, currentEthGasPriceAvg: 0 };
  const Sender = load("TransactionSender.js", {
    "ethereumjs-tx": class {},
    "ethereumjs-util": {},
    "@ethereumjs/tx": {},
    "@ethereumjs/common": { default: class {} },
    "./utils": { sleep: async () => {} },
    "./globals": globals,
  });
  const client = {
    eth: {
      getBlock: async () =>
        Object.assign({ timestamp: Math.floor(Date.now() / 1000) }, block),
      getTransactionCount: async () => "3",
      estimateGas: async () => 70000,
    },
  };
  return new Sender(
    client,
    logger,
    { ethGasPriceThresholdGwei: 1000, sleepOnGas: 0, maxSleepOnGas: 1 },
    1
  );
}
function transport(status, payload, mode) {
  const seen = [];
  const closed = { request: 0, response: 0 };
  return {
    seen,
    closed,
    get(url, cb) {
      seen.push(String(url));
      const req = new EventEmitter();
      req.destroy = () => {
        closed.request++;
      };
      process.nextTick(() => {
        const res = new EventEmitter();
        res.statusCode = status;
        res.setEncoding = () => {};
        res.resume = () => {};
        res.destroy = () => {
          closed.response++;
        };
        cb(res);
        if (mode === "stall") return;
        res.emit(
          "data",
          mode === "large"
            ? JSON.stringify({
                status: "1",
                result: { SafeGasPrice: "1" },
                padding: "x".repeat(128 * 1024),
              })
            : JSON.stringify(payload)
        );
        res.emit("end");
      });
      return req;
    },
  };
}
(async () => {
  const Average = load("GasPriceAvg.js");
  const average = new Average();
  assert.strictEqual(average.calcAvg(4, "0.5"), 0.5);
  assert.strictEqual(average.calcAvg(4, "0.25"), 0.375);
  const s = sender({
    baseFeePerGas: "123456789",
    timestamp: Math.floor(Date.now() / 1000),
  });
  const tx = await s.createETHRawTransaction("0xfrom", "0xto", "0xdata", 0, 1);
  assert.strictEqual(BigInt(tx.maxFeePerGas), 2760493826n); // ceil((123456789 + 2e9) *1.3) =2760493826
  assert.strictEqual(tx.maxPriorityFeePerGas, "0x77359400");
  for (const value of [undefined, null, 0, "0", "NaN", "1.2", Infinity, "-1"]) {
    await assert.rejects(() =>
      sender({ baseFeePerGas: value }).createETHRawTransaction(
        "a",
        "b",
        "c",
        0,
        1
      )
    );
  }
  const dead = sender({});
  dead.client.eth.getBlock = async () => {
    throw Error("provider-private-secret");
  };
  await assert.rejects(
    () => dead.createETHRawTransaction("a", "b", "c", 0, 1),
    (e) => !String(e).includes("provider-private-secret")
  );
  const tr = transport(200, {
    status: "1",
    result: { SafeGasPrice: "0.123456789" },
  });
  const Fetch = load("GasPriceFetcher.js", { https: tr });
  const fetch = new Fetch(
    logger,
    "private-api-key",
    "https://api.etherscan.io/api"
  );
  assert.strictEqual(await fetch.getEtherscanBaseGasPrice(), "0.123456789");
  const url = new URL(tr.seen[0]);
  assert.strictEqual(url.pathname, "/v2/api");
  assert.strictEqual(url.searchParams.get("chainid"), "1");
  assert.strictEqual(url.searchParams.get("apikey"), "private-api-key");
  for (const quote of ["0", "-1", "NaN", "Infinity", "", "1x", null]) {
    const t = transport(200, { status: "1", result: { SafeGasPrice: quote } });
    const F = load("GasPriceFetcher.js", { https: t });
    await assert.rejects(() =>
      new F(
        logger,
        "k",
        "https://api.etherscan.io/api"
      ).getEtherscanBaseGasPrice()
    );
  }
  for (const candidate of ["1".repeat(64), "0x" + "a".repeat(64)]) {
    const network = transport(200, {
      status: "1",
      result: { SafeGasPrice: "1" },
    });
    const Guarded = load("GasPriceFetcher.js", { https: network });
    await assert.rejects(() =>
      new Guarded(
        logger,
        candidate,
        "https://api.etherscan.io/api"
      ).getEtherscanBaseGasPrice()
    );
    assert.strictEqual(network.seen.length, 0);
  }
  const denied = transport(403, {
    status: "1",
    result: { SafeGasPrice: "1" },
    secret: "opaque-private-secret",
  });
  const D = load("GasPriceFetcher.js", { https: denied });
  await assert.rejects(
    () =>
      new D(
        logger,
        "k",
        "https://api.etherscan.io/api"
      ).getEtherscanBaseGasPrice(),
    (e) => !String(e).includes("opaque-private-secret")
  );
  assert.ok(denied.closed.request > 0);
  assert.ok(denied.closed.response > 0);
  await assert.rejects(() =>
    sender({ baseFeePerGas: "123", timestamp: 1 }).createETHRawTransaction(
      "a",
      "b",
      "c",
      0,
      1
    )
  );
  const oversized = transport(200, {}, "large");
  const O = load("GasPriceFetcher.js", { https: oversized });
  await assert.rejects(() =>
    new O(
      logger,
      "k",
      "https://api.etherscan.io/api"
    ).getEtherscanBaseGasPrice()
  );
  const stall = transport(200, {}, "stall");
  const S = load(
    "GasPriceFetcher.js",
    { https: stall },
    { setTimeout: (fn, ms) => setTimeout(fn, Math.min(ms, 20)) }
  );
  await assert.rejects(() =>
    new S(
      logger,
      "k",
      "https://api.etherscan.io/api"
    ).getEtherscanBaseGasPrice()
  );
  assert.ok(stall.closed.request > 0);
  assert.ok(stall.closed.response > 0);
  let pending = 0;
  const E = load(
    "GasPriceFetcher.js",
    {
      https: {
        get() {
          throw Error("opaque-provider-api-key");
        },
      },
    },
    {
      setTimeout(fn, ms) {
        pending++;
        return setTimeout(fn, ms);
      },
      clearTimeout(timer) {
        pending--;
        clearTimeout(timer);
      },
    }
  );
  await assert.rejects(
    () =>
      new E(logger, "k", "https://api.etherscan.io/api")._makeRequest(
        "https://api.etherscan.io/api"
      ),
    (e) => !String(e).includes("opaque-provider-api-key")
  );
  assert.strictEqual(pending, 0);
  const failureLogs = [];
  const GasServices = load("GasServices.js", {
    web3: {},
    "../../config/config.js": {
      gasApiRunEvery: 5,
      avgGasRunEvery: 10,
      periodAvgGas: 240,
    },
    "../services/Scheduler.js": class {},
    log4js: { getLogger: () => logger },
    "../lib/GasPriceFetcher.js": class {},
    "../lib/GasPriceAvg.js": class {},
  });
  const service = new GasServices(
    { ...logger, error: (...args) => failureLogs.push(args) },
    { sidechain: { host: "https://rpc.invalid" }, etherscanApiKey: "read-key" }
  );
  service.gasPriceAvg.calcAvg = () => {
    throw new Error("controlled averaging fault");
  };
  await service.runGasPriceAvg();
  assert.strictEqual(failureLogs.length, 1);
  assert.ok(String(failureLogs[0][1]).includes("controlled averaging fault"));
  for (const [configured, expected] of [[5,5000],[12,12000],[0,5000],[-1,5000],[0.1,5000],[NaN,5000],[Infinity,5000],[3000000,5000]]) {
    const intervals = [];
    const settings = {gasApiRunEvery:configured, avgGasRunEvery:10, periodAvgGas:240};
    const Service = load("GasServices.js", {
      web3: {}, "../../config/config.js": settings,
      "../services/Scheduler.js": class {
        constructor(interval) { intervals.push(interval); }
        async start() {}
      },
      "./utils": {sleep: async () => {}},
      log4js: {getLogger: () => logger},
      "../lib/GasPriceFetcher.js": class {},
      "../lib/GasPriceAvg.js": class {},
    });
    const gasService = new Service(logger, {...settings,sidechain:{host:"https://rpc.invalid"}});
    await gasService.startGasServices();
    assert.strictEqual(intervals[0], expected);
    assert.strictEqual(intervals[1], 10000);
    assert.ok(Math.ceil(86400000 / intervals[0]) <= 17280);
  }
  const scheduled = [];
  let finishPoll;
  let calls = 0;
  const Scheduler = load("../services/Scheduler.js", {}, {
    setTimeout(fn, delay) { scheduled.push({fn, delay}); return 1; },
    clearTimeout() {},
  });
  const poller = new Scheduler(5000, logger, {
    run() { calls++; return new Promise(resolve => { finishPoll = resolve; }); }
  });
  const starting = poller.start();
  assert.strictEqual(calls, 1);
  assert.strictEqual(scheduled.length, 0);
  finishPoll();
  await starting;
  assert.strictEqual(scheduled.length, 1);
  assert.strictEqual(scheduled[0].delay, 5000);
  console.log(
    `gas fee/oracle regressions: ${assertions} assertions passed; no network or signing`
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
