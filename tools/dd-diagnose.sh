#!/usr/bin/env bash
# Read-only diagnostics for your existing ETH federator/Datadog agent.
# No service restart, configuration write, key-file access or log submission.
set -u
set -o pipefail
umask 077

if [[ ${1:-} == --help ]]; then
  printf 'Usage: %s [--no-wait]\nDefault: checks, 3-minute observation, second snapshot.\n' "$0"
  exit 0
fi
wait_seconds=180
if [[ ${1:-} == --no-wait && $# == 1 ]]; then
  wait_seconds=0
elif [[ $# != 0 ]]; then
  printf 'Unknown option. Use --help.\n' >&2
  exit 1
fi
for program in docker timeout sed grep tail df mktemp date sleep tee tr rm; do
  if ! command -v "$program" >/dev/null; then
    printf 'Required command missing: %s\n' "$program" >&2
    exit 1
  fi
done

work=$(mktemp -d "$HOME/dd-diagnostics.XXXXXX") || exit 1
report="$work/report.txt"
raw="$work/command.raw"
status_raw="$work/status.raw"
probe="$work/probe.py"
: > "$report"
cleanup() { rm -f -- "$raw" "$status_raw" "$probe"; }
trap cleanup EXIT
trap 'printf "Interrupted; partial report: %s\n" "$report"; exit 130' INT TERM

safe() {
  sed -E 's/[[:xdigit:]]{32,64}/[hex value redacted]/g; s#https?://[^[:space:]]+#[URL redacted]#g; s/(API [Kk]ey ending with )[[:alnum:]]+/\1[redacted]/g;
    s/([Bb][Ee][Aa][Rr][Ee][Rr][[:space:]]+)[^[:space:]",;]+/\1[redacted]/g;
    s/([Aa]uthorization["'\'']?[[:space:]]*[=:][[:space:]]*).*/\1[redacted]/g;
    s/([Aa][Pp][IiPp][_-]?[Kk][Ee][Yy]["'\'']?[[:space:]]*[=:][[:space:]]*).*/\1[redacted]/g'
}
note() { printf '%s\n' "$*" | tee -a "$report"; }
section() {
  note ''
  note "=== $* | $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
}
emit() { safe < "$1" | tee -a "$report"; }
capture() {
  local limit=$1 destination=$2
  shift 2
  if [[ $1 == docker ]]; then
    shift
    set -- docker --host unix:///var/run/docker.sock "$@"
  fi
  if timeout "$limit" "$@" > "$destination" 2>&1; then
    last_code=0
  else
    last_code=$?
  fi
  note "Command exit: $last_code (124 means time limit; nonzero is diagnostic evidence)."
}
run() {
  local limit=$1 label=$2
  shift 2
  section "$label"
  capture "$limit" "$raw" "$@"
  emit "$raw"
}

note 'Datadog diagnostic reads; no service/configuration/registry changes.'
note 'Common key shapes and URLs are redacted. Review report.txt before sharing.'
note 'The report contains your public container identity and operator tags.'
note "Report: $report"
run 10s 'Container state' docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
run 10s 'Agent version' docker exec datadog-agent agent version
run 10s 'Docker storage capacity' df -h /var/lib/docker
run 10s 'Docker storage inodes' df -i /var/lib/docker

section 'Identify source without inspecting environment'
capture 10s "$raw" docker inspect bridge-sc_federation_1 --format '{{.Id}}'
fed_id=$(tr -d '\r\n' < "$raw")
if [[ $last_code != 0 || ! $fed_id =~ ^[0-9a-f]{64}$ ]]; then
  emit "$raw"
  note 'Could not identify the existing federator. No further checks attempted.'
  exit 1
fi
# This exact Docker ID is public metadata, not an arbitrary log/key-shaped value.
note "Federator container ID: $fed_id"
note "Datadog UI query: container_id:$fed_id"
capture 10s "$raw" docker inspect bridge-sc_federation_1 --format '{{.LogPath}}'
fed_log=$(tr -d '\r\n' < "$raw")
file_path_ok=false
if [[ $last_code == 0 && $fed_log == "/var/lib/docker/containers/$fed_id/$fed_id-json.log" ]]; then
  file_path_ok=true
else
  note 'Log path differs from the expected json-file layout; file-access probe will be skipped.'
fi
run 10s 'Source logging driver' docker inspect bridge-sc_federation_1 --format '{{.HostConfig.LogConfig.Type}}'
run 10s 'Agent mount destinations and write flags' docker inspect datadog-agent --format '{{range .Mounts}}{{println .Destination .RW}}{{end}}'

run 10s 'Only nonsecret settings; credential/proxy presence' docker exec datadog-agent sh -c '
for k in DD_SITE DD_LOGS_ENABLED DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE DD_CONTAINER_EXCLUDE DD_CONTAINER_EXCLUDE_LOGS DD_CONTAINER_INCLUDE_LOGS DD_TAGS; do
  printf "%s=%s\n" "$k" "$(printenv "$k")"
done
for k in DD_API_KEY HTTP_PROXY HTTPS_PROXY DD_PROXY_HTTP DD_PROXY_HTTPS; do
  if printenv "$k" >/dev/null; then printf "%s=present\n" "$k"; else printf "%s=unset\n" "$k"; fi
done'

source_snapshot() {
  run 15s 'Fresh source log tail (20 lines)' docker logs --tail 20 --timestamps bridge-sc_federation_1
  if [[ $file_path_ok == true ]]; then
    run 10s 'Agent identity, actual source readability and file size' docker exec -e TZ=UTC datadog-agent sh -c '
id
if test -r "$1"; then echo federator-log=readable; else echo federator-log=unreadable; fi
stat -c "bytes=%s modified=%y mode=%a owner=%u:%g" "$1"
if test -S /var/run/docker.sock; then echo docker-socket=present; else echo docker-socket=absent; fi
' sh "$fed_log"
  fi
}
status_snapshot() {
  section 'Effective API-key status, forwarder and Logs Agent'
  capture 20s "$status_raw" docker exec datadog-agent agent status
  if [[ $last_code != 0 ]]; then
    tail -20 "$status_raw" > "$raw"
    emit "$raw"
  fi
  sed -n '/API [Kk]eys status/,+6p; /Forwarder/,/Endpoints/p; /Logs Agent/,/APM Agent/p' "$status_raw" > "$raw"
  if [[ -s $raw ]]; then emit "$raw"; else note 'Requested status sections unavailable; validation/collection remains unknown.'; fi
  if grep -Fq "$fed_id" "$status_raw"; then
    note 'Federator ID appears in full agent status (discovery is not proof of reading).'
  else
    note 'Federator ID absent from captured status (incomplete status can also cause this).'
  fi
}

source_snapshot
status_snapshot
section 'Recent agent errors and tailer/upload hints'
capture 15s "$raw" docker logs --tail 500 --timestamps datadog-agent
grep -Ei 'error|warn|401|403|429|forbidden|unauthor|retry|timeout|certificate|connect|tail|docker|logs' "$raw" |
  tail -60 | safe | tee -a "$report"

# Authorize this known-site probe only from the effective Logs Agent endpoint.
if grep -Eq 'Sending.*agent-http-intake\.logs\.datadoghq\.com([^[:alnum:].-]|$)' "$status_raw"; then
  cat > "$probe" <<'PY'
import json, os, socket, ssl, urllib.request, urllib.error
site = os.environ.get('DD_SITE', '').strip()
if site not in ('', 'datadoghq.com'):
    print('US1 probe skipped: environment and effective endpoint disagree')
    raise SystemExit(0)
key = os.environ.get('DD_API_KEY')
if not key:
    print('Environment API key absent; YAML credentials were not inspected')
else:
    try:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        req = urllib.request.Request('https://api.datadoghq.com/api/v1/validate',
                                     headers={'DD-API-KEY': key})
        with urllib.request.build_opener(NoRedirect).open(req, timeout=8) as response:
            body = response.read(16385)
            if len(body) > 16384:
                print('API validation response too large; result unknown')
            else:
                print('API validation HTTP', response.status,
                      'valid=', json.loads(body).get('valid'))
    except urllib.error.HTTPError as exc:
        print('API validation HTTP', exc.code)
    except Exception as exc:
        print('API validation failed:', type(exc).__name__)
host = 'agent-http-intake.logs.datadoghq.com'
try:
    with socket.create_connection((host, 443), timeout=8) as raw:
        with ssl.create_default_context().wrap_socket(raw, server_hostname=host):
            print('Direct log-intake DNS/TCP/TLS: OK')
except Exception as exc:
    print('Direct log-intake connectivity failed:', type(exc).__name__)
PY
  section 'US1 environment-key validation and direct intake TLS'
  if timeout 30s docker --host unix:///var/run/docker.sock exec -i datadog-agent /opt/datadog-agent/embedded/bin/python - < "$probe" > "$raw" 2>&1; then
    last_code=0
  else
    last_code=$?
  fi
  note "Command exit: $last_code"
  emit "$raw"
else
  note 'US1 endpoint not established from status: API/TLS probe skipped; site must be confirmed.'
fi

if [[ $wait_seconds != 0 ]]; then
  section 'Three-minute observation; services remain running'
  for remaining in 180 120 60; do
    note "Waiting: $remaining seconds remaining. Ctrl-C preserves a partial report."
    sleep 60
  done
  source_snapshot
  status_snapshot
else
  note 'Second snapshot skipped by --no-wait; this run cannot establish counter/file deltas.'
fi

section 'Interpretation and manual UI follow-up'
note 'Fresh source + frozen counters: tailer/filter/registry OR sender backpressure; compare auth/network evidence.'
note 'Read grows but processing stalls: processing/filter branch. Processed grows but sent stalls: upload/auth/route branch.'
note 'Aggregate counters can reflect agent self-logs; check evidence from your federator specifically.'
note 'A valid key does not establish the intended organization. TLS success does not establish log authorization.'
note 'Direct TLS bypasses proxies; validation uses standard proxy environment, not necessarily Agent-specific proxy settings.'
note 'Check Live Tail for your printed container ID and intended org/site; check accessible indexes, current time and exclusions/quota.'
note 'Check blank env flags against YAML overrides before changing configuration.'
note 'Missing sections/timeouts/skipped probes are unknown results, not passing checks.'
note 'No repair attempted. Review and send only report.txt; do not share the raw temporary directory.'
note "Finished: $report"
