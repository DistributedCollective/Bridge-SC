import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import federator_upgrade_safety as m
except ImportError:
    m = None


class FakeNode:
    def __init__(self, root):
        self.cfg = root / 'config'
        self.cfg.mkdir()
        for name in ('config.js', 'mainnet.json', 'rskmainnet.json', 'peers.config.js'):
            (self.cfg / name).write_text('private-' + name)
        self.key = self.cfg / 'federator.key'
        self.key.write_text('1' * 64 + '\n')
        self.key.chmod(0o600)
        self.expected_uid = os.getuid()
        self.state = dict(id='a'*64, image_id='sha256:'+'b'*64, running=False,
                          started='2026-10-16T00:00:00Z', status='exited')
        self.runner = self
        self.changes = None
        self.marker = True
        self.commands = []

    def inspect(self):
        return dict(self.state)

    def key_ready(self):
        pass

    def run(self, cmd, timeout=15):
        self.commands.append(cmd)
        if cmd[1] == 'start':
            self.state.update(running=True, status='running', started='2026-10-16T12:00:00Z')
            return self.state['id']
        if cmd[1] == 'run':
            return 'Verified original FEDERATOR signer'
        if cmd[1] == 'logs':
            return '2026-10-16T12:00:01Z [INFO] Federators - RSK Host: hidden\n' if self.marker else ''
        raise AssertionError(cmd)


class UpgradeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'verified history archive and startup-key cleanup are missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.node = FakeNode(self.root)

    def test_start_removes_only_original_key_after_90_seconds_and_fresh_config_load(self):
        sleeps = []
        def sleep(seconds):
            sleeps.append(seconds)
            self.assertTrue(self.node.key.exists())
        out = self.root / 'start.json'
        m.start_and_clean(self.node, self.node.state['image_id'], out, expected_signer='0x'+'6'*40, sleep=sleep)
        self.assertEqual(sleeps, [90])
        self.assertFalse(self.node.key.exists())
        self.assertEqual((self.node.cfg/'config.js').read_text(), 'private-config.js')
        self.assertTrue(self.node.state['running'])
        self.assertEqual(json.loads(out.read_text())['outcome'], 'running_startup_key_removed')
        log_call = next(c for c in self.node.commands if c[1] == 'logs')
        self.assertIn('2026-10-16T12:00:00Z', log_call)
        self.assertNotIn('1'*64, out.read_text())

    def test_missing_startup_proof_or_changed_process_leaves_key_and_fails(self):
        for fault in ('marker', 'stale', 'restart', 'replacement', 'exited'):
            with self.subTest(fault=fault):
                self.node.state.update(id='a'*64, running=False, status='exited')
                self.node.marker = fault != 'marker'
                original_run=self.node.run
                if fault=='stale':
                    self.node.runner=type('Runner',(),{'run':lambda _,cmd,timeout=15: '2025-01-01T00:00:00Z [INFO] Federators - RSK Host hidden' if cmd[1]=='logs' else original_run(cmd,timeout)})()
                else:self.node.runner=self.node
                def sleep(_):
                    if fault == 'restart': self.node.state['started']='2026-10-16T12:01:00Z'
                    if fault == 'replacement': self.node.state['id']='c'*64
                    if fault == 'exited': self.node.state['running']=False
                out=self.root/(fault+'.json')
                with self.assertRaises(m.SafetyError):
                    m.start_and_clean(self.node, self.node.state['image_id'], out, expected_signer='0x'+'6'*40, sleep=sleep)
                self.assertTrue(self.node.key.exists())
                self.assertEqual(json.loads(out.read_text())['outcome'], 'startup_key_cleanup_pending')

    def test_pending_cleanup_finishes_same_process_without_restart_or_key_restore(self):
        self.node.marker = False; report = self.root / 'pending.json'
        with self.assertRaises(m.SafetyError):
            m.start_and_clean(self.node, self.node.state['image_id'], report,
                              expected_signer='0x'+'6'*40, sleep=lambda _: None)
        self.node.marker = True; self.node.commands.clear()
        m.finish_key_cleanup(self.node, report)
        self.assertFalse(self.node.key.exists())
        self.assertTrue(self.node.state['running'])
        self.assertTrue(all(c[1] == 'logs' for c in self.node.commands))
        self.assertEqual(json.loads(report.read_text())['outcome'], 'running_startup_key_removed')
        m.finish_key_cleanup(self.node, report)

    def test_pending_cleanup_refuses_changed_key_process_or_missing_fresh_proof(self):
        for fault in ('key', 'process', 'proof', 'report_link'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as td:
                node = FakeNode(Path(td).resolve()); node.marker = False
                report = Path(td).resolve() / 'pending.json'
                with self.assertRaises(m.SafetyError):
                    m.start_and_clean(node, node.state['image_id'], report,
                                      expected_signer='0x'+'6'*40, sleep=lambda _: None)
                node.marker = fault != 'proof'
                if fault == 'key': node.key.write_text('2'*64+'\n')
                if fault == 'process': node.state['started'] = '2026-10-16T13:00:00Z'
                if fault == 'report_link':
                    other = report.with_name('other.json'); report.rename(other); report.symlink_to(other)
                node.commands.clear()
                with self.assertRaises((m.SafetyError, OSError)): m.finish_key_cleanup(node, report)
                self.assertTrue(node.key.exists())
                self.assertTrue(all(c[1] == 'logs' for c in node.commands))

    def test_key_replacement_is_not_removed(self):
        def sleep(_):
            replacement=self.node.key.with_name('new.key')
            replacement.write_text('2'*64+'\n'); replacement.chmod(0o600)
            replacement.replace(self.node.key)
        with self.assertRaises(m.SafetyError):
            m.start_and_clean(self.node, self.node.state['image_id'], self.root/'start.json', expected_signer='0x'+'6'*40, sleep=sleep)
        self.assertEqual(self.node.key.read_text(), '2'*64+'\n')

    def test_existing_cleanup_journal_blocks_start(self):
        out=self.root/'start.json';out.write_text('{}')
        with self.assertRaises(Exception):
            m.start_and_clean(self.node, self.node.state['image_id'], out, expected_signer='0x'+'6'*40, sleep=lambda _:None)
        self.assertEqual(self.node.commands, [])

    def test_key_swapped_during_signer_verification_never_starts(self):
        original=self.node.run
        def changed(cmd, timeout=15):
            if cmd[1]=='run':
                self.node.key.write_text('2'*64+'\n')
                return 'Verified original FEDERATOR signer'
            return original(cmd, timeout)
        self.node.run=changed
        with self.assertRaises(m.SafetyError):
            m.start_and_clean(self.node,self.node.state['image_id'],self.root/'start.json',expected_signer='0x'+'6'*40,sleep=lambda _:None)
        self.assertFalse(self.node.state['running'])

    def test_wrong_image_or_running_state_never_starts(self):
        for image, running in [('sha256:'+'c'*64, False), (self.node.state['image_id'], True)]:
            self.node.state['running']=running
            with self.assertRaises(m.SafetyError):
                m.start_and_clean(self.node, image, self.root/('start'+str(running)+'.json'), expected_signer='0x'+'6'*40, sleep=lambda _:None)
        self.assertEqual(self.node.commands, [])

    def test_archive_keeps_all_streamed_logs_config_and_excludes_key_and_database(self):
        data=b'2025 historical\n2026 current\n'
        dest=self.root/'history'
        cmd=[sys.executable,'-c', 'import sys;sys.stdout.buffer.write('+repr(data)+')']
        m.archive_history(self.node, dest, command=cmd)
        self.assertEqual(gzip.decompress((dest/'docker.log.gz').read_bytes()), data)
        self.assertEqual((dest/'config.js').read_text(), 'private-config.js')
        self.assertFalse((dest/'federator.key').exists())
        report=json.loads((dest/'manifest.json').read_text())
        self.assertEqual(report['uncompressed_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(report['uncompressed_bytes'], len(data))
        self.assertFalse(self.node.state['running'])
        self.assertEqual(os.stat(dest/'docker.log.gz').st_mode & 0o777, 0o600)

    def test_failed_log_read_leaves_container_and_original_logs_available(self):
        cmd=[sys.executable,'-c', 'import sys;print("private error");sys.exit(1)']
        dest=self.root/'history'
        with self.assertRaises(m.SafetyError):
            m.archive_history(self.node, dest, command=cmd)
        self.assertFalse((dest/'manifest.json').exists())
        self.assertFalse(self.node.state['running'])
        self.assertEqual(self.node.commands, [])

    def test_archive_readback_catches_modified_saved_config(self):
        dest=self.root/'history';real=m.stream_logs
        def changed(*args, **kwargs):
            value=real(*args,**kwargs)
            (dest/'config.js').write_text('altered saved config')
            return value
        with patch.object(m,'stream_logs',side_effect=changed):
            with self.assertRaises(m.SafetyError):
                m.archive_history(self.node,dest,command=[sys.executable,'-c','print(123)'])
        self.assertFalse((dest/'manifest.json').exists())

    def test_low_disk_stops_archive_without_replacing_container(self):
        with patch.object(m.shutil,'disk_usage',return_value=type('Disk',(),{'free':0})()):
            with self.assertRaises(m.SafetyError):
                m.archive_history(self.node, self.root/'history', command=['false'])
        self.assertEqual(self.node.commands, [])

    def test_archive_refuses_running_container_and_existing_destination(self):
        self.node.state['running']=True
        with self.assertRaises(m.SafetyError): m.archive_history(self.node, self.root/'history')
        self.node.state['running']=False
        (self.root/'history').mkdir()
        with self.assertRaises(m.SafetyError): m.archive_history(self.node, self.root/'history')

if __name__ == '__main__': unittest.main()
