import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import etherscan_prerequisite as ep
except ImportError:
    ep = None


class EtherscanPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name).resolve()
        (self.cfg / 'config.js').write_text("const k=fs.readFileSync(__dirname+'/etherscan.key','utf8');module.exports={etherscanApiKey:k};")
        self.key = self.cfg / 'etherscan.key'
        self.value = 'a1' * 16

    def tearDown(self):
        self.tmp.cleanup()

    def test_helper_exists(self):
        self.assertIsNotNone(ep, 'upgrade must include its Etherscan prerequisite check')

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_existing_key_is_reused_without_prompt_and_validated_once(self):
        self.key.write_text(self.value + '\n'); self.key.chmod(0o644)
        with patch.object(ep, 'validate_remote') as remote:
            ep.ensure(self.cfg, prompt=lambda _: self.fail('existing key must not prompt'))
        remote.assert_called_once_with(self.value)
        self.assertEqual(self.key.read_text(), self.value + '\n')
        self.assertEqual(stat.S_IMODE(self.key.stat().st_mode), 0o600)

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_missing_key_prompts_and_installs_only_after_validation(self):
        def valid(value):
            self.assertEqual(value, self.value); self.assertFalse(self.key.exists())
        with patch.object(ep, 'validate_remote', side_effect=valid):
            ep.ensure(self.cfg, prompt=lambda _: self.value)
        self.assertEqual(self.key.read_text().strip(), self.value)
        self.assertEqual(stat.S_IMODE(self.key.stat().st_mode), 0o600)

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_invalid_scalar_never_leaves_host_or_installs(self):
        for value in ('', '0x' + '12' * 32, '12' * 32, 'bad\nkey'):
            with self.subTest(value_shape=len(value)), patch.object(ep, 'validate_remote') as remote:
                with self.assertRaises(ep.PrerequisiteError):
                    ep.ensure(self.cfg, prompt=lambda _: value)
                remote.assert_not_called()
                self.assertFalse(self.key.exists())

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_validation_failure_leaves_existing_or_missing_key_unchanged(self):
        for present in (False, True):
            if present: self.key.write_text(self.value)
            with patch.object(ep, 'validate_remote', side_effect=ep.PrerequisiteError('V2 unavailable')):
                with self.assertRaises(ep.PrerequisiteError):
                    ep.ensure(self.cfg, prompt=lambda _: self.value)
            self.assertEqual(self.key.exists(), present)
            if present: self.assertEqual(self.key.read_text(), self.value)

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_symlink_and_missing_loader_fail_without_prompt_or_network(self):
        outside = self.cfg / 'outside'; outside.write_text(self.value)
        self.key.symlink_to(outside)
        with patch.object(ep, 'validate_remote') as remote:
            with self.assertRaises(ep.PrerequisiteError):
                ep.ensure(self.cfg, prompt=lambda _: self.fail('unsafe file'))
            remote.assert_not_called()
        self.key.unlink(); (self.cfg / 'config.js').write_text('module.exports={};')
        with self.assertRaises(ep.PrerequisiteError):
            ep.ensure(self.cfg, prompt=lambda _: self.fail('missing loader'))

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_network_errors_and_rate_limit_do_not_leak_key(self):
        with patch.object(ep.urllib.request, 'build_opener') as factory:
            factory.return_value.open.side_effect = OSError('secret=' + self.value)
            with self.assertRaises(ep.PrerequisiteError) as failure:
                ep.validate_remote(self.value)
            self.assertNotIn(self.value, str(failure.exception))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, count): return json.dumps({'status':'0','result':'rate limited '+self.value}).encode()
        response=Response(); response.value=self.value
        with patch.object(ep.urllib.request, 'build_opener') as factory:
            factory.return_value.open.return_value=response
            with self.assertRaises(ep.PrerequisiteError) as failure:
                ep.validate_remote(self.value)
            self.assertNotIn(self.value, str(failure.exception))
            self.assertEqual(factory.return_value.open.call_count,1)

    @unittest.skipIf(ep is None, 'helper not implemented')
    def test_concurrent_key_creation_is_not_overwritten(self):
        def valid(value): self.key.write_text('another-existing-value')
        with patch.object(ep, 'validate_remote', side_effect=valid):
            with self.assertRaises(ep.PrerequisiteError): ep.ensure(self.cfg, prompt=lambda _: self.value)
        self.assertEqual(self.key.read_text(),'another-existing-value')

if __name__ == '__main__': unittest.main()
