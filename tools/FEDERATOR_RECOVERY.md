# Federator investigation and recovery

`federator_recovery.py` uses Python 3.8+ and its standard library. It inspects an
existing ETH–RSK or BSC–RSK mainnet federator through the local Docker Unix socket.
Diagnosis is the default. The selected repository, profile, container identity,
image and config/database mounts are checked before recovery. Duplicate mount
destinations and mounts beneath the protected config/database directories are
refused because they can override the inspected host files.

Run on the operator's own federator host. Local diagnosis needs Python and Docker
access. Recovery requires an interactive terminal as Ubuntu UID 1000, without
`sudo`. Restoring a missing key additionally requires EC2 IMDSv2 and an installed
AWS CLI with permission to read the instance's Name tag and original signing
secret. Existing keys are validated and never overwritten.

## Fetch a reviewed revision

Obtain the reviewed branch and its **full commit ID** through your review process.
The following extracts the helper and its usage document into a new private
folder. It does not check out a deployment branch or overwrite application,
configuration, database or image files.

```sh
set -eu
BRIDGE_REPO="$HOME/Bridge-SC"
REVIEWED_BRANCH='REPLACE_WITH_REVIEWED_BRANCH'
REVIEWED_REVISION='REPLACE_WITH_FULL_REVIEWED_COMMIT'
git -C "$BRIDGE_REPO" fetch --no-tags origin "$REVIEWED_BRANCH"
test "$(git -C "$BRIDGE_REPO" rev-parse --verify "$REVIEWED_REVISION^{commit}")" = "$REVIEWED_REVISION"
git -C "$BRIDGE_REPO" merge-base --is-ancestor "$REVIEWED_REVISION" FETCH_HEAD
TOOL_DIR="$(mktemp -d "$HOME/federator-recovery.XXXXXX")"
chmod 700 "$TOOL_DIR"
git -C "$BRIDGE_REPO" show "$REVIEWED_REVISION:tools/federator_recovery.py" > "$TOOL_DIR/federator_recovery.py"
git -C "$BRIDGE_REPO" show "$REVIEWED_REVISION:tools/FEDERATOR_RECOVERY.md" > "$TOOL_DIR/FEDERATOR_RECOVERY.md"
TOOL="$TOOL_DIR/federator_recovery.py"
python3 "$TOOL" --version
sha256sum "$TOOL"
```

Compare the checksum with the reviewed candidate's checksum. Keep the printed
version and selected revision with your private operator notes.

## Diagnose locally

```sh
python3 "$TOOL" --bridge eth-rsk --repo "$HOME/Bridge-SC" --local-only
python3 "$TOOL" --bridge bsc-rsk --repo "$HOME/Bridge-SC" --local-only
```

The default container name is `bridge-sc_federation_1`; use `--container NAME` if
this host uses another existing container. Mounts must match the selected profile.
Local mode opens no chain RPC clients. It reports container/key metadata, saved
cursors, configured fallbacks, peer/role/scan messages and authentication/crash
context. An absent follower cursor or directory stays absent. Historical catch-up
from the configured fallback may still be required.

For a private JSON report, explicitly choose a new filename:

```sh
python3 "$TOOL" --bridge eth-rsk --repo "$HOME/Bridge-SC" --local-only \
  --report "$HOME/federator-diagnosis.json"
```

A report is created exclusively with mode 600. Existing files, report symlinks
and symlinked report parents are refused. No report is created without `--report`.
Reports contain capture duration/failures, container/key metadata, cursors and
separate node participation and transfer completion results. Key contents and
raw environment dumps are withheld.

By default, log capture covers the last 15 minutes, with a 2000-line tail,
15-second Docker timeout and 1 MiB retained-text limit. A historical window must
specify both offset-aware instants, in increasing order, no more than 24 hours
apart. Substitute the UTC instants you need:

```sh
LOGS_SINCE='REPLACE_WITH_START_ISO_INSTANT_ENDING_Z'
LOGS_UNTIL='REPLACE_WITH_END_ISO_INSTANT_ENDING_Z'
python3 "$TOOL" --bridge eth-rsk --repo "$HOME/Bridge-SC" --local-only \
  --logs-since "$LOGS_SINCE" --logs-until "$LOGS_UNTIL" \
  --report "$HOME/federator-window.json"
```

Offsets are normalized to UTC. Capture failure/timeout is reported as unavailable;
it is never treated as successful empty evidence. Reports preserve authentication
exception lines and stack context, including `RSKKeyedAuth`, `TypeError`,
`ataraxia` and npm errors. Known credential fields, URLs, AWS access-key shapes
and 64-hex values are redacted; this also hides some public identifiers. Arbitrary
text may contain other sensitive information. **Review the whole report before
sharing it.** Historical peer messages cannot establish current participation.

