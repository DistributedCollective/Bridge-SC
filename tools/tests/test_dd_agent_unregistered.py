import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_datadog_upgrade as upgrade_tests
from test_dd_agent_legacy import LegacyDocker,m


class MissingSourceDocker(LegacyDocker):
    def __init__(self,enabled=True):
        super().__init__()
        self.registry['Registry'].pop('file:'+self.log)
        self.files['/opt/datadog-agent/run/registry.json']=json.dumps(self.registry).encode()
        self.agent['env']=['DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL='+('true' if enabled else 'false')]


class UnregisteredSourceTests(unittest.TestCase):
    def test_explicit_initialization_preserves_all_other_source_data(self):
        d=MissingSourceDocker();before=copy.deepcopy(d.registry)
        result=m.recovery_registry(before,d.log,d.source['id'],1000,'2026-10-19T09:20:34Z',allow_unregistered=True)
        self.assertEqual(d.registry,before)
        self.assertEqual(result['Registry']['file:/other.log'],before['Registry']['file:/other.log'])
        self.assertEqual(result['Registry']['file:'+d.log]['Offset'],'1000')
        with self.assertRaises(m.RepairError):m.recovery_registry(before,d.log,d.source['id'],1000,'2026-10-19T09:20:34Z')

    def test_running_agent_with_collect_all_can_initialize_missing_current_source(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker();d.agent['state'].update(Running=True,Status='running')
            source=copy.deepcopy(d.source);before=dict(d.files)
            report=u.inspect(d,Path(td).resolve()/'inspect')
            self.assertTrue(report['agent_repair_needed']);self.assertEqual(d.files,before)
            self.assertEqual(d.starts,0);self.assertEqual(d.writes,0)
            output=Path(td).resolve()/'capture';u.capture(d,output);u.verify(d,output)
            self.assertEqual(d.source,source);self.assertEqual(d.starts,1)
            current=json.loads(d.files[m.PERSISTENT_PATH+'/registry.json'])
            self.assertEqual(current['Registry']['file:/other.log'],d.registry['Registry']['file:/other.log'])
            self.assertTrue(json.loads((output/'repair/context.private.json').read_text())['source_checkpoint_initialized'])

    def test_missing_source_requires_explicit_collection_configuration(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker(enabled=False);d.agent['state'].update(Running=True,Status='running')
            with self.assertRaises(m.RepairError):u.inspect(d,Path(td).resolve()/'inspect')
            self.assertEqual(d.starts,0);self.assertEqual(d.writes,0)
            self.assertTrue(d.agent['state']['Running'])

    def test_fresh_capture_cannot_bypass_unacknowledged_initialization(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker();d.advance_registry=False
            d.agent['state'].update(Running=True,Status='running')
            with patch.object(m.time,'monotonic',side_effect=itertools.count(0,61)),patch.object(m.time,'sleep'):
                with self.assertRaises(m.DeliveryPending):u.capture(d,Path(td).resolve()/'first')
            starts=d.starts
            with self.assertRaises(m.RepairError):u.capture(d,Path(td).resolve()/'fresh')
            self.assertEqual(d.starts,starts)
            self.assertTrue(d.source['state']['Running'])

    def test_fresh_capture_can_finalize_only_after_real_checkpoint_progress(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker();d.advance_registry=False
            d.agent['state'].update(Running=True,Status='running')
            with patch.object(m.time,'monotonic',side_effect=itertools.count(0,61)),patch.object(m.time,'sleep'):
                with self.assertRaises(m.DeliveryPending):u.capture(d,Path(td).resolve()/'first')
            reg=json.loads(d.files[m.PERSISTENT_PATH+'/registry.json'])
            reg['Registry']['file:'+d.log]['Offset']='1100'
            d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(reg).encode()
            d.snapshot.update(offset=1100,size=1100)
            starts=d.starts;out=Path(td).resolve()/'fresh-ack';u.capture(d,out);u.verify(d,out)
            record=json.loads(d.files[m.PERSISTENT_PATH+'/'+m.INITIALIZATION_FILE])
            self.assertEqual(record['Acknowledged'],1100);self.assertEqual(d.starts,starts)

    def test_agent_exit_during_fresh_ack_proof_cannot_adopt_running_state(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker();d.advance_registry=False
            d.agent['state'].update(Running=True,Status='running')
            with patch.object(m.time,'monotonic',side_effect=itertools.count(0,61)),patch.object(m.time,'sleep'):
                with self.assertRaises(m.DeliveryPending):u.capture(d,Path(td).resolve()/'first')
            reg=json.loads(d.files[m.PERSISTENT_PATH+'/registry.json'])
            reg['Registry']['file:'+d.log]['Offset']='1100';d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(reg).encode()
            d.snapshot.update(offset=1100,size=1100);original=d.call
            def exit_during_proof(args,**kwargs):
                result=original(args,**kwargs)
                if args[0]=='cp' and args[-1].endswith('/'+m.INITIALIZATION_FILE):d.agent['state'].update(Running=False,Status='exited')
                return result
            d.call=exit_during_proof
            with self.assertRaises(m.RepairError):u.capture(d,Path(td).resolve()/'fresh-ack')
            self.assertTrue(d.source['state']['Running'])

    def test_corrupt_durable_initialization_metadata_blocks_preflight(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker();d.agent['state'].update(Running=True,Status='running')
            u.capture(d,Path(td).resolve()/'first');starts=d.starts
            d.files[m.PERSISTENT_PATH+'/'+m.INITIALIZATION_FILE]=b'{"Version":true}'
            with self.assertRaises(m.RepairError):u.inspect(d,Path(td).resolve()/'corrupt')
            self.assertEqual(d.starts,starts);self.assertTrue(d.source['state']['Running'])

    def test_initialized_source_requires_ack_progress_and_resumes_same_attempt(self):
        with tempfile.TemporaryDirectory() as td:
            d=MissingSourceDocker();source=copy.deepcopy(d.source);d.advance_registry=False
            output=Path(td).resolve()/'repair';m.prepare(d,output)
            with patch.object(m.time,'monotonic',side_effect=itertools.count(0,61)),patch.object(m.time,'sleep'):
                with self.assertRaises(m.DeliveryPending):m.apply(d,output)
            self.assertTrue(d.agent['state']['Running']);self.assertEqual(d.source,source)
            reg=json.loads(d.files[m.PERSISTENT_PATH+'/registry.json'])
            reg['Registry']['file:'+d.log]['Offset']='1100';d.snapshot.update(offset=1100,size=1100)
            d.files[m.PERSISTENT_PATH+'/registry.json']=json.dumps(reg).encode()
            report=m.apply(d,output)
            self.assertEqual(report['outcome'],'agent_running_current_source_offset_advanced')
            self.assertEqual(d.starts,1)
