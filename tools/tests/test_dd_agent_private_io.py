import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from test_dd_agent_apply_retry import m, archive


class PrivateIOTests(unittest.TestCase):
    def test_private_json_is_created_at_0600_without_late_chmod(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td).resolve() / 'private.json'
            previous = os.umask(0)
            try:
                with patch.object(m.os, 'chmod', side_effect=AssertionError('late chmod')):
                    m.write_private(target, {'secret': 'private-fixture'})
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            finally:
                os.umask(previous)

    def test_bounded_private_reader_rejects_symlink_fifo_and_large_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); value = root / 'ok.json'
            value.write_text('{}'); value.chmod(0o600)
            link = root / 'link.json'; link.symlink_to(value)
            fifo = root / 'fifo'; os.mkfifo(fifo)
            large = root / 'large'; large.write_bytes(b'x' * (m.MAX_BYTES + 1)); large.chmod(0o600)
            self.assertEqual(m.read_json(value), {})
            for path in (link, fifo, large):
                with self.subTest(path=path), self.assertRaises(m.RepairError): m.read_json(path)

    def test_copy_out_extracts_regular_tar_to_private_file_and_refuses_links(self):
        class Docker(m.Docker):
            def call(self, args, **kwargs):
                self.args = args
                return self.raw
        with tempfile.TemporaryDirectory() as td:
            d = Docker(); target = Path(td).resolve() / 'copy'
            d.raw = archive('config.yaml', b'private-value')
            previous = os.umask(0)
            try:
                self.assertEqual(d.copy_out('b' * 64, '/config.yaml', target), b'private-value')
                self.assertEqual(d.args[-1], '-')
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                d.raw = archive('config.yaml', link='/elsewhere')
                with self.assertRaises(m.RepairError): d.copy_out('b' * 64, '/config.yaml', target)
                self.assertEqual(target.read_bytes(), b'private-value')
            finally:
                os.umask(previous)
