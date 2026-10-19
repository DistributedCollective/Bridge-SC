# Upgrade an existing ETH federator

The wizard backs up the current image and logs, preserves bridge configuration and
checkpoints, recovers supported Datadog collection, upgrades the ETH application and
runs a fifteen-minute watcher. The tool revision and application image are pinned
separately. The BSC application is not restarted.

## 1. Prepare

Log in as the deployment user `ubuntu` (UID1000) and open interactive Bash. Have your
assigned `fed_n` label, existing public federator signer address, original signing-key
custody and your own Etherscan API key ready. Use the verified download block supplied
by the coordinator; it downloads and launches the approved wizard automatically.
No Compose override or manual file upload is needed.

If asked to collect first, the supplied command uses `--collect-only`. Return its
`federator-environment.zip`; this mode changes no services and asks for no keys.

## 2. Run the supplied upgrade block

The wizard requests any missing node identity and AWS/manual key-custody choice.
It checks the deployment and prepares the override automatically. If Compose v2 is
missing, answer `y` to install the checksum-verified plugin in your account and
continue in the same run. Docker services are not restarted for this installation.

The approved upgrader validates your existing Etherscan key or requests it through
hidden input. Do not send API keys or signing keys to the coordinator.

A supported stopped Datadog Agent is inspected first. Its checkpoint recovery occurs
within the confirmed upgrade, before the ETH application is stopped. Unsupported
settings are reported together; send only the error and printed report path.

## 3. Confirm the upgrade

At this prompt, type `y` when ready:

```text
Upgrade this ETH node and repair Datadog if needed in the agreed window now? [y/N]
```

The tool verifies the image backup, recovers Datadog if needed, preserves the existing
Agent state volume, stops only the ETH federator, archives its retained logs, restores
and verifies the original signing key, and starts the pinned repair image.

Approve restoration of your own original AWS secret when prompted. For manual custody,
enter your original signing key through hidden input. The temporary startup key is
removed after90 seconds and fresh proof that this process loaded its configuration.

## 4. Send the result

Keep the terminal open through the fifteen-minute watcher. Send its `summary.md` and
any exact error through the same channel that supplied the command. If `report.json`
is too large to attach, send its printed path with the summary. Keep the private run
directory and image/log backups until recovery is accepted.

If the flow fails after stopping services, send the last phase and error. Do not
repeat the full upgrade. The saved run supports guarded continuation or rollback.

## Startup key cleanup, if requested

Leave the node running and use its printed private run directory:

```bash
read -r -p 'Upgrade run directory: ' RUN_DIR
python3 "$RUN_DIR/federator_upgrade_safety.py" \
  --repo "$HOME/Bridge-SC" --finish-key-cleanup \
  --output "$RUN_DIR/startup-key-cleanup.json"
```

This accepts only the unchanged startup file and running process. Send any refusal;
do not delete a different key or rerun the upgrade.

## Rollback, when requested

```bash
read -r -p 'Upgrade run directory: ' RUN_DIR
bash "$RUN_DIR/upgrade.sh" --rollback "$RUN_DIR"
```

Add `--no-aws-secrets` for manual original-key recovery. Rollback verifies the saved
image and launch plan and preserves current bridge checkpoints. It does not clear
state or replay old monitoring logs.

`--help` describes optional wizard inputs. `--prepare-only` creates checked files
without installing Compose or opening the upgrade. Noninteractive upgrades are refused.
The lower-level executable accepts `--revision` for the tools and `--app-revision` for
the existing approved image source; the supplied wizard fills both automatically.
