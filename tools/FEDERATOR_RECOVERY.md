# Federator investigation and recovery

`federator_recovery.py` uses Python 3.8+ and its standard library. It inspects an
existing ETH–RSK or BSC–RSK mainnet federator through the local Docker Unix socket.
Diagnosis is the default. The selected repository, profile, container identity,
image and config/database mounts are checked before recovery. Duplicate mount
destinations and mounts beneath the protected config/database directories are
refused because they can override the inspected host files.

Run on the operator's own federator host. Local diagnosis needs Python and Docker
access. Recovery requires an interactive terminal as Ubuntu UID 1000, without
`sudo`. AWS secret recovery is the default for a missing key; it requires EC2
IMDSv2 and an installed AWS CLI with permission to read the instance's Name tag
and original signing secret. Other hosts use `--no-aws-secrets` and manually
restore the original key as described below. Existing keys are validated and
never overwritten. Non-AWS hosts still need the supported Linux Docker setup
and UID 1000 used by the existing application image.

Chain RPC checks connect directly to the configured endpoint, ignoring ambient HTTP proxy
variables and refusing redirects. Configure the final RPC URL and allow direct access from
the host. This does not change application or Datadog networking.

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

## Non-AWS hosts: restore the key manually, then start

Add `--no-aws-secrets` to disable all key-recovery EC2 metadata and AWS CLI
lookups. This also applies to guarded replay recovery. A missing key then stops
recovery with instructions; the helper never switches to AWS or generates a key.
A running container is left running even if its host key file is absent.

1. Obtain **this node's original federator private key** from the operator's
   existing secure backup or key custodian. Use the federator identity already
   authorized in the peer roster/contracts, not an administrative wallet key.
   A private key cannot be recovered from its public address or the blockchain.
   If no original key is available, stop and coordinate signer replacement.
2. For a stopped container, restore it with this hidden terminal prompt. Run in
   the same Bash shell where `TOOL` points to the verified helper. Do not put a
   key in a shell command, environment variable, chat or report. The supported
   owner is UID 1000 and the file mode is 600. Set `BRIDGE_PROFILE=bsc-rsk` for
   that separate deployment; confirm the exact container name if customized.

```bash
set -euo pipefail
export BRIDGE_PROFILE=eth-rsk
export FEDERATOR_CONTAINER=bridge-sc_federation_1
export TOOL
set +x
python3 - <<'PY'
import getpass, os, sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path(os.environ['TOOL']).parent))
import federator_recovery as r
node = r.Node(Path.home() / 'Bridge-SC', os.environ['BRIDGE_PROFILE'],
              os.environ['FEDERATOR_CONTAINER'])
if node.inspect()['running']:
    raise SystemExit('Container is running. Leave its key unchanged.')
if os.getuid() != node.expected_uid:
    raise SystemExit('Use the supported UID 1000 operator account, without sudo.')
key = r.safe_path(node.cfg / 'federator.key', node.cfg)
if key.exists():
    node.key_ready()
    print('Existing key preserved; verify its public signer before startup.')
else:
    warnings.simplefilter('error', getpass.GetPassWarning)
    value = getpass.getpass('Paste ORIGINAL federator private key (hidden): ')
    if node.inspect()['running']:
        raise SystemExit('Container started independently; key left unchanged.')
    r.install_key(node.cfg, value, node.expected_uid)
    del value
    node.key_ready()
    print('Original key installed privately. Public signer verification is next.')
PY
```

An invalid or empty existing file is refused; do not overwrite it or delete it
blindly. Stop and review that file locally. The input fails if terminal echo
cannot be disabled. The key is never printed by this procedure.

3. Verify the **derived public address** against the approved federator signer
   before startup. Enter only the public address at the prompt below. This
   isolated one-shot uses the existing pinned container image's ethers library,
   with no network or application entrypoint; it does not sign or start the
   federator. A mismatch is a stop condition.

```bash
set -euo pipefail
read -r -p 'Approved FEDERATOR public signer address: ' EXPECTED_SIGNER
[[ "$EXPECTED_SIGNER" =~ ^0x[0-9a-fA-F]{40}$ ]]
case "$BRIDGE_PROFILE" in
  eth-rsk) KEY_ENV=mainnet-ETH-RSK ;;
  bsc-rsk) KEY_ENV=mainnet-BSC-RSK ;;
  *) printf 'Unsupported bridge profile.\n'; exit 1 ;;
esac
ORIGINAL_IMAGE=$(docker --host unix:///var/run/docker.sock inspect "$FEDERATOR_CONTAINER" --format '{{.Image}}')
docker --host unix:///var/run/docker.sock run --rm --network none --read-only --log-driver none --cap-drop ALL \
  --security-opt no-new-privileges --user 1000:1000 --entrypoint node \
  --workdir /app/federator -e "EXPECTED_SIGNER=$EXPECTED_SIGNER" \
  --mount "type=bind,source=$HOME/Bridge-SC/federator-env/$KEY_ENV/federator.key,target=/run/federator.key,readonly" \
  "$ORIGINAL_IMAGE" -e '
try {
 const fs=require("fs"),ethers=require("ethers").ethers;
 const key=fs.readFileSync("/run/federator.key","utf8").trim();
 const address=new ethers.Wallet(key.startsWith("0x")?key:"0x"+key).address;
 if(address.toLowerCase()!==process.env.EXPECTED_SIGNER.toLowerCase()) throw new Error();
 console.log("Federator public signer matches:",address);
} catch (_) { console.error("Public signer verification failed; do not start."); process.exit(1); }
'
```

Continue only if that command succeeds. Then start the existing stopped node:

```bash
python3 "$TOOL" --bridge "$BRIDGE_PROFILE" --container "$FEDERATOR_CONTAINER" \
  --repo "$HOME/Bridge-SC" --recover --restart-only --no-aws-secrets
```

Approve the start prompt only after the signer matches. The same default
post-start watch runs; exit 3 means participation is not yet verified. No AWS
credentials or secret name is needed. This starts the existing image; use the
separate approved image-update procedure to install application fixes.

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
Unit tests use temporary fixtures, stub Docker/AWS operations and use only local fixtures
or ephemeral localhost servers for RPC transport checks:

```sh
python3 -m unittest discover -s tools/tests -v
python3 -m py_compile tools/federator_recovery.py tools/tests/test_federator_recovery.py
```
