# Federator environment capture and local replay

The upgrade launcher uses `federator_environment.py` as an immutable, hash-verified
component. Deliver both files with the reviewed Git download block. The coordinator
must verify the release commit is published before distributing that block.

## Operator

Use `--collect-only` to collect without upgrading. Missing anonymous node label is
prompted; signer, custody and credential prompts are skipped. Collection does not
require Compose to work. The existing operations lock prevents overlap with an
upgrade. No service is stopped, started, removed, recreated or reconfigured.

Only `federator-environment.zip` is intended for sharing. It contains `environment.json`
and `summary.txt` created0600 inside an exclusive0700 directory. Do not send raw
Docker inspect output, configuration, key files, logs, databases or backup archives.

## What is captured

- Host distribution/kernel version, architecture, CPU count, memory/swap and disk/inodes.
- Docker/client/API and Compose versions; current container/image/process identity.
- Useful runtime/resources, mounts, networking shape, labels/environment names and equality,
  and logging configuration. Secret values and arbitrary strings are withheld.
- Static public bridge configuration, cursor values and key-file metadata. Key files are
  inspected with lstat only, never opened. Configuration is parsed as data, never executed.
- Node/ABI/package versions and public repair-source hashes. A fixed bounded helper queries
  each configured RPC for chain/head and public Federation/Bridge/multisig state, without
  signing. URL credentials, paths, queries and hostnames are not exported.
- Agent version, topology/coverage, credential presence, log flags and the current source's
  registry schema/mode/offset when the Agent is running. A stopped or paused Agent is
  an explicit blocker; unavailable collection/credential/checkpoint evidence remains
  unknown. No intake credential value or other sources' data is exported.
- A matching retained original ETH upgrade, if available. Current Docker image metadata is
  used first; if pruned, only its digest-verified config JSON is read from the retained image
  archive. No image layers are loaded or extracted. `--previous-run` can choose a reviewed
  retained run explicitly; traversal and symlink escape are refused.

The fixed helpers clear preload settings. Python uses isolated mode without bytecode;
Node uses bounded regular-file reads, request deadlines and explicit helper termination.
Failures in independent probes are recorded as unavailable, preserving remaining evidence.

## Coordinator replay

Unzip only the two expected regular report files into an empty private directory. Run:

```bash
python3 tools/upgrade_eth_node.py --replay-environment environment.json
```

Replay treats the bounded JSON as data. It does not run Docker, connect to RPCs, load
modules from captured paths, run captured commands or apply captured settings. It reports
all deployment incompatibilities together for current and available original profiles.
Unknown/custom settings stay blocked until the coordinator prepares and tests their exact
preservation or a specifically approved change. A sanitized replay is not a deployable
configuration: replace real provider endpoints, credentials, peer addresses and state with
owned fixtures before constructing a local Docker reproduction.

## Limits

Collection and replay do not prove private-key custody, Etherscan entitlement, historical
RPC availability, live P2P participation, Datadog indexed delivery, pending transfer
settlement or successful startup with the repair image. Those checks and the existing
verified image backup, original-key proof/removal, Datadog preservation and watcher remain
part of the approved upgrade. The replacement plan explicitly preserves the
captured isolated IPC mode (`private` or `shareable`); host/other-container IPC
namespace access remains unsupported. A successful synthetic Docker test is not proof that an
uncaptured production host will upgrade smoothly.
