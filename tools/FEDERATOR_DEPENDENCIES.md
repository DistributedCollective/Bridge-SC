# Federator dependency diagnostics

Use Git to fetch the reviewed helper on the existing operator host. It is a
single Python 3.8+ standard-library file; no installation, manual file transfer
or sibling helper is required. This fetch leaves the deployment checkout,
configuration, signing key, database and running image unchanged.

## Fetch and run the pinned diagnostic

**Publication gate:** the branch below must be published by the owner before
operators can fetch it. A local commit is not proof that it is available on
origin. Confirm origin is the operator-approved Bridge-SC repository first;
do not change its credentials or URL to bypass a failure.

Run in Bash as the existing Docker-capable deployment user. This ETH block
records the current host commit and running image BEFORE fetching. It executes
the verified helper directly from the immutable Git object, without creating a
script file or checking out another branch:

```bash
(
  set -euo pipefail
  umask 077
  FED_REPO="$HOME/Bridge-SC"
  FED_REVISION=SET_TO_REVIEWED_FULL_COMMIT
  [[ "$FED_REVISION" =~ ^[0-9a-f]{40}$ ]]
  FED_BRANCH=federator-diagnostics-recovery-upgrade
  FED_SHA256=ebd938e63fec9c8833dd582c628eec0eb384c8a7f9f0d811addfa38849d013e0
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  git -C "$FED_REPO" rev-parse HEAD
  timeout 10s docker --host unix:///var/run/docker.sock inspect bridge-sc_federation_1 \
    --format 'configured={{.Config.Image}} image_id={{.Image}} status={{.State.Status}}'
  git -C "$FED_REPO" fetch --no-tags origin "$FED_BRANCH"
  test "$(git -C "$FED_REPO" rev-parse --verify "$FED_REVISION^{commit}")" = "$FED_REVISION"
  git -C "$FED_REPO" merge-base --is-ancestor "$FED_REVISION" FETCH_HEAD
  test "$(git -C "$FED_REPO" show "$FED_REVISION:tools/federator_dependencies.py" | sha256sum | cut -d ' ' -f 1)" = "$FED_SHA256"
  FED_REPORT="$HOME/federator-eth-dependencies-$(date -u '+%Y%m%dT%H%M%SZ').json"
  if git -C "$FED_REPO" show "$FED_REVISION:tools/federator_dependencies.py" | \
      python3 - --profile eth-rsk --repo "$FED_REPO" --output "$FED_REPORT"; then
    FED_RESULT=0
  else
    FED_RESULT=$?
  fi
  printf 'Result: %s\nReport: %s\n' "$FED_RESULT" "$FED_REPORT"
  exit "$FED_RESULT"
)
```

Return the result and small JSON report. Exit 2 is warning/failure evidence, not
an instruction to restart. For the BSC control, use the actual BSC host and
replace `--profile eth-rsk` with `--profile bsc-rsk` and the report label with
`federator-bsc-dependencies`; use `--container` if its verified name differs.
Use `--versions-only` for metadata inventory. Stop on publication, checksum or
profile/mount failure.

## Source releases, images and checkpoints

A host Git commit and Docker image revision are separate. Fetching a source
commit or restarting the existing container does not install source repairs.
An application release must pair a reviewed source revision with a built,
native-tested immutable image digest; recreate only the selected federation
service with that image and its SAME existing configuration/database mounts.
Image update and activation need the approved release packet and real-host
canary. This diagnostic performs neither.

Checkpoint files are live per-node state, not Git release content. Record them
alongside image/source provenance in private diagnostics; keep the mounted
`db/lastBlock.txt` and `db/side-fed/lastBlock.txt` in place across image changes.
Do not commit or reset them, seed them from HEAD or copy another node's cursors.
A running process can advance its cursor during a read-only report; only a
confirmed worker stop permits a stable before/after replacement comparison.
Preserving an absent checkpoint also preserves the configured fromBlock
fallback; it is not permission to invent a current-head cursor. Secrets and
node-local databases are excluded from new Git additions, but ignore rules do
not protect already tracked files or a destructive shell command.

Do not use the existing `start.sh`/`reset.sh`/`stop.sh` for this release: their
chain removes containers, hard-resets the checkout and deletes scan state.

## Direct local invocation (optional)

If a reviewed helper is already present locally, run with local Docker access:

