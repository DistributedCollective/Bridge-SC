import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_dd_agent_apply_retry import StatefulDocker
import dd_agent_recovery as r


class SnapshotDocker(StatefulDocker):
    def call(self,args,**kwargs):
        if args[:1]==['inspect'] and len(args)==2:
            return json.dumps([{'Id':self.agent['id'],'Image':self.agent['image'],
                               'Config':{'Env':['DD_API_KEY=dummy-private-fixture']}}]).encode()
        return super().call(args,**kwargs)


class UpgradeMonitoringTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[1]/'federator_upgrade_monitoring.py'
        self.assertTrue(path.is_file(),'independent monitoring lifecycle is not implemented')
        spec=importlib.util.spec_from_file_location('independent_monitoring',path)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.output=self.root/'monitoring'
        self.d=SnapshotDocker()

    def test_invalid_stopped_registry_is_backed_up_and_does_not_block_clean_replacement(self):
        self.d.files['/opt/datadog-agent/run/registry.json']=b'broken-private-fixture\0'
        self.m.snapshot(self.d,self.output)
        self.assertEqual((self.output/'registry.private.json').read_bytes(),b'broken-private-fixture\0')
        new=copy.deepcopy(self.d.agent);new['id']='e'*64
        new['image']=self.m.fresh.IMAGE_ID;new['state'].update(Running=True,Status='running')
        manifest={'utc':'2026-10-19T14:00:00Z','source_cutoff':1000}
        with patch.object(self.m.fresh,'replace',return_value=(manifest,new)):
            outcome=self.m.recover(self.d,self.output)
        self.assertEqual(outcome['status'],'TRACKING_CONFIGURED')
        self.assertEqual(outcome['source_cutoff'],1000)
        self.assertEqual(self.d.files['/opt/datadog-agent/run/registry.json'],b'broken-private-fixture\0')
        for name in ('report.json','snapshot.json'):
            self.assertNotIn('private-fixture',(self.output/name).read_text())
        for path in self.output.iterdir():
            if path.is_file():self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_missing_agent_is_reported_without_asking_for_keys_or_changing_services(self):
        original=self.d.inspect
        self.d.inspect=lambda name,agent=False:(_ for _ in ()).throw(r.RepairError('private SECRET=value')) if agent else original(name)
        value=self.m.snapshot(self.d,self.output)
        self.assertEqual(value['backup'],'UNAVAILABLE')
        outcome=self.m.recover(self.d,self.output)
        self.assertEqual(outcome['status'],'UNRESOLVED')
        self.assertNotIn('SECRET',(self.output/'report.json').read_text())
        self.assertEqual(self.d.starts,0);self.assertEqual(self.d.writes,0)

    def test_changed_agent_or_missing_backup_refuses_recovery_without_mutation(self):
        self.m.snapshot(self.d,self.output)
        self.d.agent['id']='f'*64
        result=self.m.recover(self.d,self.output)
        self.assertEqual(result['status'],'UNRESOLVED')
        self.assertEqual(result['reason'],'AGENT_CHANGED')
        self.assertEqual(self.d.writes,0);self.assertEqual(self.d.starts,0)

    def test_recovery_failure_after_agent_stop_does_not_touch_application(self):
        self.m.snapshot(self.d,self.output);source=copy.deepcopy(self.d.source)
        def fail(docker,output):
            docker.call(['stop',docker.agent['id']])
            raise r.RepairError('SECRET=must-not-print')
        with patch.object(self.m.fresh,'replace',side_effect=lambda docker,output,*a,**kw:fail(docker,output)):
            result=self.m.recover(self.d,self.output)
        self.assertEqual(result['status'],'UNRESOLVED')
        self.assertEqual(self.d.source,source);self.assertTrue(self.d.source['state']['Running'])
        self.assertNotIn('must-not-print',(self.output/'report.json').read_text())
        self.assertFalse(self.d.agent['state']['Running'])

    def test_final_result_does_not_treat_watcher_exit_zero_as_application_health(self):
        self.m.snapshot(self.d,self.output)
        (self.root/'startup-key-cleanup.json').write_text(json.dumps({'outcome':'running_startup_key_removed',
            'source_id':self.d.source['id'],'image_id':self.d.source['image'],'started_utc':self.d.source['state']['StartedAt']}))
        (self.root/'startup-key-cleanup.json').chmod(0o600)
        watcher=self.root/'watcher';watcher.mkdir()
        (watcher/'report.json').write_text(json.dumps({'samples':[{'source':{'running':False}}]}))
        (watcher/'report.json').chmod(0o600)
        self.d.source['state']['Running']=False
        value=self.m.result(self.d,self.root,watcher)
        self.assertEqual(value['application']['status'],'FAIL')
        self.assertEqual(value['monitoring']['status'],'UNRESOLVED')
        self.assertEqual(value['bridge_processing'],'NOT_ESTABLISHED')

    def test_running_application_and_unresolved_monitoring_are_separate_results(self):
        self.m.snapshot(self.d,self.output)
        path=self.root/'startup-key-cleanup.json'
        path.write_text(json.dumps({'outcome':'running_startup_key_removed','source_id':self.d.source['id'],
            'image_id':self.d.source['image'],'started_utc':self.d.source['state']['StartedAt']}));path.chmod(0o600)
        value=self.m.result(self.d,self.root,self.root/'no-watcher')
        self.assertEqual(value['application']['status'],'RUNNING_STARTUP_VERIFIED')
        self.assertEqual(value['monitoring']['status'],'UNRESOLVED')
        self.assertEqual(value['indexed_visibility'],'UNKNOWN')

if __name__=='__main__':unittest.main()
