import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import signal
import contextlib
import io
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import federator_watcher as w
except ImportError:
    w = None

class WatcherTests(unittest.TestCase):
    def test_watcher_module_exists(self):
        self.assertIsNotNone(w, 'one-command watcher has not been implemented')

    @unittest.skipIf(w is None, 'module missing')
    def test_streaming_runner_kills_oversize_and_never_echoes_output(self):
        with self.assertRaises(w.ProbeError) as err:
            w.Runner().run([sys.executable, '-c', "import sys,time;sys.stdout.write('SECRET'*10000);sys.stdout.flush();time.sleep(30)"], timeout=2, limit=1000)
        self.assertEqual(err.exception.code, 'OUTPUT_LIMIT')
        self.assertNotIn('SECRET', str(err.exception))

    @unittest.skipIf(w is None, 'module missing')
    def test_streaming_runner_kills_hung_child_with_wall_deadline(self):
        before=time.monotonic()
        with self.assertRaises(w.ProbeError) as err:
            w.Runner().run([sys.executable, '-c', 'import time;time.sleep(30)'], timeout=.15)
        self.assertEqual(err.exception.code, 'TIMEOUT')
        self.assertLess(time.monotonic()-before, 2)

    @unittest.skipIf(w is None, 'module missing')
    def test_runner_stdin_secret_absent_from_arguments_and_errors(self):
        out=w.Runner().run([sys.executable,'-c','import sys,json;v=json.load(sys.stdin);print(json.dumps({"count":len(v["secret"])}))'],input_text=json.dumps({'secret':'OPAQUE'}))
        self.assertEqual(json.loads(out),{'count':6})

    @unittest.skipIf(w is None, 'module missing')
    def test_private_store_rotates_bounded_and_has_no_symlink_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=w.Store(Path(tmp).resolve()/'evidence',segment_limit=2000)
            for n in range(100):store.append({'utc':'2026-01-01T00:00:00Z','n':n,'payload':'x'*300})
            self.assertLessEqual(sum(p.stat().st_size for p in store.root.glob('timeline*')),4000)
            store.write({'status':'UNKNOWN','samples':[]})
            self.assertEqual(store.root.stat().st_mode&0o777,0o700)
            self.assertEqual((store.root/'report.json').stat().st_mode&0o777,0o600)
            link=Path(tmp).resolve()/'link';link.symlink_to(store.root,target_is_directory=True)
            with self.assertRaises(w.ProbeError):w.Store(link/'child')

    @unittest.skipIf(w is None, 'module missing')
    def test_etherscan_deep_probe_minimum_and_fatal_burst_guard(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            w.arguments(['--deep-every','59'])
        self.assertEqual(w.arguments(['--deep-every','60']).deep_every,60)
        with tempfile.TemporaryDirectory() as tmp:
            args=w.arguments(['--repo',str(Path(tmp).resolve())])
            class Fake:
                deadline=None
                def run(self,*a,**kw):raise AssertionError('unexpected command')
            watcher=w.Watcher(args,Fake(),w.Store(Path(tmp).resolve()/'out'))
            watcher.last_deep=100
            snap={'source_guard':'PASS','source':{'id':'1'*64,'running':True}}
            watcher.report['inventory']={'1'*64:{}}
            watcher.nodes['1'*64]=object()
            with patch.object(w.time,'monotonic',return_value=159), patch.object(w.fd,'runtime_probe') as probe:
                watcher.deep_check(snap)
                probe.assert_not_called()
            with patch.object(w.time,'monotonic',return_value=160), patch.object(w.fd,'runtime_probe',return_value={'checks':[]}) as probe:
                watcher.deep_check(snap)
                probe.assert_called_once()
            self.assertEqual(watcher.last_deep,160)

    def test_counter_reset_and_container_epoch_do_not_create_negative_delivery(self):
        old={'source':{'id':'1'*64,'started':'A'},'agent':{'id':'2'*64,'started':'B'},'collection':{'source_bytes':50,'counters':{'LogsSent':100}}}
        new={'source':{'id':'1'*64,'started':'A'},'agent':{'id':'2'*64,'started':'B'},'collection':{'source_bytes':70,'counters':{'LogsSent':5}}}
        delta=w.compare(old,new)
        self.assertEqual(delta['aggregate']['LogsSent'],'RESET')
        self.assertNotIn('DELIVERED',json.dumps(delta))
        new['agent']['id']='3'*64
        self.assertEqual(w.compare(old,new)['agent_epoch'],'CHANGED')

    @unittest.skipIf(w is None, 'module missing')
    def test_growing_source_frozen_tailer_and_sender_have_distinct_hypotheses(self):
        base={'source':{'id':'1'*64,'started':'A'},'agent':{'id':'2'*64,'started':'B'},'collection':{'source_bytes':50,'tailer_bytes':20,'counters':{'LogsProcessed':10,'LogsSent':10}}}
        new=json.loads(json.dumps(base));new['collection']['source_bytes']=80
        self.assertIn('COLLECTION_STALL',w.compare(base,new)['hypotheses'])
        new['collection']['tailer_bytes']=30;new['collection']['counters']['LogsProcessed']=15
        self.assertIn('SENDER_STALL',w.compare(base,new)['hypotheses'])

    @unittest.skipIf(w is None, 'module missing')
    def test_unknown_zero_counters_never_healthy(self):
        self.assertEqual(w.assess({'source':{'running':True},'agent':{'running':True},'collection':{'counters':{'LogsSent':0}}})['status'],'UNKNOWN')
        self.assertEqual(w.assess({'source':{'running':False,'status':'exited'},'agent':{}})['status'],'FAIL')

    @unittest.skipIf(w is None, 'module missing')
    def test_marker_classifier_with_split_auth_stack_never_retains_raw_secret(self):
        raw='2026-01-01T00:00:00Z TypeError: Received null secret=OPAQUE\n2026-01-01T00:00:01Z at Buffer.concat (node:buffer:1)\n2026-01-01T00:00:01Z at RSKKeyedAuthTCPTransport.addPeer (/app/federator/src/vendors/RSKKeyedAuth.js:82:3)\n'
        out=w.markers(raw)
        self.assertEqual(out[0]['class'],'AUTH_STREAM_NULL')
        self.assertNotIn('OPAQUE',json.dumps(out))
        self.assertNotIn('Received null',json.dumps(out))

    @unittest.skipIf(w is None, 'module missing')
    def test_read_key_missing_and_signing_shape_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve()/'datadog-read.key'
            self.assertIsNone(w.read_app_key(p))
            p.write_text('1'*64);p.chmod(0o600)
            with self.assertRaises(w.ProbeError):w.read_app_key(p)
            p.write_text('a'*40)
            self.assertEqual(w.read_app_key(p),'a'*40)
            p.chmod(0o644)
            with self.assertRaises(w.ProbeError):w.read_app_key(p)
            p.chmod(0o600);link=Path(tmp).resolve()/'link';link.symlink_to(p)
            with self.assertRaises(w.ProbeError):w.read_app_key(link)

    @unittest.skipIf(w is None, 'module missing')
    def test_cli_defaults_and_invalid_bounds_precede_commands(self):
        args=w.arguments(['--operator','fed_2'])
        self.assertEqual((args.duration,args.interval,args.deep_every),(900,60,300))
        for flags in (['--interval','0'],['--deep-every','0'],['--duration','-1'],['--operator','../evil'],['--incident-since','bad']):
            with self.subTest(flags=flags),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):w.arguments(['--operator','fed_2']+flags)