```sh
python3 federator_dependencies.py --profile eth-rsk --repo "$HOME/Bridge-SC" \
  --output "$HOME/federator-dependencies.json"
python3 federator_dependencies.py --profile bsc-rsk --repo "$HOME/Bridge-SC" \
  --watch 120 --samples 3 --output "$HOME/federator-watch.json"
python3 federator_dependencies.py --profile eth-rsk --repo "$HOME/Bridge-SC" --versions-only
```

The default container is `bridge-sc_federation_1`; `--container` selects another
existing container only when its config/database mounts match the profile.
Overriding descendant mounts, duplicates and replacement identities are refused.
`--output` exclusively creates a new mode-600 JSON file; existing files and
symlinks are refused. Without it, only summaries are printed. Review evidence
before sharing it; public identifiers and source checksums are retained.

The script reads restricted container state/image metadata, source and lockfile
hashes, Node/package versions, resource counters, database checkpoint numbers,
and aggregate fresh log markers. Host Git revision is separate from the image's
revision label and embedded source hashes. No environment dump or signing-key
file is read, and `config.js`/`peers.config.js` are parsed statically, never executed.
Timezone-free application log dates are explicitly uncertain; Docker dates are
used for freshness. Datadog output is limited to state/discovery and numeric
counters; this does not establish log delivery.

Network probes run inside the pinned existing container against its configured
chain endpoints. Requests have 5-second absolute deadlines and a 128 KiB body
limit, with at most three jobs running concurrently. Each runtime sample has a
deadline of at most 45 seconds, reduced to the host budget remaining, that
preserves checks already collected. Every completion flushes JSON and exits the
diagnostic child so pending DNS handles cannot keep it alive. The host command
budget is the greater of 90 seconds and `--watch + 50` seconds. Failed offline
versions utilities receive a separate cleanup attempt bounded to 3 seconds. `--watch` accepts
0..600 seconds and `--samples` accepts 1..3 (default 2); timeout or missing
observations are WARN/SKIP. No retries beyond those bounded samples are made.

Each chain checks both `eth_chainId` and `net_version`, head age/sync/gas, bounded
recent/configured/saved-cursor history, contract code/mapping/membership and both
bridge/federation owners. Public member lists are compared across the chains. The configured other-peer gate is compared with
`max(required, majority)-1`; either a smaller or larger gate is warned about.
An absent/nonmember signer label is WARN. ETH fee readiness separately requires a positive base fee in a block no older
than 120 seconds, matching the repaired builder; the general 300-second head
check is insufficient for that purpose. A valid configured public signer can be checked for membership, balance and
latest/pending nonce. That label does not prove which signing key is running.
The ETH historical sample also attempts a read-only destination
`getTransactionIdU` with a decoded Cross event, plus source transaction/receipt
reads. Empty history, ABI/version absence and incomplete probes do not prove
history completeness or transfer settlement.

ETH probes summarize deprecated Etherscan V1 responses and V2 with `chainid=1`.
Only `etherscan.key` may be read for the private V2 read API request. A credential
with a 64-hex signing-scalar shape, including an optional `0x` prefix, is refused
before any oracle request. Its contents, URL, provider messages and raw HTTP body
never enter the report. Response bodies are separate from internal transport
failure flags; unexpected provider failure fields produce fixed shape errors. BSC skips that
oracle. **Active P2P connections are always skipped:** unauthenticated TCP probes
may trigger remote authentication faults. Peer DNS and admitted-peer log evidence
are used instead.

For a stopped container, full network diagnosis is unavailable. Versions-only
may run a temporary, read-only, network-disabled container from the pinned local
image with no config/key mounts and logging disabled. That utility has a random
diagnostic-only name; if its Docker client fails, only that named utility is
removed. Existing service containers are never cleanup targets. The federator is never
started or restarted. No image pull, package installation, signing, vote,
broadcast, configuration/database write, wipe or telemetry submission occurs.
A stopped container remains FAIL even if its image versions are readable.

Exit 0 means the collected checks passed within their scope; exit 2 means FAIL
or WARN evidence; exit 1 is a guard/command failure. Partial private evidence is
retained on a failed diagnosis. These observations identify root-cause candidates,
not an automatically applied repair.

Tests stub Docker/network boundaries and exercise the embedded Node code locally:

```sh
python3 -m unittest discover -s tools/tests -v
```

Embedded Node tests require Node on PATH (or `FEDERATOR_TEST_NODE`); otherwise
those tests explicitly skip. Production probes use the container's own Node.
