"use strict";
const fs = require("fs"),
  path = require("path"),
  readline = require("readline");
const [mode, appPath, configPath] = process.argv.slice(2),
  app = path.resolve(appPath),
  fixture = JSON.parse(fs.readFileSync(configPath, "utf8"));
const dependencies = path.join(app, "federator/node_modules");
const Web3 = require(path.join(dependencies, "web3"));
const { ethers } = require(path.join(dependencies, "ethers"));
const bridgeAbi = require(path.join(app, "abis/Bridge.json"));
const federationAbi = require(path.join(app, "abis/Federation.json"));
const ERC = [
  {
    name: "balanceOf",
    type: "function",
    stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ name: "value", type: "uint256" }],
  },
];
const contracts = fixture.contracts || {
  1: {
    bridge: "0x33c0d33a0d4312562ad622f91d12b0ac47366ee1",
    federation: "0xd77b76a65a19715bdcb5ee223928af2919836a3e",
  },
  30: {
    bridge: "0x1ccad820b6d031b41c54f1f3da11c0d48b399581",
    federation: "0x32593e4f7a4991c2fe17459dae9920fd612855b4",
  },
};
const clients = {};
for (const chain of [1, 30]) {
  if (
    !/^http:\/\/(?:127\.0\.0\.1:[0-9]+|bf-[0-9a-f]{12}-gateway:8547)\/local\/(1|30)$/.test(
      fixture.rpc[chain]
    )
  )
    throw Error("Only owned lab gateway URLs permitted");
  clients[chain] = new Web3(
    new Web3.providers.HttpProvider(fixture.rpc[chain], { timeout: 15000 })
  );
}
const emit = (value) =>
  process.stdout.write("LAB:" + JSON.stringify(value) + "\n");
const logger = {
  debug() {},
  info(...a) {
    console.log("INFO", ...a);
  },
  warn(...a) {
    console.log("WARN", ...a);
  },
  error(...a) {
    console.log("ERROR", ...a);
  },
};
const addresses =
  fixture.addresses ||
  fixture.keys.map((key) => new ethers.Wallet(key).address);
const raw = async (chain, method, params) =>
  new Promise((resolve, reject) =>
    clients[chain].currentProvider.send(
      { jsonrpc: "2.0", id: Date.now(), method, params },
      (err, result) =>
        err || result.error
          ? reject(Error("Lab RPC " + method + " unavailable"))
          : resolve(result.result)
    )
  );