class AgentBoundaryTests(unittest.TestCase):
    def agent(self):
        self.assertTrue(hasattr(w,'AGENT_CODE'),'fixed Agent-side boundary missing')
        ns={'__name__':'unit_test'}
        exec(w.AGENT_CODE,ns)
        return ns

    def test_effective_site_mismatch_blocks_authenticated_requests(self):
        ns=self.agent()
        raw='Logs Agent\\n  Sending compressed logs in HTTPS to agent-http-intake.logs.datadoghq.eu\\nLogsProcessed: 10\\nLogsSent: 7'
        out=ns['parse_status'](raw.replace('\\n','\n'),'1'*64,'datadoghq.com')
        self.assertEqual(out['site_status'],'MISMATCH')
        with patch.dict(os.environ,{'DD_API_KEY':'a'*32,'DD_SITE':'datadoghq.com'},clear=True),patch.object(ns['urllib'].request,'build_opener',side_effect=AssertionError('must not send')):
            self.assertEqual(ns['perform']({'op':'direct','site':'datadoghq.eu','marker':'fw-direct-'+'1'*24,'operator':'fed_2'})['failure'],'SITE_MISMATCH')

    def test_status_keeps_only_public_counters_and_exact_source_tailer(self):
        ns=self.agent();cid='1'*64
        raw='API key ending with SECRET: invalid\nLogsProcessed: 10\nLogsSent: 8\ncontainer_id:'+cid+'\nBytes Read: 32\nprivateKey=OPAQUE\nSending logs in HTTPS to agent-http-intake.logs.datadoghq.com\n'
        out=ns['parse_status'](raw,cid,'datadoghq.com')
        self.assertEqual(out['tailer_bytes'],32)
        self.assertEqual(out['api_key_status'],'INVALID')
        self.assertNotIn('SECRET',json.dumps(out));self.assertNotIn('OPAQUE',json.dumps(out))
        other=ns['parse_status'](raw,'2'*64,'datadoghq.com')
        self.assertIsNone(other['tailer_bytes'])

    def test_direct_invalid_scalar_key_and_no_redirect_proxy_or_retry(self):
        ns=self.agent()
        for key in ('1'*64,'0x'+'1'*64,'bad'):
            with patch.dict(os.environ,{'DD_API_KEY':key,'DD_SITE':'datadoghq.com'},clear=True),patch.object(ns['urllib'].request,'build_opener',side_effect=AssertionError('must not send')):
                out=ns['perform']({'op':'direct','site':'datadoghq.com','marker':'fw-direct-'+'1'*24,'operator':'fed_2'})
                self.assertEqual(out['failure'],'API_KEY_SHAPE')

    def test_search_404_access_and_empty_are_not_delivery_failures(self):
        ns=self.agent()
        self.assertEqual(ns['search_result']({'data':[]})['status'],'UNKNOWN')
        out=ns['search_result']({'data':[{'attributes':{'timestamp':'2026-01-01T00:00:00Z','message':'SECRET'}}]})
        self.assertEqual(out['count'],1);self.assertNotIn('SECRET',json.dumps(out))
        self.assertEqual(ns['search_result']({'failure':'OPAQUE'})['failure'],'JSON_SHAPE')

    def test_agent_stdin_app_key_not_argv_env_or_code_literal(self):
        calls=[]
        class Fake:
            def run(self,args,**kw):calls.append((args,kw));return '{"status":"UNKNOWN"}'
        w.agent_call(Fake(),'1'*64,{'op':'search','app_key':'a'*40,'site':'datadoghq.com','query':'container_id:'+'2'*64})
        self.assertNotIn('a'*40,json.dumps(calls[0][0]))
        self.assertIn('a'*40,calls[0][1]['input_text'])
        self.assertNotIn('a'*40,w.AGENT_CODE)

