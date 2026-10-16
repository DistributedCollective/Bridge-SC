# Repair existing ETH federator log shipping

`dd_agent_recovery.py` changes only a stopped Datadog Agent. The existing ETH
federator must remain running. It preserves local logs, bridge state, Agent
image and credentials. Use Linux Python 3.8+ as the UID 1000 deployment user
with Docker Unix-socket access.

## Run

Copy this standalone file onto the server, then run:

```bash
python3 ~/dd_agent_recovery.py --repair
```

The tool backs up Agent configuration and registry privately, records a one-time
cutover at the current complete Docker-log record, advances only that source's
monitoring offset, moves the registry into the existing Agent log volume, and
resumes the same Agent. It confirms that source's acknowledged offset advances.
Old logs stay local. Records before the cutover are intentionally not resent.
No image pull, bridge restart, database edit, log truncation or container
replacement occurs.

Send only `report.json` and `failure.json` if present, from the printed directory.
Keep configuration/context/registry backups private: the original YAML may
contain credentials. Every apply attempt has its own private `attempt-*` directory with a phase and
exact sanitized failure reason. Earlier reports and backups are retained.
For a stopped Agent that never started during the repair, repeat the same
`--apply` command: the tool accepts only unchanged original files or the exact
journalled patch, completes missing recognised writes and retains the original
cutoff. Unknown/changed state is refused; never delete the attempt marker.

To prepare evidence without changing or starting the Agent, omit `--repair`.
The tool prints an exact `--apply` command for that private packet.

## Supported scope

- Agent 7.33+ with registry schema 2 and a verified numeric Docker JSON-file source.
  Normal saved tailing modes include the empty default, `beginning`, and `end`;
  forced/unknown modes are refused.
- Stopped root-run Agent using its normal main configuration path, with a writable
  Docker volume mounted at `/var/log/datadog`. The main YAML may be a regular
  file or the standard link to `/etc/datadog-agent/datadog-docker.yaml`; the link
  is preserved and its unmounted regular target is backed up and patched.
- Existing `bridge-sc_federation_1` with the standard ETH config/DB mounts.
- No conflicting registry/integration-path override, forced replay configuration,
  custom launcher, shadow mount or ambiguous legacy socket cursor. Unsupported collection modes stop before applying a patch.

A changed process/container, rotated log or unrecognised packet/config is refused.
An existing persistent registry is accepted only on a stopped pre-start retry
when it exactly matches that packet's intended patch. The source log is read only through a bounded
tail; the signing key is never read.

## Future Agent replacement

The latest attempt directory contains `future-agent-override.private.json`,
which explicitly reuses the existing log volume
and registry path. The coordinator must integrate it with the actual deployment
before any later Agent recreation. Ordinary restarts of the patched Agent retain
its current registry. Removing containers/volumes through legacy reset scripts
is outside this workflow.

Registry progress does not prove indexed visibility. Verify fresh source records
in Datadog and check any exhausted indexing quota separately. The old application
and its gas/peer behavior are unchanged.

## Manual verification

The unit suite is part of `tools/tests`. The isolated Agent smoke is manual only:

```bash
python3 tools/tests/dd_agent_cutover_smoke.py \
  --agent-image LOCAL_IMMUTABLE_AGENT_IMAGE \
  --evidence-dir /private/tmp/dd-cutover-proof
```

It uses dummy credentials, an internal Docker network, one dedicated test log
and local receiver; no production telemetry or host Docker socket is mounted.
It checks cutoff, fresh delivery, normal restart, Agent recreation with explicit
state-volume reuse, and preservation of the test application process/data/logs.
Only its owned lab resources are removed. Images must already be local.

Collector offset precedence is documented in [Datadog log start positions](https://docs.datadoghq.com/agent/logs/#start-position).

## ETH upgrade integration

`upgrade-eth-federator.sh` bundles this repair and `federator_datadog_upgrade.py`
at the same pinned revision. Read-only preflight precedes application downtime.
After upgrade confirmation/image backup, compatible unrepaired Agents use the
existing prepare/apply flow; repaired running Agents keep their current cutoff.
The private upgrade packet stores the explicit existing-volume/path override
and verifies Agent identity/config/integrations/checkpoint retention after
application upgrade and rollback. Unsupported or stopped Agent setups are
prerequisites; the executable does not replace the Agent image.
