"""Isolated intake-probe checks. All HTTP calls use a fake transport."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

SCRIPT = Path(__file__).resolve().parents[1] / 'dd-send-test.sh'
KEY = 'a' * 32


def load_probe():
    if not SCRIPT.is_file():
        raise AssertionError('The requested intake-test script has not been implemented')
    source = SCRIPT.read_text().split("<<'PY'\n", 1)[1].rsplit('\nPY\n', 1)[0]
    namespace = {'__name__': 'probe_under_test'}
    exec(compile(source, str(SCRIPT), 'exec'), namespace)
    return namespace


class Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Transport:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response or Response()
        self.error = error

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class IntakeProbeTests(unittest.TestCase):
    def execute(self, site='datadoghq.com', env=None, transport=None):
        probe = load_probe()
        transport = transport or Transport()
        output = io.StringIO()
        with patch.dict(os.environ, env if env is not None else {'DD_API_KEY': KEY}, clear=True), \
                patch.object(urllib.request, 'build_opener', return_value=transport) as builder, \
                contextlib.redirect_stdout(output):
            code = probe['main'](site)
        return code, output.getvalue(), transport, builder

    def test_single_small_log_with_private_key_and_search_marker(self):
        code, output, transport, _ = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(len(transport.calls), 1)
        request, timeout = transport.calls[0]
        self.assertEqual(request.full_url, 'https://http-intake.logs.datadoghq.com/api/v2/logs')
        self.assertEqual(request.method, 'POST')
        self.assertEqual(request.get_header('Dd-api-key'), KEY)
        self.assertLess(len(request.data), 1024)
        logs = json.loads(request.data)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['service'], 'bridge-federator-datadog-test')
        marker = logs[0]['message'].split(' ')[1]
        self.assertIn(marker, output)
        self.assertIn('UTC:', output)
        self.assertIn('HTTP 202', output)
        self.assertIn('does not prove Docker collection', output)
        self.assertNotIn(KEY, output)
        self.assertLessEqual(timeout, 10)

    def test_operator_identity_matches_the_actual_test_node(self):
        probe = load_probe(); transport = Transport(); output = io.StringIO()
        with patch.dict(os.environ, {'DD_API_KEY': KEY}, clear=True), \
                patch.object(urllib.request, 'build_opener', return_value=transport), \
                contextlib.redirect_stdout(output):
            code = probe['main']('datadoghq.com', 'fed_1')
        self.assertEqual(code, 0)
        event = json.loads(transport.calls[0][0].data)[0]
        self.assertEqual(event['hostname'], 'fed_1-eth-intake-probe')
        self.assertIn('operator:fed_1', event['ddtags'])
        self.assertNotIn('fed_2', json.dumps(event))
        self.assertNotIn(KEY, output.getvalue())

    def test_invalid_operator_cannot_send_or_inject_log_tags(self):
        probe = load_probe(); transport = Transport(); output = io.StringIO()
        with patch.dict(os.environ, {'DD_API_KEY': KEY}, clear=True), \
                patch.object(urllib.request, 'build_opener', return_value=transport) as builder, \
                contextlib.redirect_stdout(output):
            code = probe['main']('datadoghq.com', 'fed_1,operator:fed_2')
        self.assertEqual(code, 2)
        self.assertFalse(transport.calls)
        builder.assert_not_called()

    def test_missing_or_malformed_key_and_site_mismatch_send_nothing(self):
        cases = [{}, {'DD_API_KEY': 'bad'}, {'DD_API_KEY': KEY, 'DD_SITE': 'datadoghq.eu'}]
        for env in cases:
            with self.subTest(env=list(env)):
                code, output, transport, builder = self.execute(env=env)
                self.assertEqual(code, 2)
                self.assertFalse(transport.calls)
                builder.assert_not_called()
                self.assertNotIn(KEY, output)

    def test_only_official_sites_and_no_arbitrary_url(self):
        for site in ['attacker.example', 'datadoghq.com/extra', 'datadoghq.com@attacker.example', '']:
            with self.subTest(site=site):
                code, output, transport, builder = self.execute(site=site)
                self.assertEqual(code, 2)
                self.assertFalse(transport.calls)
                builder.assert_not_called()
                self.assertNotIn(site, output) if site else None
        code, _, transport, _ = self.execute(site='datadoghq.eu', env={'DD_API_KEY': KEY, 'DD_SITE': 'datadoghq.eu'})
        self.assertEqual(code, 0)
        self.assertEqual(transport.calls[0][0].full_url, 'https://http-intake.logs.datadoghq.eu/api/v2/logs')

    def test_redirects_and_inherited_proxies_cannot_forward_the_key(self):
        _, _, _, builder = self.execute(env={'DD_API_KEY': KEY, 'HTTPS_PROXY': 'https://attacker.example'})
        handlers = builder.call_args.args
        proxies = [h for h in handlers if isinstance(h, urllib.request.ProxyHandler)]
        redirects = [h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies[0].proxies, {})
        self.assertEqual(len(redirects), 1)
        self.assertIsNone(redirects[0].redirect_request(None, None, 302, '', {}, 'https://attacker.example'))

    def test_http_failures_do_not_print_body_or_retry(self):
        for status in [302, 400, 401, 403, 429, 500]:
            error = urllib.error.HTTPError('https://example.invalid', status, KEY, {}, io.BytesIO(KEY.encode()))
            code, output, transport, _ = self.execute(transport=Transport(error=error))
            self.assertEqual(code, 3)
            self.assertEqual(len(transport.calls), 1)
            self.assertIn('HTTP ' + str(status), output)
            self.assertNotIn(KEY, output)
            self.assertNotIn('accepted for processing', output)

    def test_ambiguous_transport_failure_is_not_retried_or_leaked(self):
        code, output, transport, _ = self.execute(transport=Transport(error=urllib.error.URLError(KEY)))
        self.assertEqual(code, 3)
        self.assertEqual(len(transport.calls), 1)
        self.assertIn('delivery unknown', output)
        self.assertNotIn(KEY, output)

    def test_unexpected_success_status_does_not_claim_v2_acceptance(self):
        response = Response()
        response.status = 200
        code, output, _, _ = self.execute(transport=Transport(response=response))
        self.assertEqual(code, 3)
        self.assertIn('HTTP 200', output)
        self.assertNotIn('accepted for processing', output)

    def test_wrapper_pins_local_socket_and_passes_no_key_in_arguments(self):
        load_probe()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            capture = folder / 'arguments.json'
            docker = folder / 'docker'
            docker.write_text('#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\nPath(os.environ["ARGUMENT_CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\nsource = sys.stdin.read()\nos.environ.pop("DD_API_KEY", None)\nsys.argv = ["-"] + sys.argv[-2:]\nexec(compile(source, "embedded", "exec"), {"__name__": "__main__"})\n')
            docker.chmod(0o700)
            env = dict(os.environ, PATH=str(folder) + os.pathsep + os.environ['PATH'], ARGUMENT_CAPTURE=str(capture), DD_API_KEY=KEY)
            result = subprocess.run(['bash', str(SCRIPT), '--site', 'datadoghq.com', '--operator', 'fed_1'], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            arguments = json.loads(capture.read_text())
            self.assertEqual(arguments[:5], ['--host', 'unix:///var/run/docker.sock', 'exec', '-i', 'datadog-agent'])
            self.assertEqual(arguments[-2:], ['datadoghq.com', 'fed_1'])
            self.assertNotIn(KEY, json.dumps(arguments) + result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