class WatchLifecycleTests(unittest.TestCase):
    def test_owned_canary_has_no_key_or_data_mount_and_no_pull_or_immediate_rm(self):
        self.assertTrue(hasattr(w,'Canary'),'canary lifecycle missing')
        calls=[]
        class Fake:
            def run(self,args,**kw):
                calls.append(args)
                if args[:3]==['docker','image','inspect']:return json.dumps({'id':'sha256:'+'2'*64,'volumes':None})
                if args[:2]==['docker','create']:return '3'*64
                if args[:2]==['docker','inspect']:return json.dumps({'id':'3'*64,'name':'/fw-canary-'+'1'*24,'image':'sha256:'+'2'*64,'label':'fw-canary-'+'1'*24,'mounts':[],'network':'none'})
                return ''
        canary=w.Canary(Fake(),'fw-canary-'+'1'*24)
        canary.create('sha256:'+'2'*64,'fw-canary-marker-'+'1'*24)
        args=next(a for a in calls if a[:2]==['docker','create'])
        for bad in ('--rm','--mount','-v','--privileged','--pull=always'):self.assertNotIn(bad,args)
        self.assertEqual(args[args.index('--network')+1],'none')
        self.assertIn('--read-only',args);self.assertIn('--pull=never',args)
        self.assertIn('setTimeout',args[-1]);self.assertIn('150000',args[-1]);self.assertEqual(args[-1].count('process.stdout.write'),1)
        self.assertFalse(any(a[:2]==['docker','rm'] for a in calls))

    def test_canary_cleanup_wrong_identity_is_refused(self):
        self.assertTrue(hasattr(w,'Canary'),'canary lifecycle missing')
        calls=[]
        class Fake:
            def run(self,args,**kw):calls.append(args);return json.dumps({'id':'4'*64,'name':'/wrong','image':'sha256:'+'2'*64,'label':'wrong','mounts':[]})
        c=w.Canary(Fake(),'fw-canary-'+'1'*24);c.identity='3'*64;c.image='sha256:'+'2'*64
        self.assertEqual(c.cleanup()['status'],'UNKNOWN')
        self.assertFalse(any(a[:2]==['docker','rm'] for a in calls))

    def test_source_missing_and_agent_missing_preserve_other_evidence(self):
        self.assertTrue(hasattr(w,'Watcher'),'watch orchestration missing')
        with tempfile.TemporaryDirectory() as tmp:
            args=w.arguments(['--repo',str(Path(tmp).resolve()),'--duration','1'])
            class Fake:
                deadline=None
                def run(self,args,**kw):raise w.ProbeError('COMMAND_FAILED')
            watcher=w.Watcher(args,Fake(),w.Store(Path(tmp).resolve()/'out'))
            sample=watcher.quick()
            self.assertEqual(sample['source']['status'],'unknown')
            self.assertEqual(sample['agent']['status'],'unknown')
            self.assertEqual(sample['assessment']['status'],'UNKNOWN')


