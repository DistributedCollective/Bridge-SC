import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_dd_agent_apply_retry import StatefulDocker, m

TOOL = Path(__file__).resolve().parents[1] / 'federator_datadog_upgrade.py'


class UpgradeDatadogTests(unittest.TestCase):
    def load(self):
        self.assertTrue(TOOL.is_file(), 'upgrade does not yet integrate Datadog repair')
        sys.path.insert(0, str(TOOL.parent))
        try:
            spec = importlib.util.spec_from_file_location('dd_upgrade', TOOL)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        finally:
            sys.path.pop(0)
        mod.r = m
        return mod

    def running(self, repaired=False):
        d = StatefulDocker(); d.agent['state'].update(Running=True, Status='running')
        if repaired:
            d.advance_registry = False
            d.files[m.DOCKER_CONFIG] = json.dumps({'api_key': 'dummy-private-fixture', 'logs_enabled': True, 'logs_config': {'run_path': m.PERSISTENT_PATH}}).encode()
            d.files[m.PERSISTENT_PATH + '/registry.json'] = json.dumps(d.registry).encode()
        return d

    def test_already_repaired_agent_is_captured_and_preserved_without_stop_or_recutoff(self):
        u = self.load()
        with tempfile.TemporaryDirectory() as td:
            d = self.running(repaired=True); original = dict(d.files)
            p = Path(td).resolve() / 'capture'; result = u.capture(d, p)
            self.assertFalse(result['agent_repaired_now'])
            self.assertEqual(d.files, original); self.assertEqual(d.starts, 0); self.assertEqual(d.writes, 0)
            override = json.loads((p / 'agent-state.override.private.json').read_text())
            self.assertEqual(override['volumes']['bridge_dd_state']['name'], 'fixture_agent_logs')
            self.assertEqual(override['services']['datadog']['environment']['DD_LOGS_CONFIG_RUN_PATH'], m.PERSISTENT_PATH)
            self.assertNotIn('dummy-private-fixture', (p / 'manifest.json').read_text())
            u.verify(d, p)

    def test_retained_checkpoint_start_detects_rotation_and_stops_agent(self):
        u=self.load()
        for fault in ('inode','truncated'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as td:
                d=self.running(repaired=True);d.agent['state'].update(Running=False,Status='exited')
                original=d.call
                def rotated(args,**kwargs):
                    out=original(args,**kwargs)
                    if args[0]=='start':
                        if fault=='inode':d.snapshot['inode']+=1
                        else:d.snapshot.update(size=500,offset=500)
                    return out
                d.call=rotated
                with self.assertRaises(u.r.RepairError):u.capture(d,Path(td).resolve()/'capture')
                self.assertEqual(d.starts,1)
                self.assertFalse(d.agent['state']['Running'])
                self.assertTrue(d.source['state']['Running'])

    def test_empty_quiet_log_can_resume_its_zero_checkpoint(self):
        u=self.load();d=self.running(repaired=True)
        d.agent['state'].update(Running=False,Status='exited');d.snapshot.update(size=0,offset=0)
        key=next(iter(d.registry['Registry']));d.registry['Registry'][key]['Offset']='0'
        d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(d.registry).encode()
        with tempfile.TemporaryDirectory() as tmp:
            value=u.capture(d,Path(tmp).resolve()/'capture')
        self.assertTrue(d.agent['state']['Running']);self.assertEqual(value['cursor_offset'],0)

    def test_compatible_original_agent_is_repaired_before_capture(self):
        u = self.load()
        with tempfile.TemporaryDirectory() as td:
            d = self.running(); source = dict(d.source)
            p = Path(td).resolve() / 'capture'; result = u.capture(d, p)
            self.assertTrue(result['agent_repaired_now']); self.assertEqual(d.starts, 1)
            self.assertEqual(d.source, source)
            self.assertTrue((p / 'repair/report.json').is_file())
            u.verify(d, p)

    def test_unsupported_agent_refuses_before_stop(self):
        u = self.load()
        class Old(StatefulDocker):
            def helper(self, image, code, mounts, **kwargs):
                result = super().helper(image, code, mounts, **kwargs)
                if 'version' in code:
                    value = json.loads(result); value['version'] = 'Agent 7.32.4'; return json.dumps(value).encode()
                return result
        with tempfile.TemporaryDirectory() as td:
            d = Old(); d.agent['state'].update(Running=True, Status='running')
            before = dict(d.files)
            with self.assertRaisesRegex(m.RepairError, '7.33'):
                u.capture(d, Path(td).resolve() / 'capture')
            self.assertTrue(d.agent['state']['Running']); self.assertEqual(d.files, before); self.assertEqual(d.writes, 0)

    def test_verify_detects_agent_replacement_or_config_change(self):
        u = self.load()
        for change in ('identity', 'config', 'cursor'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as td:
                d = self.running(repaired=True); p = Path(td).resolve() / 'capture'; u.capture(d, p)
                if change == 'identity': d.agent['id'] = 'e' * 64
                if change == 'config': d.files[m.DOCKER_CONFIG] = b'{}'
                if change == 'cursor':
                    reg = json.loads(d.files[m.PERSISTENT_PATH + '/registry.json']); reg['Registry']['file:' + d.log]['Offset'] = '1'
                    d.files[m.PERSISTENT_PATH + '/registry.json'] = json.dumps(reg).encode()
                with self.assertRaises(m.RepairError): u.verify(d, p)

    def test_verify_allows_created_replacement_with_no_log_path(self):
        u = self.load()
        with tempfile.TemporaryDirectory() as td:
            d = self.running(repaired=True); p = Path(td).resolve() / 'capture'; u.capture(d, p)
            d.source['id'] = 'e' * 64; d.source['log_path'] = ''
            d.source['state'].update(Running=False, Status='created')
            u.verify(d, p)

    def test_missing_captured_cursor_fails_without_an_explicit_verified_handoff(self):
        u = self.load()
        with tempfile.TemporaryDirectory() as td:
            d = self.running(repaired=True); p = Path(td).resolve() / 'capture'; u.capture(d, p)
            reg = json.loads(d.files[m.PERSISTENT_PATH + '/registry.json'])
            del reg['Registry']['file:' + d.log]
            d.files[m.PERSISTENT_PATH + '/registry.json'] = json.dumps(reg).encode()
            with self.assertRaisesRegex(m.RepairError, 'checkpoint absent'):
                u.verify(d, p)
            with self.assertRaises(m.RepairError):
                u.verify(d, p, allow_handoff=True)

    def test_explicit_handoff_requires_new_running_source_with_valid_nonzero_cursor(self):
        u = self.load()
        for fault in ('none', 'missing', 'zero', 'past_end', 'stopped', 'wrong_mount', 'forced_start'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as td:
                d = self.running(repaired=True); p = Path(td).resolve() / 'capture'; u.capture(d, p)
                reg = json.loads(d.files[m.PERSISTENT_PATH + '/registry.json'])
                del reg['Registry']['file:' + d.log]
                old = d.source['id']; d.source['id'] = 'e' * 64
                d.source['log_path'] = d.log.replace(old, d.source['id'])
                if fault != 'missing':
                    reg['Registry']['file:' + d.source['log_path']] = {
                        'Offset': '0' if fault == 'zero' else '1001' if fault == 'past_end' else '100',
                        'TailingMode': ''}
                if fault == 'stopped': d.source['state'].update(Running=False, Status='created')
                if fault == 'wrong_mount': d.source['mounts'][0]['Source'] = '/other/federator-env/mainnet-ETH-RSK'
                if fault == 'forced_start': d.source['labels'] = {'com.datadoghq.ad.logs': json.dumps([{'type':'file', 'path':d.source['log_path'], 'start_position':'forceBeginning'}])}
                d.files[m.PERSISTENT_PATH + '/registry.json'] = json.dumps(reg).encode()
                if fault == 'none':
                    u.verify(d, p, allow_handoff=True)
                    report = json.loads(next(p.glob('verify-*/report.json')).read_text())
                    self.assertTrue(report['source_handoff_verified'])
                    self.assertFalse(report['previous_source_cursor_present'])
                    self.assertFalse(report['state_retained'])
                else:
                    with self.assertRaises(m.RepairError): u.verify(d, p, allow_handoff=True)

    def test_capture_detects_agent_stop_or_pause_during_snapshot(self):
        u = self.load()
        for kind in ('stop', 'pause'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                d = self.running(repaired=True); original = d.inspect; checks = []
                def changing(name, agent=False):
                    if agent:
                        checks.append(1)
                        if len(checks) > 1:
                            if kind == 'stop': d.agent['state'].update(Running=False, Status='exited')
                            else: d.agent['state']['Paused'] = True
                    return original(name, agent)
                d.inspect = changing
                with self.assertRaises(m.RepairError): u.capture(d, Path(td).resolve() / 'capture')
                self.assertEqual(d.writes, 0); self.assertEqual(d.starts, 0)

    def test_integration_changes_are_detected_after_capture(self):
        from test_dd_agent_apply_retry import archive
        u = self.load()
        with tempfile.TemporaryDirectory() as td:
            d = self.running(repaired=True); p = Path(td).resolve() / 'capture'; u.capture(d, p)
            original = d.call
            def changed(args, **kwargs):
                if args[0] == 'cp' and args[-1] == '-' and args[1].endswith('/conf.d'):
                    return archive('conf.d/source.d/conf.yaml.default', json.dumps({'logs': [{'type':'file','path':d.log,'service':'changed'}]}).encode())
                return original(args, **kwargs)
            d.call = changed
            with self.assertRaises(m.RepairError): u.verify(d, p)

    def test_unknown_destination_and_invalid_service_refuse_before_stop(self):
        u = self.load()
        for kind in ('destination', 'service'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                d = self.running()
                if kind == 'destination': d.files[m.PERSISTENT_PATH + '/registry.json'] = b'{}'
                else: d.agent['labels'] = {'com.docker.compose.service':'invalid/service'}
                with self.assertRaises(m.RepairError): u.capture(d, Path(td).resolve() / 'capture')
                self.assertTrue(d.agent['state']['Running']); self.assertEqual(d.starts, 0); self.assertEqual(d.writes, 0)

    def test_main_config_change_during_snapshot_is_detected(self):
        u = self.load()
        with tempfile.TemporaryDirectory() as td:
            d = self.running(repaired=True); original = d.helper
            def changing(image, code, mounts, **kwargs):
                value = original(image, code, mounts, **kwargs)
                if 'version' in code: d.files[m.DOCKER_CONFIG] = b'{"unknown":true}'
                return value
            d.helper = changing
            with self.assertRaises(m.RepairError): u.capture(d, Path(td).resolve() / 'capture')
            self.assertEqual(d.writes, 0)

    def test_mount_scoped_to_old_log_directory_is_rejected_before_stop(self):
        u = self.load()
        for unrelated_broad in (False, True):
            with self.subTest(unrelated_broad=unrelated_broad), tempfile.TemporaryDirectory() as td:
                d = self.running(repaired=True)
                d.agent['mounts'][1]['Source'] = str(Path(d.log).parent)
                d.agent['mounts'][1]['Destination'] = str(Path(d.log).parent)
                if unrelated_broad:
                    d.agent['mounts'].append({'Type':'bind','Source':str(Path(d.log).parent.parent),'Destination':'/logs','RW':False})
                with self.assertRaises(m.RepairError): u.capture(d, Path(td).resolve() / 'capture')
                self.assertTrue(d.agent['state']['Running']); self.assertEqual(d.writes, 0)


if __name__ == '__main__': unittest.main()
