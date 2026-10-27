# Versioned Datadog checks for ETH federators

These tools operate on the existing local `datadog-agent` and
`bridge-sc_federation_1` containers as the normal Docker-capable deployment user.
Fetch/extract them from an owner-published immutable Bridge-SC revision; never
run an unreviewed moving branch as a credential-bearing probe.

## Read collection and sender state

```bash
bash tools/dd-diagnose.sh
```

This captures current source identity/log driver, Agent mounts/settings,
selected credential/forwarder/Logs Agent status, small log tails, storage and
three-minute collection/sending deltas. `--no-wait` gives one snapshot only.
It creates a private report directory and removes raw intermediates on exit.
Return only its reviewed `report.txt`, not the raw directory or environment.
Missing/status-timeout/skipped checks are unknown, not passes. This tool does
not restart services, clear registry state or send a synthetic log. Its optional
US1 validation reads only the existing Agent environment API key; another site
requires its own confirmed effective endpoint. Site/proxy differences are
reported, not automatically changed.

## Send one bounded direct-intake event

Choose the exact Datadog site for the intended organization and this node's
operator. Each execution sends at most one log smaller than 1 KiB, not old
Docker history:

```bash
bash tools/dd-send-test.sh --site datadoghq.com --operator fed_1
bash tools/dd-send-test.sh --site datadoghq.com --operator fed_2
```

Use the relevant one command, not both on one host. Other node labels are
`fed_3`, `fed_4` and `fed_5`; omitted labels become `unspecified`.
The API key stays in the existing Agent environment, never command arguments
or printed output. Only allowed official sites/operators are accepted. TLS is
verified, redirects/proxies disabled for this direct test, and no automatic
retry occurs. The script prints a UUID marker/current UTC and search query.
A timeout may leave an exec briefly pending: search its marker before retrying.

HTTP202 means acceptance for processing. Confirm that exact marker in the
intended organization's Live Tail and Explorer. This bypasses Docker collection
and the Agent sender, so also verify new real federator logs, source-specific
reading and advancing sender counters. Live Tail success with missing Explorer
points to indexes/exclusions/quota/access. API authorization or network failure
is separate from a peer/quorum/application failure.

Secrets belong to operator custody. Etherscan read API keys, Datadog API keys,
RPC credentials, federator signing keys and administrative multisig keys are
separate credentials; no key conversion or interchange is performed by these
tools. Do not print full Agent status/config or raw provider errors.

## Local test

```bash
python3 -m unittest discover -s tools/tests -p test_dd_send_test.py
bash -n tools/dd-diagnose.sh
bash -n tools/dd-send-test.sh
```

The automated intake checks use fake HTTP and a fake Docker client, including
operator attribution, bad inputs, one-request limits, redirects/proxies,
credential privacy and ambiguous failure. No actual Datadog event is sent.