class EndToEndTests(unittest.TestCase):
    def test_agent_missing_stopped_and_source_profile_failure_are_independent_failures(self):
        for s in ({'source':{'running':True},'agent':{'status':'missing'}},
                  {'source':{'running':True},'agent':{'running':False}},
                  {'source':{'running':True},'agent':{'running':True},'source_guard':'FAIL'},
                  {'source':{'running':True},'agent':{'running':True},'source_changed_during_sample':True}):
            self.assertEqual(w.assess(s)['status'],'FAIL')

    def test_reader_inode_rotation_resets_tailer_delta(self):
        old={'source':{'id':'1'*64,'started':'A'},'agent':{'id':'2'*64,'started':'B'},'collection':{'source_inode':10,'source_bytes':100,'tailer_bytes':10,'counters':{'LogsSent':5}}}
        new=json.loads(json.dumps(old));new['collection'].update(source_inode=11,source_bytes=200,tailer_bytes=10)
        out=w.compare(old,new)
        self.assertEqual(out['reader_epoch'],'CHANGED')
        self.assertNotIn('COLLECTION_STALL',out['hypotheses'])

    def test_summary_has_evidence_backed_actions(self):
        report={'started':'2026-01-01T00:00:00Z','samples':[{'assessment':{'status':'FAIL','reason':'AGENT_MISSING'}}]}
        self.assertIn('Agent container',w.summary(report))
        self.assertIn('check',w.summary(report).lower())

    def test_runner_kills_descendant_when_parent_already_exited(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve()/'pid'
            script="import subprocess;from pathlib import Path;p=subprocess.Popen(['"+sys.executable+"','-c','import time;time.sleep(30)']);Path("+repr(str(p))+").write_text(str(p.pid))"
            with self.assertRaises(w.ProbeError):w.Runner().run([sys.executable,'-c',script],timeout=.3)
            pid=int(p.read_text());dead=False
            for _ in range(30):
                try:os.kill(pid,0)
                except ProcessLookupError:dead=True;break
                time.sleep(.01)
            if not dead:
                os.kill(pid,signal.SIGKILL)
            self.assertTrue(dead,'child remains alive after bounded runner timed out')

    def test_canary_inherited_image_volume_is_rejected_before_create(self):
        calls=[];image='sha256:'+'2'*64
        class Fake:
            def run(self,args,**kw):
                calls.append(args)
                if args[:3]==['docker','image','inspect']:
                    return image if args[-1]=='{{.Id}}' else json.dumps({'id':image,'volumes':{'/secret':{}}})
                if args[:2]==['docker','create']:return '3'*64
                return ''
        with self.assertRaises(w.ProbeError):w.Canary(Fake(),'fw-canary-'+'1'*24).create(image,'fw-canary-marker-'+'1'*24)
        self.assertFalse(any(a[:2]==['docker','create'] for a in calls))

    def test_canary_wrong_network_or_mount_is_not_started(self):
        calls=[];image='sha256:'+'2'*64;name='fw-canary-'+'1'*24
        class Fake:
            def run(self,args,**kw):
                calls.append(args)
                if args[:3]==['docker','image','inspect']:return image if args[-1]=='{{.Id}}' else json.dumps({'id':image,'volumes':None})
                if args[:2]==['docker','create']:return '3'*64
                if args[:2]==['docker','inspect']:return json.dumps({'id':'3'*64,'name':'/'+name,'image':image,'label':name,'mounts':[{'Destination':'/secret'}],'network':'host'})
                return ''
        with self.assertRaises(w.ProbeError):w.Canary(Fake(),name).create(image,'fw-canary-marker-'+'1'*24)
        self.assertFalse(any(a[:2]==['docker','start'] for a in calls))

    def test_canary_timeout_orphan_cleanup_validates_random_owned_name(self):
        calls=[];image='sha256:'+'2'*64;name='fw-canary-'+'1'*24
        class Fake:
            def run(self,args,**kw):
                calls.append(args)
                if args[:3]==['docker','image','inspect']:return image if args[-1]=='{{.Id}}' else json.dumps({'id':image,'volumes':None})
                if args[:2]==['docker','create']:raise w.ProbeError('TIMEOUT')
                if args[:2]==['docker','inspect']:return json.dumps({'id':'3'*64,'name':'/'+name,'image':image,'label':name,'mounts':[],'network':'none'})
                return ''
        c=w.Canary(Fake(),name)
        with self.assertRaises(w.ProbeError):c.create(image,'fw-canary-marker-'+'1'*24)
        self.assertEqual(c.cleanup()['status'],'REMOVED')
        rm=next(a for a in calls if a[:2]==['docker','rm'])
        self.assertEqual(rm[-1],'3'*64)

    def test_partial_interrupt_flushes_report_without_service_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=w.arguments(['--repo',str(Path(tmp).resolve()),'--duration','900'])
            class Fake:
                deadline=None
                def run(self,args,**kw):raise AssertionError(args)
            watcher=w.Watcher(args,Fake(),w.Store(Path(tmp).resolve()/'out'))
            def quick():
                watcher.interrupted()
                return {'utc':'2026-01-01T00:00:00Z','source':{'status':'missing'},'agent':{'status':'missing'},'assessment':{'status':'FAIL'}}
            watcher.quick=quick
            report=watcher.run()
            self.assertTrue(report['interrupted'])
            self.assertEqual(len(json.loads((watcher.store.root/'report.json').read_text())['samples']),1)

    def test_search_fails_closed_to_opaque_provider_messages(self):
        out=w.clean_agent({'status':'OPAQUE','failure':{'privateKey':'SECRET'},'count':0,'message':'SECRET','counters':{'LogsSent':2,'SECRET':3}})
        self.assertEqual(out['status'],'UNKNOWN');self.assertNotIn('SECRET',json.dumps(out))


class ReviewRegressionTests(unittest.TestCase):
    def test_tailer_source_block_ends_before_another_source_bytes(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns)
        text='target\nType: docker\nInputs: '+'1'*64+'\n\nother-source\nType: docker\nBytes Read: 987\n'
        out=ns['parse_status'](text,'1'*64,'datadoghq.com')
        self.assertIsNone(out['tailer_bytes'])

    def test_malformed_search_rows_are_not_found(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns)
        for body in ({'data':[None]},{'data':[{}]},{'data':[{'attributes':{}}]}):
            out=ns['search_result'](body)
            self.assertEqual(out['status'],'UNKNOWN');self.assertEqual(out['failure'],'JSON_SHAPE')

    def test_store_rename_symlink_race_remains_anchored_to_original_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();store=w.Store(root/'out');outside=root/'outside';outside.mkdir()
            original=store.guard
            def race():
                original();store.root.rename(root/'retained');store.root.symlink_to(outside,target_is_directory=True)
            store.guard=race
            store.append({'utc':'2026-01-01T00:00:00Z','status':'UNKNOWN'})
            self.assertFalse((outside/'timeline.jsonl').exists())
            self.assertTrue((root/'retained/timeline.jsonl').exists())

    def test_inspection_permission_failure_is_unknown_not_proven_missing(self):
        class Fake:
            def run(self,*args,**kw):raise w.ProbeError('COMMAND_FAILED')
        self.assertEqual(w.state(Fake(),'fed')['status'],'unknown')


class FixtureRunner:
    deadline=None
    def __init__(self,cfg):
        self.cfg=cfg;self.calls=[];self.states=['running'];self.agent_running=True;self.overlay=False
    def run(self,args,**kw):
        self.calls.append((args,kw))
        source='1'*64;agent='2'*64;image='sha256:'+'3'*64
        if args[:2]==['docker','inspect']:
            target=args[2]
            if args[-1]=='{{.HostConfig.LogConfig.Type}}':return 'json-file'
            if 'log_path' in args[-1]:return json.dumps({'log_path':'/var/lib/docker/containers/'+source+'/'+source+'-json.log','mounts':[{'Source':'/var/lib/docker/containers','Destination':'/var/lib/docker/containers','RW':False}]})
            role_agent=target in ('datadog-agent',agent)
            status=('running' if self.agent_running else 'exited') if role_agent else self.states[0]
            if not role_agent and args[-1]==w.STATE_FORMAT and len(self.states)>1:self.states.pop(0)
            snap={'id':agent if role_agent else source,'status':status,'running':status=='running','started':'2026-01-01T00:00:00Z','finished':'2026-01-01T00:00:00Z','exit':0,'oom':False,'restarts':0,'image_id':image,'mounts':[{'Source':str(self.cfg),'Destination':'/app/federator/config'},{'Source':str(self.cfg/'db'),'Destination':'/app/federator/db'}]}
            if self.overlay:snap['mounts'].append({'Source':'/wrong','Destination':'/app/federator/config/federator.key'})
            return json.dumps(snap)
        if args[:2]==['docker','info']:return '/var/lib/docker'
        if args[:3]==['docker','image','inspect']:return json.dumps({'digests':['repo@sha256:'+'4'*64],'revision':'5'*40,'created':'2026-01-01T00:00:00Z'})
        if args[0]=='git':return '6'*40
        if args[:2]==['docker','exec']:
            if args[-1]==w.AGENT_CODE:
                payload=json.loads(kw['input_text'])
                if payload['op']=='snapshot':return json.dumps({'status':'OBSERVED','site':'datadoghq.com','site_status':'MATCH','source_bytes':100,'source_inode':10,'source_readable':True,'source_registered':True,'tailer_bytes':100,'counters':{'LogsSent':1,'LogsProcessed':1}})
                return json.dumps({'status':'UNKNOWN'})
            return json.dumps({'checks':[{'name':'eth.rpc','status':'FAIL','failure':'DNS'}],'versions':{'node':'v14'}})
        if args[:2]==['docker','logs']:return '2026-01-01T00:00:01Z TypeError: Received null\n2026-01-01T00:00:02Z at RSKKeyedAuthTCPTransport.addPeer\n'
        if args[:2]==['docker','events']:return ''
        if args[:2]==['docker','stats']:return json.dumps({'CPUPerc':'1%','MemUsage':'2MiB / 1GiB','PIDs':'4'})
        if args[0]=='journalctl':raise w.ProbeError('COMMAND_FAILED')
        raise w.ProbeError('COMMAND_FAILED')

class OrchestrationTests(unittest.TestCase):
    def fixture(self,tmp):
        repo=Path(tmp).resolve();cfg=repo/'federator-env/mainnet-ETH-RSK';(cfg/'db').mkdir(parents=True)
        (cfg/'config.js').write_text("module.exports={mainchain:require('./rskmainnet.json'),sidechain:require('./mainnet.json'),minimumPeerAmount:2,runEvery:2};")
        runner=FixtureRunner(cfg);args=w.arguments(['--repo',str(repo),'--dd-app-key-file',str(repo/'datadog-read.key')])
        return w.Watcher(args,runner,w.Store(repo/'out')),runner
    def test_first_quick_has_current_epoch_tail_and_death_at_end_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=self.fixture(tmp);runner.states=['running','exited']
            snap=watcher.quick()
            self.assertEqual(snap['assessment']['status'],'FAIL');self.assertFalse(snap['source']['running'])
            logs=next(a for a,k in runner.calls if a[:2]==['docker','logs'])
            self.assertNotIn('--since',logs)
            self.assertEqual(snap['markers'][0]['class'],'AUTH_STREAM_NULL')
    def test_bad_profile_overlay_never_executes_application_or_creates_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=self.fixture(tmp);runner.overlay=True
            snap=watcher.quick();watcher.deep_check(snap);watcher.tests(snap)
            self.assertEqual(snap['source_guard'],'FAIL')
            self.assertFalse(any(a[:2]==['docker','create'] or (a[:2]==['docker','exec'] and a[-1]!=w.AGENT_CODE) for a,k in runner.calls))
    def test_deep_profile_replacement_failure_does_not_lose_quick_agent_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=self.fixture(tmp);snap=watcher.quick();watcher.samples.append(snap)
            with patch.object(w.fd,'runtime_probe',side_effect=w.fd.DiagnosticError('changed')):watcher.deep_check(snap)
            watcher.flush();report=json.loads((watcher.store.root/'report.json').read_text())
            self.assertEqual(report['samples'][0]['collection']['source_registered'],True)
            self.assertEqual(report['deep'][0]['evidence']['checks'][0]['failure'],'SOURCE_CHANGED_OR_UNAVAILABLE')
    def test_deep_inventory_distinguishes_host_and_image_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=self.fixture(tmp);snap=watcher.quick();watcher.deep_check(snap)
            report=watcher.report
            inventory=report['inventory']['1'*64]
            self.assertEqual(inventory['host_commit'],'6'*40)
            self.assertEqual(inventory['image']['revision'],'5'*40)
    def test_actual_source_layout_and_safe_agent_flags_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=self.fixture(tmp);snap=watcher.quick()
            self.assertIn('agent_docker_stats',snap)
            self.assertEqual(snap['agent_docker_stats']['CPUPerc'],'1%')
            self.assertTrue(snap['source_layout']['log_path_verified'])
            self.assertTrue(snap['source_layout']['agent_readonly_source_mount'])
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns)
        with patch.dict(os.environ,{'DD_LOGS_ENABLED':'true','DD_CONTAINER_EXCLUDE_LOGS':'password=OPAQUE'},clear=True):
            flags=ns['safe_flags']()
        self.assertEqual(flags['DD_LOGS_ENABLED'],'TRUE');self.assertTrue(flags['exclusion_present']);self.assertNotIn('OPAQUE',json.dumps(flags))
    def test_search_matching_requires_exact_marker_and_source_epoch(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns);marker='fw-direct-'+'1'*24
        row={'attributes':{'timestamp':'2026-01-01T00:00:01Z','service':'bridge-federator-watcher','message':'wrong marker'}}
        self.assertEqual(ns['search_result']({'data':[row]},'direct',marker,'2026-01-01T00:00:00Z')['status'],'UNKNOWN')
        row['attributes']['message']=marker
        self.assertEqual(ns['search_result']({'data':[row]},'direct',marker,'2026-01-01T00:00:00Z')['status'],'FOUND')
    def test_http_search_404_does_not_claim_not_delivered(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns)
        error=ns['urllib'].error.HTTPError('https://with-secret.invalid',404,'SECRET',None,None)
        class Opener:
            def open(self,*args,**kwargs):raise error
        with patch.dict(os.environ,{'DD_API_KEY':'a'*32,'DD_SITE':'datadoghq.com'},clear=True),patch.object(ns['urllib'].request,'build_opener',return_value=Opener()):
            out=ns['perform']({'op':'search','site':'datadoghq.com','app_key':'b'*40,'kind':'source','identifier':'1'*64,'since':'2026-01-01T00:00:00Z'})
        self.assertEqual(out,{'status':'UNKNOWN','failure':'HTTP_STATUS','http_status':404})
        self.assertNotIn('SECRET',json.dumps(out))