async function receipt(chain, hash) {
  for (let i = 0; i < 60; i++) {
    const r = await clients[chain].eth.getTransactionReceipt(hash);
    if (r) return r;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw Error("Local receipt deadline");
}
async function setup() {
  const roster = [];
  for (const chain of [1, 30]) {
    const fed = new clients[chain].eth.Contract(
      federationAbi,
      contracts[chain].federation
    );
    const owner = await fed.methods.owner().call(),
      before = await fed.methods.getMembers().call(),
      required = await fed.methods.required().call();
    if (Number(required) !== 3) throw Error("Expected unchanged required3");
    await raw(chain, "anvil_impersonateAccount", [owner]);
    await raw(chain, "anvil_setBalance", [owner, "0x52b7d2dcc80cd2e4000000"]);
    const send = async (method) => {
      const hash = await raw(chain, "eth_sendTransaction", [
        {
          from: owner,
          to: fed.options.address,
          data: method.encodeABI(),
          gas: "0x2dc6c0",
          gasPrice: "0x77359400",
        },
      ]);
      const r = await receipt(chain, hash);
      if (!r.status) throw Error("Local member mutation reverted");
      return hash;
    };
    const tx = [];
    for (const address of addresses)
      tx.push(await send(fed.methods.addMember(address)));
    for (const address of before)
      tx.push(await send(fed.methods.removeMember(address)));
    await raw(chain, "anvil_stopImpersonatingAccount", [owner]);
    for (const address of addresses)
      await raw(chain, "anvil_setBalance", [
        address,
        "0x52b7d2dcc80cd2e4000000",
      ]);
    const after = await fed.methods.getMembers().call();
    if (
      after.length !== 3 ||
      after.some((a) => !addresses.includes(ethers.utils.getAddress(a)))
    )
      throw Error("Fixture roster mismatch");
    roster.push({ chain, before, after, required, localMutationReceipts: tx });
    console.log("Fixture roster complete", chain);
  }
  const cases = [];
  for (const event of fixture.events) {
    const source = clients[event.chain],
      destination = clients[event.chain === 1 ? 30 : 1];
    const sourceBridge = new source.eth.Contract(
      bridgeAbi,
      contracts[event.chain].bridge
    );
    console.log("Checking source receipt", event.chain, event.tx.slice(0, 12));
    const r = await source.eth.getTransactionReceipt(event.tx);
    if (!r || !r.status)
      throw Error("Canonical successful source receipt required");
    const logs = await sourceBridge.getPastEvents("Cross", {
      fromBlock: r.blockNumber,
      toBlock: r.blockNumber,
    });
    const matching = logs.filter(
      (x) => x.transactionHash.toLowerCase() === event.tx.toLowerCase()
    );
    if (matching.length !== 1)
      throw Error("Expected one canonical source Cross");
    const log = matching[0],
      v = log.returnValues,
      dest = event.chain === 1 ? 30 : 1,
      bridge = new destination.eth.Contract(bridgeAbi, contracts[dest].bridge),
      fed = new destination.eth.Contract(
        federationAbi,
        contracts[dest].federation
      );
    const fid = await fed.methods
      .getTransactionIdU(
        v._tokenAddress,
        v._to,
        v._amount,
        v._symbol,
        log.blockHash,
        log.transactionHash,
        log.logIndex,
        v._decimals,
        v._granularity,
        v._userData || "0x"
      )
      .call();
    if (event.id && fid.toLowerCase() !== event.id.toLowerCase())
      throw Error("Supplied ID mismatch");
    const bid = await bridge.methods
      .getTransactionId(
        log.blockHash,
        log.transactionHash,
        v._to,
        v._amount,
        log.logIndex
      )
      .call();
    cases.push({
      chain: event.chain,
      tx: event.tx,
      sourceBlock: r.blockNumber,
      sourceBlockHash: r.blockHash,
      receiver: v._to,
      token: v._tokenAddress,
      symbol: v._symbol,
      amount: v._amount,
      federationId: fid,
      bridgeId: bid,
      before: {
        bridge: await bridge.methods.processed(bid).call(),
        federation: await fed.methods.transactionWasProcessed(fid).call(),
      },
    });
  }
  emit({ ok: true, rosters: roster, fixture: { addresses, cases } });
}
async function worker() {
  const P2p = require(path.join(app, "federator/src/lib/p2p"));
  const Federator = require(path.join(app, "federator/src/lib/Federator"));
  const { ConfirmationTableReader } = require(path.join(
    app,
    "federator/src/helpers/ConfirmationTableReader"
  ));
  const C = require(path.join(app, "federator/src/lib/constants"));
  const p2p = new P2p(logger),
    index = fixture.index,
    root = path.join(fixture.root, "db-" + index);
  fs.mkdirSync(root, { recursive: true });
  const table = {
    1: { minConfirmation: 1, default: 400 },
    30: { minConfirmation: 1, default: 400 },
  };
  const build = (source, dest, type) =>
    new Federator(
      type,
      {
        mainchain: { host: fixture.rpc[source], ...contracts[source] },
        sidechain: { host: fixture.rpc[dest], ...contracts[dest] },
        storagePath: path.join(root, String(source)),
        privateKey: fixture.privateKey || fixture.keys[index],
        minimumPeerAmount: 2,
        signaturesTTL: 600,
        signatureRequestTimeoutMs: 10000,
        confirmationTable: table,
        ethGasPriceThresholdGwei: 1000,
        maxSleepOnGas: 0,
      },
      logger,
      p2p
    );
  for (const c of [1, 30])
    fs.mkdirSync(path.join(root, String(c)), { recursive: true });
  const fed = {
    1: build(1, 30, C.SIDE_FEDERATOR),
    30: build(30, 1, C.MAIN_FEDERATOR),
  };
  for (const f of Object.values(fed)) await f.populateMemberAddresses();
  p2p.initiateP2pNetwork(
    "bridge-fork-lab-" + (fixture.runId || path.basename(fixture.root)),
    fixture.ports[index],
    fixture.ports.flatMap((port, i) =>
      i === index
        ? []
        : [{ ip: fixture.ips ? fixture.ips[i] : "127.0.0.1", port }]
    ),
    addresses,
    fixture.privateKey || fixture.keys[index]
  );
  let submitted = 0,
    requested = 0,
    signatureDelay = 0,
    signatureEpoch = 0;
  const signatureEvidence = [];
  p2p.net.onMessage(async (msg) => {
    const source =
      msg.type === C.MAIN_SIGNATURE_REQUEST
        ? 30
        : msg.type === C.SIDE_SIGNATURE_REQUEST
        ? 1
        : null;
    if (!source) return;
    requested++;
    const epoch = signatureEpoch;
    try {
      if (signatureDelay)
        await new Promise((resolve) => setTimeout(resolve, signatureDelay));
      if (epoch !== signatureEpoch) return;
      const value = await fed[source].signTransaction({
        blockNumber: msg.data.log.blockNumber,
        id: msg.data.log.id,
      });
      signatureEvidence.push({
        chain: source,
        logId: value.logId,
        deadline: value.signatureData.deadline,
        signer: addresses[index],
      });
      submitted++;
      await msg.source.send(
        source === 30
          ? C.MAIN_SIGNATURE_SUBMISSION
          : C.SIDE_SIGNATURE_SUBMISSION,
        value
      );
    } catch (err) {
      logger.warn("Signature request failed", err.message);
    }
  });
  await p2p.start();
  emit({
    ok: true,
    type: "started",
    index,
    address: addresses[index],
    node: process.version,
  });
  const state = () => ({
    ok: true,
    index,
    peers: p2p.getPeerAmount(),
    leader: p2p.isLeader(),
    nodeId: p2p.net.networkId,
    leaderId: p2p.getLeaderId(),
    requested,
    submitted,
    signatures: signatureEvidence.slice(-20),
  });
  let chain = Promise.resolve();
  readline.createInterface({ input: process.stdin }).on("line", (line) => {
    chain = chain
      .then(async () => {
        const cmd = JSON.parse(line);
        if (cmd.op === "state") {
          emit(state());
          return;
        }
        if (cmd.op === "delay-signatures") {
          signatureDelay = cmd.ms;
          emit(state());
          return;
        }
        if (cmd.op === "leave") {
          signatureEpoch++;
          await p2p.stop();
          emit({ ...state(), left: true });
          return;
        }
        if (cmd.op === "join") {
          await p2p.start();
          emit(state());
          return;
        }
        if (cmd.op === "gas-probe") {
          const http = require("http");
          let variant = "valid";
          let seen = null;
          const server = http.createServer((req, res) => {
            seen = new URL(req.url, "http://localhost");
            res.setHeader("Content-Type", "application/json");
            res.end(
              JSON.stringify(
                variant === "valid"
                  ? { status: "1", result: { SafeGasPrice: "0.123456789" } }
                  : {
                      status: "0",
                      message: "NOTOK",
                      result: "Deprecated V1 endpoint",
                    }
              )
            );
          });
          await new Promise((resolve) =>
            server.listen(0, "127.0.0.1", resolve)
          );
          const Fetch = require(path.join(
              app,
              "federator/src/lib/GasPriceFetcher"
            )),
            Average = require(path.join(app, "federator/src/lib/GasPriceAvg")),
            Services = require(path.join(app, "federator/src/lib/GasServices"));
          const fetcher = new Fetch(
            logger,
            "lab-read-credential",
            "http://127.0.0.1:" + server.address().port + "/v2/api"
          );
          const quote = await fetcher.getEtherscanBaseGasPrice(),
            avg = new Average(logger).calcAvg(4, quote);
          if (
            quote !== "0.123456789" ||
            avg !== 0.123456789 ||
            seen.pathname !== "/v2/api" ||
            seen.searchParams.get("chainid") !== "1"
          )
            throw Error("V2 fractional quote regression");
          const svc = new Services(
            logger,
            {
              sidechain: { host: fixture.rpc[1] },
              etherscanApiKey: "lab-read-credential",
            },
            Web3
          );
          svc.gasPriceFetcher = fetcher;
          variant = "deprecated";
          await svc.runGasPriceService();
          await new Promise((resolve) => server.close(resolve));
          emit({
            ...state(),
            gas: {
              v2Quote: quote,
              fractionalAverage: avg,
              deprecatedResponseCaught: true,
              peerCountAfter: p2p.getPeerAmount(),
            },
          });
          return;
        }
        if (cmd.op === "fee-probe") {
          const Current = require(path.join(
              app,
              "federator/src/lib/TransactionSender"
            )),
            Old = require(path.join(
              app,
              "federator/src/lib/TransactionSender.baseline.js"
            ));
          const cfg = {
            storagePath: root,
            ethGasPriceThresholdGwei: 1000,
            maxSleepOnGas: 0,
          };
          const before = await clients[1].eth.getBlock("latest");
          const old = await new Old(
            clients[1],
            logger,
            cfg,
            1
          ).createETHRawTransaction(
            addresses[index],
            addresses[index],
            "0x",
            0,
            1
          );
          const repaired = await new Current(
            clients[1],
            logger,
            cfg,
            1
          ).createETHRawTransaction(
            addresses[index],
            addresses[index],
            "0x",
            0,
            1
          );
          const base = BigInt(before.baseFeePerGas),
            oldCap = BigInt(old.maxFeePerGas),
            newCap = BigInt(repaired.maxFeePerGas);
          emit({
            ...state(),
            fee: {
              baseFeeWei: base.toString(),
              oldMaxFeeWei: oldCap.toString(),
              repairedMaxFeeWei: newCap.toString(),
              oldBelowBaseFee: oldCap < base,
              repairedCoversBaseFee: newCap >= base,
            },
          });
          return;
        }
        if (cmd.op === "connection-reset") {
          const net = require("net");
          const sockets = [];
          const server = net.createServer((socket) => sockets.push(socket));
          await new Promise((resolve) =>
            server.listen(0, "127.0.0.1", resolve)
          );
          const peer = p2p.transport.connectToPeer([
            { host: "127.0.0.1", port: server.address().port },
          ]);
          await new Promise((resolve) => setTimeout(resolve, 150));
          const binding = {
            localBytes:
              peer.stream && peer.stream.publicKey
                ? peer.stream.publicKey.length
                : null,
            remoteBytes:
              peer.stream && peer.stream.remotePublicKey
                ? peer.stream.remotePublicKey.length
                : null,
          };
          peer.remainingAuthProviders = p2p.transport.authProviders.slice();
          // Re-enter the native transport callback while its channel is unready.
          // The old application's uncaught exception ends this disposable worker.
          setImmediate(() => peer.sendInitialAuth());
          await new Promise((resolve) => setTimeout(resolve, 250));
          peer.stopConnecting();
          if (peer.stream) peer.stream.destroy();
          for (const socket of sockets) socket.destroy();
          await new Promise((resolve) => server.close(resolve));
          emit({
            ...state(),
            connectionReset: { nativeBinding: binding, processSurvived: true },
          });
          return;
        }
        if (cmd.op === "process") {
          const f = fed[cmd.event.chain],
            r = await f.mainWeb3.eth.getTransactionReceipt(cmd.event.tx),
            logs = await f.mainBridgeContract.getPastEvents("Cross", {
              fromBlock: r.blockNumber,
              toBlock: r.blockNumber,
            });
          const selected = logs.filter(
            (x) =>
              x.transactionHash.toLowerCase() === cmd.event.tx.toLowerCase()
          );
          if (selected.length !== 1) throw Error("Source event missing");
          const log = selected[0],
            v = log.returnValues,
            dest = new f.sideWeb3.eth.Contract(
              bridgeAbi,
              contracts[cmd.event.chain === 1 ? 30 : 1].bridge
            );
          const fid = fixture.cases.find(
            (x) => x.tx === cmd.event.tx
          ).federationId;
          const destinationToken = async () =>
            (await dest.methods.knownTokens(v._tokenAddress).call())
              ? v._tokenAddress
              : await dest.methods.mappedTokens(v._tokenAddress).call();
          const tokenBefore = await destinationToken();
          const bal = async (token) =>
            token && token !== "0x0000000000000000000000000000000000000000"
              ? await new f.sideWeb3.eth.Contract(ERC, token).methods
                  .balanceOf(v._to)
                  .call()
              : "0";
          const before = await bal(tokenBefore);
          const processedBefore = await f._isAlreadyProcessed(log);
          const destinationStart = await f.sideWeb3.eth.getBlockNumber();
          let error = null;
          try {
            await f._processLogs(
              new ConfirmationTableReader(cmd.event.chain, table),
              selected
            );
          } catch (err) {
            error = {
              name: err.name,
              message: err.message,
              stack: String(err.stack).slice(0, 2000),
            };
          }
          const tokenAfter = await destinationToken(),
            after = await bal(tokenAfter),
            processedAfter = await f._isAlreadyProcessed(log);
          const executions =
            processedAfter && !processedBefore
              ? await f.federationContract.getPastEvents("Executed", {
                  fromBlock: destinationStart + 1,
                  toBlock: "latest",
                  filter: { transactionId: fid },
                })
              : [];
          const executionProof = [];
          for (const ev of executions) {
            const receipt = await f.sideWeb3.eth.getTransactionReceipt(
              ev.transactionHash
            );
            executionProof.push({
              transactionHash: ev.transactionHash,
              blockNumber: ev.blockNumber,
              transactionId: ev.returnValues.transactionId,
              status: receipt.status,
              gasUsed: receipt.gasUsed,
              logs: receipt.logs,
            });
          }
          emit({
            ...state(),
            ok: !error,
            executionProof,
            outcome: error
              ? "failed"
              : processedBefore
              ? "already-processed"
              : processedAfter
              ? "executed"
              : "not-processed",
            event: cmd.event,
            federationId: fid,
            processedBefore,
            processedAfter,
            error,
            receiverToken: tokenAfter,
            balanceBefore: before,
            balanceAfter: after,
            balanceDelta:
              before !== null && after !== null
                ? (BigInt(after) - BigInt(before)).toString()
                : null,
            votes: await f.federationContract.methods
              .getTransactionCount(fid)
              .call(),
          });
          return;
        }
        throw Error("Unknown command");
      })
      .catch((err) =>
        emit({
          ok: false,
          error: {
            name: err.name,
            message: err.message,
            stack: String(err.stack).slice(0, 2000),
          },
        })
      );
  });
}
(mode === "setup" ? setup() : worker()).catch((err) => {
  emit({
    ok: false,
    error: {
      name: err.name,
      message: err.message,
      stack: String(err.stack).slice(0, 2500),
    },
  });
  process.exitCode = 1;
});
