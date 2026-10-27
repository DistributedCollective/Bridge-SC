"""Recovery transport and shareable-report regression checks; localhost only."""
import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import federator_recovery as recovery


class TransportTests(unittest.TestCase):
    @contextlib.contextmanager
    def endpoint(self, redirect=False):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                if redirect:
                    self.send_response(302)
                    self.send_header('Location', '/redirected')
                    self.end_headers()
                else:
                    body = b'{"jsonrpc":"2.0","id":1,"result":"0x1"}'
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            def do_GET(self):
                received.append((self.path, None))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"id":1,"result":"redirect-followed"}')
            def log_message(self, *_):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield 'http://127.0.0.1:' + str(server.server_port), received
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_configured_rpc_works_despite_broken_ambient_proxy(self):
        with self.endpoint() as (url, received):
            proxy = 'http://127.0.0.1:1'
            env = {key: proxy for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy')}
            env.update({'NO_PROXY': '', 'no_proxy': ''})
            with patch.dict(os.environ, env), patch('urllib.request._opener', None):
                self.assertEqual(recovery.RPC(url, timeout=1).call('eth_chainId', []), '0x1')
            self.assertEqual(received, [('/', {'jsonrpc': '2.0', 'id': 1, 'method': 'eth_chainId', 'params': []})])

    def test_rpc_redirect_fails_without_sending_payload_to_new_path(self):
        with self.endpoint(redirect=True) as (url, received), patch.dict(os.environ, {'NO_PROXY': '*', 'no_proxy': '*'}):
            with self.assertRaises(recovery.RecoveryError) as caught:
                recovery.RPC(url).call('eth_call', ['dummy'])
            self.assertIn('HTTP 302', str(caught.exception))
            self.assertEqual(len(received), 1)


class RedactionTests(unittest.TestCase):
    def test_recovery_hides_application_keys_and_bare_bearer_tokens(self):
        for raw in ('DATADOG_APP_KEY=opaque-app-credential',
                    '{"DD_APP_KEY":"opaque-app-credential"}',
                    'client saw Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature'):
            with self.subTest(raw=raw):
                clean = recovery.redact_logs(raw)
                self.assertNotIn('opaque-app-credential', clean)
                self.assertNotIn('eyJhbGciOiJIUzI1NiJ9.payload.signature', clean)
        ordinary = 'APP_KEY_PRESENT=true TypeError: RSKKeyedAuth'
        self.assertEqual(recovery.redact_logs(ordinary), ordinary)

    def test_shell_report_hides_authorization_header_and_application_key(self):
        script = (TOOLS / 'dd-diagnose.sh').read_text()
        function = script.split('safe() {', 1)[1].split('\n}', 1)[0]
        for raw in ('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature',
                    'bearer eyJhbGciOiJIUzI1NiJ9.payload.signature',
                    'DATADOG_APP_KEY=opaque-app-credential',
                    'DD_API_KEY=opaque-api-credential',
                    '{"DD_APP_KEY" : "opaque-app-credential"}',
                    "{'DD_APP_KEY': 'opaque-app-credential with spaces'}",
                    '{"DATADOG_API_KEY":"opaque-api-credential with spaces"}'):
            with self.subTest(raw=raw):
                result = subprocess.run(['bash', '-c', function], input=raw + '\n',
                                        text=True, capture_output=True, check=True).stdout
                for secret in ('eyJhbGciOiJIUzI1NiJ9.payload.signature', 'opaque-app-credential', 'opaque-api-credential'):
                    self.assertNotIn(secret, result)
                self.assertIn('redacted', result)
        ordinary = 'APP_KEY_PRESENT=true TypeError: RSKKeyedAuth\n'
        result = subprocess.run(['bash', '-c', function], input=ordinary, text=True,
                                capture_output=True, check=True).stdout
        self.assertEqual(result, ordinary)


if __name__ == '__main__':
    unittest.main()