class FinalWorkflowTests(unittest.TestCase):
    def test_one_command_duration_writes_complete_private_report_without_real_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture=OrchestrationTests();watcher,runner=fixture.fixture(tmp)
            args=['--operator','fed_2','--repo',str(Path(tmp).resolve()),'--duration','1','--output-dir',str(Path(tmp).resolve()/'cli-out'),'--dd-app-key-file',str(Path(tmp).resolve()/'datadog-read.key')]
            out=io.StringIO()
            with patch.object(w,'Runner',return_value=runner),contextlib.redirect_stdout(out):result=w.main(args)
            report=json.loads((Path(tmp).resolve()/'cli-out/report.json').read_text())
            self.assertEqual(result,0);self.assertTrue(report['finished']);self.assertEqual(len(report['samples']),1)
            self.assertIn('Watcher started UTC',out.getvalue());self.assertIn('duration 1 seconds',out.getvalue())
            self.assertFalse(any(a[:2] in (['docker','restart'],['docker','pull'],['docker','stop']) for a,k in runner.calls))
    def test_direct_success_is_one_request_and_is_not_indexing_proof(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns);calls=[]
        class Response:
            status=202
            def __enter__(self):return self
            def __exit__(self,*args):pass
        class Opener:
            def open(self,request,**kwargs):calls.append((request,kwargs));return Response()
        with patch.dict(os.environ,{'DD_API_KEY':'a'*32,'DD_SITE':'datadoghq.com'},clear=True),patch.object(ns['urllib'].request,'build_opener',return_value=Opener()) as opener:
            result=ns['perform']({'op':'direct','site':'datadoghq.com','marker':'fw-direct-'+'1'*24,'operator':'fed_2'})
        self.assertEqual(result,{'status':'ACCEPTED','http_status':202});self.assertEqual(len(calls),1)
        self.assertLess(len(calls[0][0].data),1024)
        self.assertTrue(any(isinstance(arg,ns['NoRedirect']) for arg in opener.call_args.args))
        self.assertTrue(any(isinstance(arg,ns['urllib'].request.ProxyHandler) and not arg.proxies for arg in opener.call_args.args))
    def test_direct_dns_error_is_fixed_without_provider_message(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns)
        class Opener:
            def open(self,*args,**kw):raise ns['urllib'].error.URLError(ns['socket'].gaierror('SECRET_PROVIDER'))
        with patch.dict(os.environ,{'DD_API_KEY':'a'*32,'DD_SITE':'datadoghq.com'},clear=True),patch.object(ns['urllib'].request,'build_opener',return_value=Opener()):
            result=ns['perform']({'op':'direct','site':'datadoghq.com','marker':'fw-direct-'+'1'*24,'operator':'fed_2'})
        self.assertEqual(result['failure'],'DNS');self.assertNotIn('SECRET',json.dumps(result))
    def test_search_throttle_and_direct_are_once_per_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=OrchestrationTests().fixture(tmp);snap=watcher.quick();watcher.app_key='b'*40
            watcher.tests(snap);watcher.tests(snap)
            payloads=[json.loads(k['input_text']) for a,k in runner.calls if a[:2]==['docker','exec'] and a[-1]==w.AGENT_CODE]
            self.assertEqual(sum(v['op']=='direct' for v in payloads),1)
            self.assertEqual(sum(v['op']=='search' for v in payloads),3)
    def test_summary_retains_old_crash_and_latest_deep_boundary_failure(self):
        report={'samples':[{'utc':'2026-01-01T00:00:00Z','source':{'status':'exited','running':False,'oom':True}},{'utc':'2026-01-01T00:01:00Z','source':{'running':True},'assessment':{'status':'UNKNOWN'}}],
            'deep':[{'evidence':{'checks':[{'name':'eth.fee_readiness','status':'FAIL','failure':'BASE_FEE_MISSING'}]}}]}
        text=w.summary(report);self.assertIn('OOM',text);self.assertIn('eth.fee_readiness FAIL BASE_FEE_MISSING',text)
    def test_existing_world_readable_or_symlink_timeline_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=w.Store(Path(tmp).resolve()/'out');p=store.root/'timeline.jsonl';p.write_text('old');p.chmod(0o644)
            with self.assertRaises(w.ProbeError):store.append({'public':True})
            p.unlink();outside=Path(tmp).resolve()/'outside';outside.write_text('unchanged');p.symlink_to(outside)
            with self.assertRaises(w.ProbeError):store.append({'public':True})
            self.assertEqual(outside.read_text(),'unchanged')


