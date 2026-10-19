import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_dd_agent_apply_retry import StatefulDocker, m
import test_datadog_upgrade as upgrade_tests

LEGACY_IMAGE='sha256:4b37339b169c666008e4717eebc7f529329656f9ed13619f1d54d40a85adeeb8'


class LegacyDocker(StatefulDocker):
    def __init__(self, socket_only=False):
        super().__init__()
        self.agent['image']=LEGACY_IMAGE
        if socket_only:
            self.registry['Registry'].pop('file:'+self.log)
            self.registry['Registry']['docker:'+self.source['id']]={'Offset':'2025-11-19T16:00:00.000000001Z','TailingMode':''}
            self.registry['Registry']['docker:'+'e'*64]={'Offset':'2025-11-19T17:00:00Z','TailingMode':''}
            self.files['/opt/datadog-agent/run/registry.json']=json.dumps(self.registry).encode()
    def helper(self,image,code,mounts,**kwargs):
        value=super().helper(image,code,mounts,**kwargs)
        if 'version' in code:
            result=json.loads(value);result['version']='Agent 7.32.4 - fixture';return json.dumps(result).encode()
        return value


class LegacyAgentTests(unittest.TestCase):
    def test_only_the_verified_legacy_image_version_pair_is_supported(self):
        m.validate_agent_version('Agent 7.32.4 - fixture',LEGACY_IMAGE)
        m.validate_agent_version('Agent 7.33.1 - fixture','sha256:'+'c'*64)
        for version,image in [('Agent 7.32.3',LEGACY_IMAGE),('Agent 7.32.4','sha256:'+'c'*64),('Agent 6.33.1',LEGACY_IMAGE),('unknown',LEGACY_IMAGE)]:
            with self.subTest(version=version,image=image),self.assertRaises(m.RepairError):m.validate_agent_version(version,image)

    def test_socket_migration_changes_only_selected_source_and_enables_file_reads(self):
        d=LegacyDocker(socket_only=True);before=copy.deepcopy(d.registry)
        result=m.recovery_registry(before,d.log,d.source['id'],1000,'2026-10-19T09:00:00Z')
        self.assertEqual(d.registry,before)
        self.assertNotIn('docker:'+d.source['id'],result['Registry'])
        self.assertEqual(result['Registry']['file:'+d.log]['Offset'],'1000')
        self.assertEqual(result['Registry']['file:'+d.log]['TailingMode'],'')
        self.assertEqual(result['Registry']['docker:'+'e'*64],before['Registry']['docker:'+'e'*64])
        self.assertEqual(result['Registry']['file:/other.log'],before['Registry']['file:/other.log'])
        cfg=m.persistent_config({'api_key':'dummy','logs_config':{}},{})
        self.assertTrue(cfg['logs_config']['docker_container_use_file'])
        self.assertNotIn('docker_container_force_use_file',cfg['logs_config'])

    def test_unregistered_or_malformed_socket_source_cannot_seed_a_cursor(self):
        d=LegacyDocker(socket_only=True)
        for invalid in ('missing','bad-offset','wrong-source'):
            registry=copy.deepcopy(d.registry);cid=d.source['id']
            if invalid=='missing':registry['Registry'].pop('docker:'+cid)
            elif invalid=='bad-offset':registry['Registry']['docker:'+cid]['Offset']='invalid'
            else:cid='f'*64
            with self.subTest(invalid=invalid),self.assertRaises(m.RepairError):
                m.recovery_registry(registry,d.log,cid,1000,'2026-10-19T09:00:00Z')

    def test_prepare_apply_legacy_socket_source_preserves_other_sources_and_app(self):
        with tempfile.TemporaryDirectory() as td:
            d=LegacyDocker(socket_only=True);source=copy.deepcopy(d.source)
            out=Path(td).resolve()/'repair';m.prepare(d,out);m.apply(d,out)
            current=json.loads(d.files[m.PERSISTENT_PATH+'/registry.json'])
            self.assertEqual(current['Registry']['docker:'+'e'*64],d.registry['Registry']['docker:'+'e'*64])
            self.assertNotIn('docker:'+d.source['id'],current['Registry'])
            self.assertEqual(d.source,source);self.assertEqual(d.starts,1)

    def test_stopped_agent_preflight_is_read_only_and_confirmed_capture_recovers_it(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=LegacyDocker(socket_only=True);source=copy.deepcopy(d.source);before=dict(d.files)
            info=u.inspect(d,Path(td).resolve()/'inspect')
            self.assertTrue(info['agent_repair_needed']);self.assertFalse(info['agent_running'])
            self.assertEqual(d.files,before);self.assertEqual(d.writes,0);self.assertEqual(d.starts,0)
            result=u.capture(d,Path(td).resolve()/'capture')
            self.assertTrue(result['agent_repaired_now']);self.assertTrue(d.agent['state']['Running'])
            self.assertEqual(d.source,source)
            u.verify(d,Path(td).resolve()/'capture')

    def test_stopped_persistent_agent_starts_without_recutoff_or_config_writes(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=LegacyDocker();d.advance_registry=False
            d.agent['state'].update(Running=False,Status='exited')
            d.files[m.DOCKER_CONFIG]=json.dumps({'api_key':'dummy','logs_enabled':True,'logs_config':{'run_path':m.PERSISTENT_PATH,'docker_container_use_file':True}}).encode()
            d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(d.registry).encode()
            before=dict(d.files)
            out=Path(td).resolve()/'capture';u.capture(d,out)
            self.assertTrue(d.agent['state']['Running'])
            self.assertEqual(d.starts,1);self.assertEqual(d.writes,0);self.assertEqual(d.files,before)
            u.verify(d,out)

    def test_stopped_persistent_legacy_socket_default_cannot_be_adopted_as_file_success(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=LegacyDocker();d.agent['state'].update(Running=False,Status='exited')
            d.files[m.DOCKER_CONFIG]=json.dumps({'api_key':'dummy','logs_enabled':True,'logs_config':{'run_path':m.PERSISTENT_PATH}}).encode()
            d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(d.registry).encode()
            with self.assertRaises(m.RepairError):u.capture(d,Path(td).resolve()/'capture')
            self.assertEqual(d.starts,0);self.assertEqual(d.writes,0)

    def test_source_epoch_change_during_retained_agent_start_is_not_adopted(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        class Changed(LegacyDocker):
            def call(self,args,**kwargs):
                result=super().call(args,**kwargs)
                if args[0]=='start':self.source['state']['StartedAt']='2026-10-19T10:00:00Z'
                return result
        with tempfile.TemporaryDirectory() as td:
            d=Changed();d.advance_registry=False
            d.files[m.DOCKER_CONFIG]=json.dumps({'api_key':'dummy','logs_enabled':True,'logs_config':{'run_path':m.PERSISTENT_PATH,'docker_container_use_file':True}}).encode()
            d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(d.registry).encode()
            with self.assertRaises(m.RepairError):u.capture(d,Path(td).resolve()/'capture')
            self.assertFalse(d.agent['state']['Running'])
            self.assertTrue(d.source['state']['Running'])

    def test_future_agent_override_retains_explicit_file_reader(self):
        with tempfile.TemporaryDirectory() as td:
            d=LegacyDocker(socket_only=True);out=Path(td).resolve()/'repair'
            m.prepare(d,out);m.apply(d,out)
            plan=json.loads(next(out.glob('attempt-*/future-agent-override.private.json')).read_text())
            self.assertEqual(plan['services']['datadog']['environment']['DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE'],'true')
            self.assertNotIn('DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE',plan['services']['datadog']['environment'])

    def test_paused_agent_remains_blocked_before_writes(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=LegacyDocker();d.agent['state'].update(Running=True,Paused=True,Status='running')
            with self.assertRaises(m.RepairError):u.inspect(d,Path(td).resolve()/'inspect')
            self.assertEqual(d.writes,0);self.assertEqual(d.starts,0)