## Restore the original key and start the existing container

```sh
python3 "$TOOL" --bridge eth-rsk --repo "$HOME/Bridge-SC" \
  --recover --restart-only --report "$HOME/federator-start.json"
```

For BSC use `--bridge bsc-rsk`. This route requires no chain RPC. A running
container is left running, even if its host key has been removed. A stopped
container is started only after its original key is available and validated.

If the key is missing, expect separate confirmations to discover the local EC2
instance, approve its Name-tag secret mapping for the selected bridge, and start
the pinned existing container. Blank or No declines an action. Failed or declined
key restoration prevents start. Invalid scalars, unsafe paths, wrong ownership
or mode, and changed mounts/container/image/directory identities abort recovery.
No new signing identity is generated.

Restart-only does not edit database or configuration files. It leaves absent
cursors and configured fallbacks unchanged before start, creates no database
backup and never asks for a checkpoint seed. After start the application resumes
normal progress and may update or create cursors. Log export failure does not prevent this route from
starting a valid stopped container. The subsequent watch uses fresh local logs
and the static configured other-peer gate; it does not verify chain membership
or settlement. Default watch is 600 seconds (`--watch-seconds 0..3600`). It
requires two distinct fresh role polls from the same current process run, with
fresh peer evidence at the configured threshold. Peer joins and scan lines do
not count as new role polls; a process restart resets accumulated readiness.
The helper performs no additional restart or cursor change when the watch times
out.

## Check transfers or use guarded replay separately

Default chain diagnosis makes explicit read-only RPC calls to the configured
endpoints and checks chain IDs, contracts, receipts and source confirmations:

```sh
EXTERNAL_TX='REPLACE_WITH_EXTERNAL_SOURCE_TRANSACTION_HASH'
python3 "$TOOL" --bridge eth-rsk --repo "$HOME/Bridge-SC" \
  --no-scan --tx "$EXTERNAL_TX"
```

Repeat `--tx` for external-source transfers, or use `--rootstock-tx` for
Rootstock-source transfers. Without `--no-scan`, a recent source audit is bounded
by `--lookback` (default 1000 blocks) and `--max-pages` (default 100 pages of 100
blocks). RPC rejection, timeout or incomplete audit means the relevant chain
state is unknown. It does not establish a replay frontier or settlement.

`--recover` **without** `--restart-only` retains the guarded interactive replay
workflow. This mode depends on RPC availability, asks whether to preserve each
cursor, and requires explicit source-block selection and typed confirmation for
changes. Missing or forward-moving cursors require a specific older-deposit
completeness statement. It creates temporary private database copies, stops a
running container before cursor edits, rechecks source anchors, and rolls back
its exact writes if an installation fails. Use it only with reviewed replay
evidence. Ordinary original-key restoration and start use `--recover
--restart-only`, which creates no database copies. The replay route is not
recommended for routine recovery when no cursor edits are intended.

The replay copies are temporary rollback material. Retain them while recovery
has failed or remains unverified and rollback may still be needed. After the
relevant cursor recovery and any affected transfers are verified, manually
remove only `db-before` and `db-after-stop` inside the **exact private evidence
directory printed by this recovery run**. Preserve the live mounted database
and sanitized support evidence, including `logs.txt`. The helper does not
automatically clean up these copies.

Local/restart-only modes reject transfer hashes, completed anchors, `--lookback`,
`--max-pages` and `--no-scan`. Run the separate chain diagnosis command for those
checks. Process start and local peer participation are separate from supplied
transfer completion.

## Results and verification

Exit 0 means diagnosis completed or the requested watch verified participation
and any supplied targets. It does not claim settlement when no target was
checked. Exit 1 means an operation/guard failed; inspect current state before
retrying. Exit 2 means invalid arguments or a noninteractive/wrong-UID recovery
request. Exit 3 means participation or transfer completion remains unverified at
the watch deadline. Exit 130 means interrupted input; inspect the existing
container before repeating actions.

The helper contains no Git pull/reset, image updates, container removal,
restart-policy changes, Datadog edits, manual votes or signing/broadcast commands.
Unit tests use temporary fixtures and stub all Docker, AWS and RPC operations:

```sh
python3 -m unittest discover -s tools/tests -v
python3 -m py_compile tools/federator_recovery.py tools/tests/test_federator_recovery.py
```
