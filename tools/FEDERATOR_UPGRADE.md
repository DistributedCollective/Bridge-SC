# Upgrade an existing ETH federator

Updates your ETH federator, backs up its image and retained local logs, checks its keys and runs the
federator/Datadog watcher. It repairs Datadog when needed, preserves an already
repaired Agent and its checkpoint volume, and keeps the existing bridge
configuration and database.

## 1. Log in

Log into your ETH server as the deployment user and open Bash.
Get your per-node upgrade package from the release coordinator before continuing:

| Input | What the coordinator supplies |
| --- | --- |
| Release commit | The exact approved Git commit, matching the application image. |
| Image | The published Docker image name with its `sha256` digest. |
| Host override file | A ready-to-use Compose file for your server, plus where to save it. Enter its full saved path. |
| Node label | Your assigned `fed_1`–`fed_5` label. |
| Federator address | Your existing public federator signer address, verified against the node register. |

The coordinator prepares the image and override file and sends them with these
values. Use the public federator address for the identity input.

## 2. Fetch and run

```bash
cd ~/Bridge-SC
git fetch origin federator-diagnostics-recovery-upgrade
UPGRADE_DIR=$(mktemp -d)
git show FETCH_HEAD:tools/upgrade-eth-federator.sh > "$UPGRADE_DIR/upgrade.sh"
bash "$UPGRADE_DIR/upgrade.sh"
```

Without an AWS signing-key secret, use this instead of the last line:

```bash
bash "$UPGRADE_DIR/upgrade.sh" --no-aws-secrets
```

## 3. Answer the prompts

Enter the supplied values and confirm the agreed upgrade time.
The executable reuses your Etherscan key; if missing, enter it at the hidden
prompt. Use your original federator signing key when asked. Keep the terminal open:
the executable verifies startup and removes the temporary signing key after
90 seconds. Datadog reuses its
existing API key; the executable handles its checks and repair. Unsupported Agent
versions or collection setups stop at preflight before either service is stopped.

## 4. Return the reports

Leave the watcher running for fifteen minutes. Send `summary.md`, `report.json`
and any error from the paths it prints. Keep the private run directory and
image/log backups. On an error, stop and send the error before retrying.

## If startup key cleanup is pending

Leave the node running. Use the saved run directory printed by the upgrade:

```bash
read -r -p 'Upgrade run directory: ' RUN_DIR
python3 "$RUN_DIR/federator_upgrade_safety.py" \
  --repo "$HOME/Bridge-SC" --finish-key-cleanup \
  --output "$RUN_DIR/startup-key-cleanup.json"
```

This finishes only the unchanged startup key for the same running process after
its configuration-load message is verified. Send the result. If refused, send the
error and cleanup report to the coordinator. Do not rerun the full upgrade.
Older reports lacking cleanup metadata require coordinator review.

## Rollback, when requested

```bash
read -r -p 'Upgrade run directory: ' RUN_DIR
bash "$RUN_DIR/upgrade.sh" --rollback "$RUN_DIR"
```

Add `--no-aws-secrets` for manual signing-key recovery. Return the report paths
printed by the executable. Use `--help` to see optional runtime arguments.
