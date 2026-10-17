# One-command federator watcher

Run with Python 3.8 or later and local Docker access. Place the reviewed
`federator_watcher.py` and `federator_dependencies.py` together in the same tools
directory. The default repository is `~/Bridge-SC`; its selected config/database
mounts must match the existing source container before application probes or a
canary are allowed.

```bash
python3 tools/federator_watcher.py --operator fed_2
```

This observes the ETH/Rootstock federator and `datadog-agent` for 15 minutes.
Use the operator label belonging to this node; supported labels are `fed_2`,
`fed_1`, `fed_3`, `fed_4`, `fed_5` and `unspecified`. For BSC/Rootstock, add
`--profile bsc-rsk`. Alternate existing deployment names use `--container` and
`--agent`; alternate host checkout uses `--repo`.

The command prints its private evidence directory immediately, then a UTC
heartbeat after each sample. It writes `summary.md`, `report.json` and two
rotating timeline files. Review the summary first. It includes current status,
earlier observed crashes/OOM/identity changes, known application marker times,
failed dependency checks and evidence-backed next checks. Exit zero means the
observation completed; it does not mean the application or delivery is healthy.

## Observations and limits

Defaults are `--duration 900 --interval 60 --deep-every 300`. Duration zero
continues until Ctrl-C. Quick checks target each interval; slow bounded probes
can skip a scheduled interval, and actual sample intervals are recorded. Deep
read-only RPC/fee/history/contract/version checks run initially, every deep
interval and after a newly observed fatal marker. No peer TCP authentication
probe, signing, transaction submission, application restart, key fetch, image
pull or configuration/database edit occurs.

The report distinguishes source and Agent lifecycle, CPU/memory, host pressure,
storage capacity/inodes, bounded kernel errors, logging layout/readability,
source registration/tailer bytes, aggregate processing/sending and forwarder
counters. Inspection errors are unknown; a successfully confirmed absent
container is missing. Container ID/process start/file inode changes and counter
resets invalidate comparisons. Host Git HEAD, image labels/digests and embedded
source hashes are separate evidence about versions.

Only fixed marker classes, known stack frame names, numeric counters and public
identities are retained. Raw application/Agent logs, full environment, provider
response messages and credentials are not exported. Unknown Agent layouts or
status schemas stay unknown. Aggregate counters may include other containers;
they are never proof that this federator's logs were delivered. A single host's
peer timing cannot establish which node caused a historical crash or prove
quorum across nodes.

Command stdout and stderr are capped while streaming, with command-group
cleanup on timeout/overflow. Raw intermediate capture is memory only. The
rolling report retains 60 quick snapshots and three deep snapshots; timeline
segments are at most 8 MiB each and the JSON report at most 4 MiB. Continuous
runs intentionally discard older rolling evidence. Output directories are
private, newly created, reject symlink paths and use anchored directory writes.
Ctrl-C/SIGTERM preserves a partial report and cleans only the validated canary
belonging to this run. Existing services are never stopped or removed.

## Automatic delivery tests

Each run attempts at most one synthetic direct HTTPS intake event smaller than
1 KiB from the existing Agent. The API key stays inside that Agent. Its public
`DD_SITE` and effective Logs Agent endpoint must agree on one of the nine
allowed Datadog sites; otherwise authenticated probes are withheld. API-key
shape failures also withhold requests. TLS is verified, redirects/proxies are
disabled for direct tests and read searches, and submissions are never retried.
HTTP202 means intake acceptance only; it does not prove collection or indexing.

The watcher also creates at most one isolated stdout canary using the guarded
federator's already-local immutable image ID. Images declaring inherited
volumes are refused. The canary has no mounts, no network, a read-only root,
dropped capabilities and bounded memory/PIDs/log storage. Its ownership,
image, mount list and network are inspected before start. It prints one public
marker and stays alive silently for at most 150 seconds to allow discovery.
Cleanup is attempted after at least 120 seconds, or at interruption/end of a
short run; the exact owned name/CID is validated again before removal. Failed
cleanup remains explicit in the report. It never pulls an image or uses the
source database. A canary is not available on a fresh host without a guarded
existing federator container/image.

For automatic search confirmation, optionally place a Datadog application key
with `logs_read_data` scope in `~/.config/bridge-eth/datadog-read.key`. Only this
read-key filename is accepted by `--dd-app-key-file`; it must be a caller-owned
regular file with mode 0600, no symlink components and a 40-hex read credential.
A signing-scalar shape is refused. No federator key file is read. The read key
is passed to fixed Agent-side Python through stdin, never argv/env/code text.
The existing Agent environment API key authenticates official-site read-only
log search. At most three queries per five minutes look for the direct marker,
canary marker and exact current source CID/process epoch from this run. Only
matched counts and UTC timestamp bounds are returned. A missing read key,
HTTP404/authorization error or empty result is unknown visibility, not proof of
non-delivery. The summary prints exact human search queries when automatic
visibility is unavailable. FOUND proves the matched log was indexed and
accessible through that API scope; it does not prove every source log arrived.

## Optional historical window and offline comparison

Append explicit UTC instants to the same command:

```bash
python3 tools/federator_watcher.py --operator fed_2 \
  --incident-since "$INCIDENT_SINCE_UTC" --incident-until "$INCIDENT_UNTIL_UTC"
```

Both values must be ISO UTC timestamps ending in `Z`. The watcher makes one
bounded historical Docker-log/event/kernel snapshot. It captures at most 1,000
log lines per current container, with an eight-second log deadline; it does not
scan an entire large log file. Rotation, replacement, privilege and retention
can hide older evidence. Historical capture is explicitly partial; missing
records cannot prove a cause. It sends no historical logs to Datadog.

To merge reviewed watcher directories locally, without Docker or network:

```bash
python3 tools/federator_watcher.py --analyze "$NODE_A_REPORT" "$NODE_B_REPORT"
```

Only bounded UTC/public-ID/marker summaries enter the coordinator report.
Cross-node temporal order remains correlation, not attribution of fault.

## Isolated tests

```bash
python3 -m unittest discover -s tools/tests -p test_federator_watcher.py
```

Docker, Agent, HTTP and dependency RPC fixtures are isolated. Local subprocess
fixtures prove timeout, streaming-size and descendant cleanup. No live service
or Datadog event is contacted by the tests. Actual deployed Agent status
schemas, Docker/Node runtime compatibility and Datadog organization/access
must be established by an operator run; unit tests do not claim that integration.

## Etherscan request budget

Use a dedicated Etherscan key for this node, separate from other applications
and operators. The normal gas poll stays at five seconds (at most17,280 reads
per day); slower configured polls remain slower. Invalid/faster gas intervals
fall back to five seconds. Average sampling remains ten seconds and the average
window remains four hours. Per-transfer fresh fee reads use the configured
Ethereum RPC, not Etherscan.

Deep watcher checks default to300 seconds (at most288 keyed V2 reads/day for
one continuously running watcher). `--deep-every` cannot be less than60 seconds,
and new fatal markers cannot trigger deep checks more often than that minimum.
Even at that minimum, one gas poller plus one watcher uses at most18,720 keyed
reads per day in a sustained run. The retired V1 comparison is unkeyed. API
failures do not trigger an immediate retry loop. Repeated process restarts,
multiple watchers or other software sharing a key add traffic outside this
single-node budget; the code does not reserve an account-wide daily quota.