class FractionalEpochTests(unittest.TestCase):
    def test_new_fractional_process_start_is_accepted_by_search_boundary(self):
        ns={'__name__':'unit'};exec(w.AGENT_CODE,ns)
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'{"data":[]}'
        class Opener:
            def open(self,*args,**kw):return Response()
        with patch.dict(os.environ,{'DD_API_KEY':'a'*32,'DD_SITE':'datadoghq.com'},clear=True),patch.object(ns['urllib'].request,'build_opener',return_value=Opener()) as opened:
            out=ns['perform']({'op':'search','site':'datadoghq.com','app_key':'b'*40,'kind':'source','identifier':'1'*64,'since':'2026-01-01T00:00:05.123456Z'})
        self.assertEqual(out.get('http_status'),200);self.assertTrue(opened.called)
    def test_process_epoch_order_uses_utc_instants_not_string_sort(self):
        self.assertTrue(hasattr(w,'epoch_since'),'parsed epoch helper missing')
        self.assertEqual(w.epoch_since('2026-01-01T00:00:05Z','2026-01-01T00:00:05.123456789Z'),'2026-01-01T00:00:05.123456Z')


class KernelRetentionTests(unittest.TestCase):
    def test_historical_kernel_query_does_not_limit_to_current_boot(self):
        calls=[]
        class Fake:
            def run(self,args,**kw):calls.append(args);return ''
        w.kernel_evidence(Fake(),'2026-01-01T00:00:00Z','2026-01-02T00:00:00Z')
        args=calls[0]
        self.assertIn('_TRANSPORT=kernel',args)
        self.assertNotIn('--dmesg',args);self.assertNotIn('-b',args);self.assertNotIn('-k',args)
    def test_initial_log_markers_before_current_process_are_excluded(self):
        logs='2026-01-01T00:00:00Z TypeError: Received null\n2026-01-01T00:00:01Z at RSKKeyedAuthTCPTransport.addPeer\n'
        self.assertEqual(w.markers(logs,w.fd.parse_time('2026-01-01T01:00:00Z')),[])


