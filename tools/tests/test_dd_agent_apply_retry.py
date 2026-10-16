"""Interrupted Agent applies against stateful private filesystem/container fixtures."""
import copy
import importlib.util
import io
import itertools
from unittest.mock import patch
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('retry_tool', Path(__file__).resolve().parents[1] / 'dd_agent_recovery.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def archive(name, data=None, link=None):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        row = tarfile.TarInfo(name)
        if link:
            row.type = tarfile.SYMTYPE; row.linkname = link
        else:
            row.size = len(data)
        tf.addfile(row, None if link else io.BytesIO(data))
    return buf.getvalue()


class StatefulDocker(m.Docker):
    def __init__(self):
        cid = 'a' * 64; aid = 'b' * 64
        base = '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK'
        self.log = '/var/lib/docker/containers/' + cid + '/' + cid + '-json.log'
        self.agent = {'id': aid, 'image': 'sha256:' + 'c' * 64, 'user': '', 'env': [], 'env_fingerprint': 'unchanged',
                      'state': {'Running': False, 'Paused': False, 'Status': 'exited', 'StartedAt': '2025-11-19T16:11:33Z'},
                      'mounts': [{'Type': 'volume', 'Destination': '/var/log/datadog', 'Name': 'fixture_agent_logs', 'RW': True},
                                 {'Type': 'bind', 'Source': '/var/lib/docker/containers', 'Destination': '/var/lib/docker/containers', 'RW': False}]}
        self.source = {'id': cid, 'image': 'sha256:' + 'd' * 64, 'state': {'Running': True, 'Status': 'running', 'StartedAt': '2026-10-16T00:34:02Z'},
                       'log_config': {'Type': 'json-file'}, 'log_path': self.log,
                       'mounts': [{'Type': 'bind', 'Destination': '/app/federator/config', 'Source': base},
                                  {'Type': 'bind', 'Destination': '/app/federator/db', 'Source': base + '/db'}]}
        self.registry = {'Version': 2, 'Registry': {'file:' + self.log: {'Offset': '12', 'TailingMode': '', 'LastUpdated': '2026-10-16T00:00:00Z'},
                                                 'file:/other.log': {'Offset': '9', 'TailingMode': 'beginning'}}}
        self.files = {m.DOCKER_CONFIG: json.dumps({'api_key': 'dummy-private-fixture', 'logs_enabled': True}).encode(),
                      '/opt/datadog-agent/run/registry.json': json.dumps(self.registry).encode()}
        self.snapshot = {'offset': 1000, 'size': 1000, 'device': 1, 'inode': 2, 'last_record_utc': '2026-10-16T09:05:41Z'}
        self.advance_registry = True
        self.interrupt = None; self.starts = 0; self.writes = 0; self.inspections = 0

    def inspect(self, name, agent=False):
        self.inspections += 1
        obj = copy.deepcopy(self.agent if agent else self.source)
        if self.inspections % 2: obj['mounts'].reverse()
        return obj

    def copy_out(self, cid, path, destination):
        if path not in self.files: raise m.RepairError('Fixture Agent file absent')
        if self.advance_registry and self.agent['state']['Running'] and path == m.PERSISTENT_PATH + '/registry.json':
            reg = json.loads(self.files[path]); reg['Registry']['file:' + self.log]['Offset'] = '1100'
            self.files[path] = json.dumps(reg).encode()
            self.snapshot.update(offset=max(1100, self.snapshot['offset']), size=max(1100, self.snapshot['size']))
        destination.write_bytes(self.files[path]); destination.chmod(0o600)
        return self.files[path]

    def fail(self, phase):
        if self.interrupt == phase:
            self.interrupt = None
            raise m.RepairError('Fixture interruption ' + phase)

    def call(self, args, **kwargs):
        if args[0] == 'cp' and args[-1] == '-':
            if args[1].endswith(':' + m.AGENT_CONFIG): return archive('datadog.yaml', link=m.DOCKER_CONFIG)
            return archive('conf.d/source.d/conf.yaml.default', json.dumps({'logs': [{'type': 'file', 'path': self.log}]}).encode())
        if args[0] == 'cp':
            src = Path(args[1]); target = args[2].split(':', 1)[1]
            if target == m.PERSISTENT_PATH:
                self.fail('before-registry')
                self.files[target + '/registry.json'] = (src / 'registry.json').read_bytes()
                self.writes += 1; self.fail('after-registry')
            else:
                self.files[target] = src.read_bytes(); self.writes += 1; self.fail('after-config')
            return b''
        if args[0] == 'start':
            self.starts += 1
            self.agent['state'].update(Running=True, Status='running', StartedAt='2026-10-16T10:00:00Z')
            return b''
        if args[0] == 'stop':
            self.agent['state'].update(Running=False, Status='exited'); return b''
        raise AssertionError(args)

    def helper(self, image, code, mounts, user=None, read_search=False):
        if 'fd=os.open' in code: return json.dumps(self.snapshot).encode()
        if '/discovery.tar' in code: return b'{"files_checked":1}'
        if '/agent-logs/bridge-log-state' in code:
            raw = self.files.get(m.PERSISTENT_PATH + '/registry.json')
            expected = json.loads(Path(mounts[-1][0]).read_text()) if len(mounts) > 1 else None
            result = {'exists': raw is not None}
            if 'registry_match' in code: result['registry_match'] = raw is not None and json.loads(raw) == expected
            if "'regular'" in code: result['regular'] = raw is not None
            return json.dumps(result).encode()
        cfg = json.loads(Path(mounts[0][0]).read_text())
        if 'version' in code: return json.dumps({'config': cfg, 'version': 'Agent 7.33.1 - fixture'}).encode()
        return json.dumps(cfg).encode()


class InterruptedApplyTests(unittest.TestCase):
    def test_interrupted_writes_resume_same_packet_without_source_changes(self):
        for phase in ('before-registry', 'after-registry', 'after-config'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as td:
                docker = StatefulDocker(); source = copy.deepcopy(docker.source)
                output = Path(td).resolve() / 'repair'; m.prepare(docker, output)
                originals = {p.name: p.read_bytes() for p in output.glob('original-*')}
                docker.interrupt = phase
                with self.assertRaisesRegex(m.RepairError, 'Fixture interruption ' + phase): m.apply(docker, output)
                self.assertTrue((output / 'apply-started.json').is_file())
                self.assertEqual(docker.starts, 0)
                result = m.apply(docker, output)
                self.assertEqual(result['outcome'], 'agent_running_current_source_offset_advanced')
                self.assertEqual(docker.starts, 1)
                self.assertEqual(docker.source, source)
                self.assertEqual(originals, {p.name: p.read_bytes() for p in output.glob('original-*')})
                self.assertEqual(json.loads(docker.files[m.PERSISTENT_PATH + '/registry.json'])['Registry']['file:' + docker.log]['TailingMode'], '')
                self.assertEqual(len(list(output.glob('attempt-*'))), 2)
                self.assertTrue(any((p / 'failure.json').is_file() for p in output.glob('attempt-*')))

    def test_idle_source_keeps_agent_running_without_claiming_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            d = StatefulDocker(); d.advance_registry = False
            packet = Path(td).resolve() / 'repair'; m.prepare(d, packet)
            with patch.object(m.time, 'monotonic', side_effect=itertools.count(0, 61)), patch.object(m.time, 'sleep'):
                result = m.apply(d, packet)
            self.assertTrue(d.agent['state']['Running'])
            self.assertEqual(result['outcome'], 'agent_running_source_idle')
            self.assertEqual(result['source_delivery'], 'UNKNOWN')
            self.assertEqual(result['acknowledged_offset'], result['cutover_offset'])
            self.assertEqual(d.starts, 1)

    def test_stalled_poststart_check_resumes_without_repatch_restart_or_new_cutoff(self):
        class Growing(StatefulDocker):
            def call(self, args, **kwargs):
                value = super().call(args, **kwargs)
                if args[0] == 'start': self.snapshot.update(offset=1200, size=1200)
                return value
        with tempfile.TemporaryDirectory() as td:
            d = Growing(); d.advance_registry = False
            packet = Path(td).resolve() / 'repair'; m.prepare(d, packet)
            with patch.object(m.time, 'monotonic', side_effect=itertools.count(0, 61)), patch.object(m.time, 'sleep'):
                with self.assertRaises(m.RepairError): m.apply(d, packet)
            self.assertTrue(d.agent['state']['Running'])
            writes = d.writes; source = copy.deepcopy(d.source)
            d.advance_registry = True
            result = m.apply(d, packet)
            self.assertEqual(result['outcome'], 'agent_running_current_source_offset_advanced')
            self.assertEqual(result['cutover_offset'], 1000)
            self.assertEqual(d.starts, 1); self.assertEqual(d.writes, writes)
            self.assertEqual(d.source, source)
            d.agent['state']['StartedAt'] = '2026-10-16T12:00:00Z'
            with self.assertRaises(m.RepairError): m.apply(d, packet)
            self.assertEqual(d.starts, 1); self.assertEqual(d.writes, writes)

    def test_unknown_installed_files_refuse_without_another_write_or_start(self):
        for kind in ('config', 'registry'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                docker = StatefulDocker(); output = Path(td).resolve() / 'repair'; m.prepare(docker, output)
                docker.interrupt = 'after-registry'
                with self.assertRaises(m.RepairError): m.apply(docker, output)
                if kind == 'config': docker.files[m.DOCKER_CONFIG] = b'{"unknown":true}'
                else: docker.files[m.PERSISTENT_PATH + '/registry.json'] = b'{"unknown":true}'
                writes = docker.writes
                with self.assertRaises(m.RepairError): m.apply(docker, output)
                self.assertEqual(docker.writes, writes); self.assertEqual(docker.starts, 0)

    def test_packet_inside_source_mount_never_receives_evidence_writes(self):
        import shutil
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); docker = StatefulDocker()
            base = root / 'federator-env/mainnet-ETH-RSK'; (base / 'db').mkdir(parents=True)
            docker.source['mounts'][0]['Source'] = str(base)
            docker.source['mounts'][1]['Source'] = str(base / 'db')
            packet = root / 'repair'; m.prepare(docker, packet)
            moved = base / 'repair'; shutil.copytree(packet, moved)
            before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(m.RepairError, 'outside every live application mount'):
                m.apply(docker, moved)
            self.assertFalse(m.report_incomplete(docker, moved, 'test refusal'))
            after = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertFalse(list(moved.glob('attempt-*')))
            self.assertEqual(docker.starts, 0); self.assertEqual(docker.writes, 0)

    def test_changed_source_or_log_refuses_retry_without_writes(self):
        for kind in ('process', 'rotation', 'truncation'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                docker = StatefulDocker(); output = Path(td).resolve() / 'repair'; m.prepare(docker, output)
                docker.interrupt = 'before-registry'
                with self.assertRaises(m.RepairError): m.apply(docker, output)
                if kind == 'process': docker.source['state']['StartedAt'] = '2026-10-16T11:00:00Z'
                if kind == 'rotation': docker.snapshot['inode'] += 1
                if kind == 'truncation': docker.snapshot.update(offset=500, size=500)
                writes = docker.writes
                with self.assertRaises(m.RepairError): m.apply(docker, output)
                self.assertEqual(docker.writes, writes); self.assertEqual(docker.starts, 0)


if __name__ == '__main__': unittest.main()
