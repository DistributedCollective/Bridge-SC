# Upgrade an existing ETH federator

The wizard replaces the ETH application and Datadog containers with pinned images,
preserving this node's configuration, original signer, database and bridge checkpoints.
Historical logs stay local; fresh persistent monitoring starts at current records.
The BSC application stays running.

## 1. Open the server shell

Use interactive Bash as `ubuntu` (UID1000). From a root shell, run `sudo -iu ubuntu`.
Use the coordinator's verified download block. No override file or manual upload is needed.

## 2. Run the wizard

Select your assigned `fed_n` label in the coordinator's block. That block supplies
your independently approved public signer. When run without it, the wizard requests
the expected public signer from your coordinator; local configuration alone is not proof.

- If Compose is missing, approve its verified installation.
- If requested, enter your own Etherscan API key through hidden input.
- Approve the planned upgrade when ready.
- The original signing file is reused when available. Otherwise the wizard discovers
  this instance's AWS secret/name, or asks for the original federator key privately.
- The Datadog key is recovered from the existing environment/configuration. Hidden
  input is requested only when it is unavailable.

The wizard verifies backups, recreates the ETH container and proves the signing key
matches the independently supplied public address and current configuration. It removes the temporary startup key after
90 seconds and fresh configuration-load proof, then replaces Datadog while retaining
its old container, image archive and volumes. Monitoring failure does not roll back
or restart the application.

An approved application image stays running. If only monitoring needs recovery,
the wizard replaces only Datadog. A healthy approved deployment is left unchanged.

## 3. Send the result

Keep the terminal open through the fifteen-minute watcher. Send the final application
and monitoring status, `summary.md`, and any exact error. Keep the private run directory
and backups until recovery is accepted. Datadog indexing and transfer settlement need
their own evidence; a running container alone does not establish either.

If the flow stops after changing services, send its last phase and error instead of
repeating the full upgrade. Do not send credentials or private configuration backups.

## If retained-history backup stops

During log export and verification, the wizard prints progress every 30 seconds.
A failure prints a safe reason and saves `history/progress.json` in the private run
directory. Send that reason and the run directory to the coordinator.

Use the coordinator's verified continuation for that saved run. It preserves any
incomplete archive, checks the original stopped container and checkpoints, and
completes the backup before continuing with key recovery, startup and the watcher.
It reuses the verified image backup and deployment plan. Do not rerun the full
upgrade or remove partial backups.

## Startup key cleanup, only when requested

Leave the node running and use its printed private run directory:

```bash
read -r -p 'Upgrade run directory: ' RUN_DIR
python3 "$RUN_DIR/federator_upgrade_safety.py" \
  --repo "$HOME/Bridge-SC" --finish-key-cleanup \
  --output "$RUN_DIR/startup-key-cleanup.json"
```

This accepts only the unchanged startup file and running process.

## Application rollback, only when requested

```bash
read -r -p 'Upgrade run directory: ' RUN_DIR
bash "$RUN_DIR/upgrade.sh" --rollback "$RUN_DIR"
```

Rollback verifies the archived image and launch plan and preserves current bridge
checkpoints. `--no-aws-secrets` skips AWS discovery for manual key recovery.

`--collect-only` saves a sanitized environment ZIP without changing services.
`--prepare-only` prepares checked files without opening the upgrade.
The wizard fills immutable tool/application revisions automatically; never edit scripts.
