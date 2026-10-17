# Upgrade an existing ETH federator

The single-file [upgrade wizard](upgrade_eth_node.py) checks your existing deployment,
prepares its Compose override automatically and runs the approved upgrade. It backs up
the old image and retained logs, preserves bridge configuration/checkpoints, checks
Datadog and runs the watcher. It uses a separately pinned, already-published application
release; updating this launcher does not require rebuilding the application image.

## 1. Have these ready

- Access to the ETH server as `ubuntu`, UID1000, using interactive Bash.
- The reviewed `upgrade_eth_node.py` file supplied by your release coordinator.
- Your assigned `fed_n` label and existing public **federator** signer address.
- Access to your original federator key and your own Etherscan API key.

Save the supplied file as `~/upgrade_eth_node.py`. Your coordinator provides the
file checksum, node label/address and signing-key custody method. You do not need
to prepare, download or enter a Compose override file. The launcher checks startup,
environment, mounts, networking and resource settings directly on this server.

## 2. Run your supplied command

Run:

```bash
python3 ~/upgrade_eth_node.py --upgrade
```

Missing node label, public federator address and AWS/manual custody are requested
with validation; invalid answers are re-prompted without echoing them in errors.
Use the public federator address from your supplied node table, not a private key.
Four numbered stages identify the node, check the account/repository/lock, audit
and prepare the approved package, then open the approved upgrader.

For a natural interactive wizard, omit `--upgrade`. After preparation it asks
`Open the approved upgrade now? [y/N]`; answering y continues with the same prepared
packet. The approved upgrader still asks its separate maintenance confirmation
before stopping services. Explicit `--prepare-only` finishes after checks/files,
without an upgrade decision or handoff. Fully specified noninteractive use also
prepares only; noninteractive `--upgrade` is refused.

`--operator`, `--expected-signer`, `--aws-secrets` and `--no-aws-secrets` can supply
known values directly. The signing key itself is requested only through the
approved upgrader's hidden prompt. The launcher checks image identity itself;
no preliminary manual `docker inspect` command is needed.

If an earlier run is still at `Absolute path to supplied Compose override:`, press
Ctrl+C there first. At that input prompt, no service changes have started. If an
older run already reached stopping/replacement, keep that run and send its last
phase to the coordinator; do not launch a second upgrade.

Unsupported/custom settings stop preparation before service changes. Send the
printed error to the coordinator in the same channel where you received the
command; no separate manual check or raw environment dump is requested.
If Compose v2 is missing, the launcher prints an exact `--install-compose` command.
Run it, then repeat your original upgrade command. The installer verifies pinned
Compose2.40.3, respects `DOCKER_CONFIG`, and does not restart Docker.

## 3. Answer the upgrade prompts

The executable reuses your Etherscan key, or requests it through hidden input.
After prerequisite checks, it asks:

```text
Upgrade this ETH node and repair Datadog if needed in the agreed window now? [y/N]
```

Type `y` when ready for the maintenance window. The executable backs up the old
image/logs, stops only the ETH federator, restores/verifies your original key,
starts the repaired image and removes the temporary key after90 seconds and
fresh configuration-load proof. Approve original AWS secret restoration if
using AWS custody; otherwise enter your original key at the hidden prompt.
Datadog credentials and its retained checkpoint volume are handled by the tool.

## 4. Send the final result

Keep the terminal open through the fifteen-minute watcher. Send `summary.md` and
any error to the coordinator through the same channel that supplied this command.
If `report.json` is too large to attach, send its printed path with the summary.
Keep the private run directory and image/log backups. On a failure, send the exact
error and last phase; do not repeat the full upgrade after a service-stop phase.

Use `--help` for wizard, preparation and advanced parameters; `--version` prints
the launcher version without accessing Docker. The lower-level `upgrade-eth-federator.sh --override`
interface remains available for separately reviewed custom deployments.

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
