# Three-federator Docker recovery lab

This is an isolated integration test of the bridge application's P2P signature
exchange and transaction processing against deployed contract state on local
Ethereum and Rootstock forks. It never submits a transaction to an upstream RPC.
It is not a production image or an automatic node recovery command.

## Build and run

Requirements: Python 3.8+, Git, a running Linux Docker engine, network access for
public build artifacts and a Rootstock RPC supporting historical event logs and
fork state. No real signing keys, Etherscan key or Datadog key are needed.

From the reviewed Bridge-SC checkout:

```bash
python3 tools/build_fork_lab.py --image bridge-fork-lab:local
python3 tools/fork_lab.py --docker-image bridge-fork-lab:local \
  --inputs "$EVENT_MANIFEST" \
  --eth-block "$ETH_FORK_BLOCK" --rsk-block "$RSK_FORK_BLOCK" \
  --eth-upstream "$ETH_ARCHIVE_RPC" --rsk-upstream "$RSK_ARCHIVE_RPC"
```

Choose fixed, settled fork blocks containing the source events and enough
confirmations. Choose the destination snapshot before execution when testing a
previously completed event; otherwise the application correctly skips it.
Historical Rootstock event queries require a capable provider. Chain identity,
Anvil identity and canonical pinned block hashes are verified before local setup.
A mismatch stops the run. Endpoint availability failures are test limitations,
not a diagnosis of the production operator's RPC.

The manifest is JSON containing `events`, with between one and fifty entries:

```json
{
  "events": [
    {"chain": 1, "tx": "SOURCE_TRANSACTION_HASH", "id": "OPTIONAL_FEDERATION_ID"},
    {"chain": 30, "tx": "SOURCE_TRANSACTION_HASH", "id": "OPTIONAL_FEDERATION_ID"}
  ]
}
```

The receipt-and-balance evidence gate currently covers18-decimal ERC20 token
fixtures, including the supplied BOS/SOV transfers; native-coin and other-decimal
fixtures need separate balance adapters. Replace the placeholder hashes with
full public32-byte hex hashes. Chain1 is
Ethereum-source; chain30 is Rootstock-source. Source receipt, Cross event and
optional federation ID are checked. Transfer amount, receiver, processed flags,
bridge/token bytecode and token limits are not overwritten.

## What the test proves

- Three separate containers use distinct disposable keys and databases, actual
  native transport, authenticated peers and real Federator/TransactionSender
  modules. Each sees two other peers before replay.
- The old transport callback is re-entered while its native remote public binding
  is unavailable. The baseline must exit with the historical null-binding error;
  the repaired worker must survive. This controlled callback trigger tests failure
  handling; it does not establish the original host/network trigger.
- A peer leaves during an actual signature request. Processing must fail without
  completing the transfer, all workers must survive, and reconnection must restore
  three peers before retrying.
- A local Etherscan fixture tests V2 chain selection and fractional quote handling,
  and a rejected/deprecated response remains caught. This does not test a real
  operator's Etherscan account entitlement or connectivity.
- A simulated5-Gwei Ethereum base fee compares the old insufficient fee cap with
  the repaired fresh-RPC calculation. The real event replay then signs and submits
  destination transactions on the forks.
- The bounded private report records initial/final flags, public signature metadata,
  three votes, local execution receipts/logs, receiver token balances, exits and
  the image identity. Inspect `status`, outcomes and cleanup errors; a completed
  test is not proof of production deployment or recovery.

The setup changes only local federation membership to three generated signers,
keeping required3, and funds those test accounts. It uses the actual deployed
contracts. Signer-roster replacement affects how old votes are counted; an
already-processed event can therefore have zero votes from the *new* test roster.

## Isolation and cleanup

Workers and forks share an internal Docker network with no published ports. Only
an upstream relay has egress, with a read-only RPC method allowlist. Local writes
are confined to attested owned forks. Worker mounts contain only their own
configuration/key and own disposable database. Host operator configs, keys and
live databases are excluded from the image build context.

Cleanup validates the run's exact ownership label before removing containers and
networks. Disposable keys and databases are deleted; bounded proof is retained
in the private printed directory. Existing Docker MCP, editor, agent and bridge
containers are outside the cleanup scope. An interrupted Python process that
cannot run its `finally` block may require inspection of its exact owner label;
do not use `docker system prune`.

After retaining the reports and finishing all runs, inspect and remove the lab
image you built:

```bash
docker --host unix:///var/run/docker.sock image inspect bridge-fork-lab:local \
  --format '{{.Id}} {{index .Config.Labels "bridge.lab.build"}}'
# Continue only for the reviewed lab image, with no running lab containers:
docker --host unix:///var/run/docker.sock image rm bridge-fork-lab:local
```

Preserve ordinary base-image/build caches. No global Docker cleanup is needed.

## Runtime limits

The builder pins the Node22 base digest, npm lock graph and official Anvil1.3.5
archive checksums for ARM64/AMD64. The recorded integration execution is ARM64;
AMD64 has a checksum-pinned build path but needs its own execution evidence.
This lab does not certify compatibility with an unknown production image,
production scheduler startup, production confirmation amount tiers, long-running
catch-up/checkpoint scheduling, Rootstock consensus or actual host pressure.
Rootstock's minimumGasPrice header is supplied by the test relay from the
canonical Rootstock pin because Anvil omits that Rootstock field.

## Datadog separation

This lab does not automatically upload any logs. Use the separate node watcher
for the real Agent's source, sender, intake and indexing diagnosis. Its small
synthetic events use `service:bridge-federator-watcher`; exclude them with
`-service:bridge-federator-watcher`. If optional lab summaries are separately
submitted, label them `service:bridge-fork-lab` and `lab_run:<run-id>`; include
that query or exclude `-service:bridge-fork-lab`. Never upload fixture keys,
private config or raw collected logs as a test event.

## Controller regressions

```bash
python3 -m unittest discover -s tools/tests -p test_fork_lab.py
```

These verify upstream write rejection, local receipt routing, ownership cleanup,
fatal stderr retention, manifest handling and exclusion of operator secrets.
They do not replace a real Docker integration run.