class LastReviewTests(unittest.TestCase):
    def test_interrupt_during_direct_request_prevents_canary_and_followup_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=OrchestrationTests().fixture(tmp);snap=watcher.quick();watcher.app_key='a'*40
            before=len(runner.calls)
            def direct(*args,**kw):watcher.interrupted();return {'status':'UNKNOWN'}
            with patch.object(w,'agent_call',side_effect=direct) as request,patch.object(watcher.canary,'create',return_value={'status':'CREATED'}) as create:
                watcher.tests(snap)
            create.assert_not_called();self.assertEqual(request.call_count,1)
            self.assertFalse(any(a[:2] in (['docker','create'],['docker','start']) for a,k in runner.calls[before:]))
    def test_interrupt_during_canary_create_prevents_start(self):
        calls=[];image='sha256:'+'2'*64;name='fw-canary-'+'1'*24;cancel=[False]
        class Fake:
            def run(self,args,**kw):
                calls.append(args)
                if args[:3]==['docker','image','inspect']:return json.dumps({'id':image,'volumes':None})
                if args[:2]==['docker','create']:cancel[0]=True;return '3'*64
                if args[:2]==['docker','inspect']:return json.dumps({'id':'3'*64,'name':'/'+name,'image':image,'label':name,'mounts':[],'network':'none'})
                return ''
        c=w.Canary(Fake(),name);c.cancelled=lambda:cancel[0]
        with self.assertRaises(w.ProbeError):c.create(image,'fw-canary-marker-'+'1'*24)
        self.assertFalse(any(a[:2]==['docker','start'] for a in calls))
        self.assertEqual(c.cleanup()['status'],'REMOVED')
    def test_offline_merge_uses_marker_time_and_includes_historical_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();node=root/'node';node.mkdir()
            rows=[{'type':'sample','operator':'fed_2','evidence':{'utc':'2026-01-01T01:00:00Z','source':{'id':'1'*64},'markers':[{'utc':'2026-01-01T00:00:01Z','class':'AUTH_STREAM_NULL'}]}},
                  {'type':'historical','operator':'fed_2','evidence':{'until':'2026-01-01T00:00:00Z','containers':{'source':{'id':'1'*64,'markers':[{'utc':'2025-12-31T23:00:00Z','class':'SIGNATURE_ERROR'}]}}}}]
            (node/'timeline.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
            args=w.arguments(['--analyze',str(node)]);report=w.analyze(args,w.Store(root/'out'))
            self.assertEqual(report['merged_timeline'][0]['utc'],'2025-12-31T23:00:00Z')
            self.assertEqual(report['merged_timeline'][1]['utc'],'2026-01-01T00:00:01Z')
            self.assertEqual(report['merged_timeline'][1]['observation_utc'],'2026-01-01T01:00:00Z')
    def test_journal_time_format_is_explicit_utc_compatible_with_older_systemd(self):
        calls=[]
        class Fake:
            def run(self,args,**kw):calls.append(args);return ''
        w.kernel_evidence(Fake(),'2026-01-01T00:00:00Z','2026-01-02T00:00:00Z')
        args=calls[0]
        self.assertEqual(args[args.index('--since')+1],'2026-01-01 00:00:00 UTC')
        self.assertEqual(args[args.index('--until')+1],'2026-01-02 00:00:00 UTC')


class HistoricalCaptureTimeTests(unittest.TestCase):
    def test_old_window_event_keeps_actual_later_capture_time_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();node=root/'node';node.mkdir()
            row={'type':'historical','operator':'fed_2','evidence':{'since':'2026-01-01T00:00:00Z','until':'2026-01-02T00:00:00Z','captured_utc':'2026-01-06T12:00:00Z','containers':{'source':{'id':'1'*64,'markers':[{'utc':'2026-01-01T01:00:00Z','class':'AUTH_STREAM_NULL'}]}}}}
            (node/'timeline.jsonl').write_text(json.dumps(row)+'\n')
            report=w.analyze(w.arguments(['--analyze',str(node)]),w.Store(root/'out'))
            event=report['merged_timeline'][0]
            self.assertEqual(event['utc'],'2026-01-01T01:00:00Z')
            self.assertEqual(event['observation_utc'],'2026-01-06T12:00:00Z')
            self.assertEqual(event['window_until'],'2026-01-02T00:00:00Z')
    def test_historical_snapshot_records_when_capture_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher,runner=OrchestrationTests().fixture(tmp)
            watcher.args.incident_since='2026-01-01T00:00:00Z';watcher.args.incident_until='2026-01-02T00:00:00Z'
            with patch.object(w.fd,'utc_now',return_value='2026-01-06T12:00:00Z'):watcher.historical()
            self.assertEqual(watcher.report['historical']['captured_utc'],'2026-01-06T12:00:00Z')

if __name__=='__main__':unittest.main()
