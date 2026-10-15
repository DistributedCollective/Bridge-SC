#!/usr/bin/env bash
# Send one synthetic log using the existing Datadog Agent environment key.
# No credentials leave the Agent process in command arguments or printed output.
set +x
set -u
set -o pipefail

if [[ ${1:-} == --help && $# == 1 ]]; then
  printf 'Usage: bash %s --site datadoghq.com [--operator fed_1|fed_2|fed_3|fed_4|fed_5]\nSends ONE synthetic log by direct HTTPS from the existing datadog-agent.\n' "$0"
  exit 0
fi
if [[ ($# != 2 && $# != 4) || ${1:-} != --site || ($# == 4 && ${3:-} != --operator) ]]; then
  printf 'Specify the intended Datadog site: --site datadoghq.com (US1).\n' >&2
  exit 2
fi
case "$2" in
  datadoghq.com|datadoghq.eu|us3.datadoghq.com|us5.datadoghq.com|ap1.datadoghq.com|ap2.datadoghq.com|uk1.datadoghq.com|ddog-gov.com|us2.ddog-gov.com) ;;
  *) printf 'Unsupported Datadog site; no request sent.\n' >&2; exit 2 ;;
esac
operator=${4:-unspecified}
case "$operator" in
  fed_1|fed_2|fed_3|fed_4|fed_5|unspecified) ;;
  *) printf 'Unsupported operator label; no request sent.\n' >&2; exit 2 ;;
esac
for program in docker timeout; do
  if ! command -v "$program" >/dev/null; then
    printf 'Required command missing: %s\n' "$program" >&2
    exit 2
  fi
done

# Use bundled Python in the existing Agent; the key is never read on the host.
# A Docker client timeout can leave the exec alive; HTTP also has an operation timeout.
timeout --kill-after=5s 20s docker --host unix:///var/run/docker.sock exec -i datadog-agent /opt/datadog-agent/embedded/bin/python - "$2" "$operator" <<'PY'
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

SITES = frozenset((
    'datadoghq.com', 'datadoghq.eu', 'us3.datadoghq.com', 'us5.datadoghq.com',
    'ap1.datadoghq.com', 'ap2.datadoghq.com', 'uk1.datadoghq.com',
    'ddog-gov.com', 'us2.ddog-gov.com',
))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(site, operator="unspecified"):
    if site not in SITES:
        print('Unsupported Datadog site; no request sent.')
        return 2
    if operator not in ('fed_1', 'fed_2', 'fed_3', 'fed_4', 'fed_5', 'unspecified'):
        print('Unsupported operator label; no request sent.')
        return 2
    configured_site = os.environ.get('DD_SITE', '').strip()
    if configured_site and configured_site != site:
        print('Requested site differs from Agent DD_SITE; no request sent.')
        return 2
    key = os.environ.get('DD_API_KEY', '')
    if not re.fullmatch(r'[0-9a-fA-F]{32}', key):
        print('Agent environment API key absent or malformed; no request sent. YAML keys are not read.')
        return 2

    marker = 'dd-intake-test-' + str(uuid.uuid4())
    utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    endpoint = 'https://http-intake.logs.' + site + '/api/v2/logs'
    payload = json.dumps([{
        'message': utc + ' ' + marker + ' synthetic direct HTTPS intake test',
        'service': 'bridge-federator-datadog-test',
        'ddsource': 'federator-diagnostic',
        'hostname': operator + '-eth-intake-probe',
        'ddtags': 'diagnostic:true,operator:' + operator + ',bridge:eth-rsk',
        'status': 'info',
    }], separators=(',', ':')).encode('utf-8')
    if len(payload) >= 1024:
        print('Unexpected payload size; no request sent.')
        return 2
    print('UTC:', utc, flush=True)
    print('Marker:', marker, flush=True)
    print('Site:', site, flush=True)
    print('Payload bytes:', len(payload), '(one synthetic log)', flush=True)
    print('Search in Live Tail and Explorer:', 'service:bridge-federator-datadog-test "' + marker + '"', flush=True)
    print('Direct HTTPS; standard and Agent-specific proxies are not used.', flush=True)
    request = urllib.request.Request(endpoint, data=payload, method='POST', headers={
        'Content-Type': 'application/json', 'DD-API-KEY': key,
    })
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=10) as response:
            code = response.status
        print('HTTP', code)
        if code == 202:
            print('Request accepted for processing. Verify the marker in the intended organization.')
            print('This bypasses the Agent sender and does not prove Docker collection or indexing.')
            return 0
        print('Unexpected v2 intake status; delivery not verified. No automatic retry.')
        return 3
    except urllib.error.HTTPError as exc:
        print('HTTP', exc.code)
        exc.close()
        print('Intake rejected/failed this request. No redirects, response-body printing or automatic retry.')
        return 3
    except Exception:
        print('Transport failed (DNS/TCP/TLS/timeout); delivery unknown. No automatic retry.')
        return 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
PY
result=$?
if [[ $result == 124 || $result == 137 ]]; then
  printf 'Docker exec exceeded its deadline; delivery unknown. Check the marker before retrying.\n' >&2
fi
exit "$result"
