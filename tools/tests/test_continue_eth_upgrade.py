import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parents[1]


class ContinueTests(unittest.TestCase):
    def module(self):
        path=TOOLS/'continue_eth_upgrade.py'
        self.assertTrue(path.is_file(),'guarded continuation from stopped/key-recovery stage is missing')
        spec=importlib.util.spec_from_file_location('continue_eth_upgrade',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_reuses_only_verified_original_functions_and_never_runs_full_workflow(self):
        m=self.module()
        original=subprocess.check_output(['git','-C',str(TOOLS.parent),'show',
            '510b1b3419593f4b1193c6249a17a7a8813712c2:tools/upgrade-eth-federator.sh'],text=True)
        script=m.resume_script(original)
        with tempfile.NamedTemporaryFile(mode='w',suffix='.sh') as out:
            out.write(script);out.flush();subprocess.run(['bash','-n',out.name],check=True)
        boundary=script.split(m.SUFFIX_MARKER,1)[1]
        # These are statements executed after function definitions, not text searches over definitions.
        self.assertNotIn('\n  prepare\n',boundary)
        self.assertNotIn('\nbackup_image\n',boundary)
        self.assertNotIn('\nstop_original\n',boundary)
        self.assertLess(boundary.index('--guard --run'),boundary.index('\nrestore_key\n'))
        self.assertLess(boundary.index('\nrestore_key\n'),boundary.index('\nactivate\n'))
        self.assertLess(boundary.index('\nactivate\n'),boundary.index('\nrun_watcher\n'))

    def test_continuation_uses_only_flags_supported_by_the_original_pinned_bundle(self):
        m = self.module()
        old = subprocess.check_output(['git', '-C', str(TOOLS.parent), 'show',
            '510b1b3419593f4b1193c6249a17a7a8813712c2:tools/upgrade-eth-federator.sh'], text=True)
        old_suffix = m.resume_script(old).split(m.SUFFIX_MARKER, 1)[1]
        self.assertNotIn('--allow-source-handoff', old_suffix)
        current_suffix = m.resume_script((TOOLS/'upgrade-eth-federator.sh').read_text()).split(m.SUFFIX_MARKER, 1)[1]
        self.assertEqual(current_suffix.count('--allow-source-handoff'), 2)

    def test_continuation_binds_application_revision_from_saved_context(self):
        from unittest.mock import patch
        m=self.module()
        base={'FED_REPO':'/home/ubuntu/Bridge-SC','REPAIR_REVISION':'1'*40,'FED_IMAGE':'immutable-image',
              'RELEASE_OVERRIDE':'/private/override.json','PUBLIC_OPERATOR':'fed_2','EXPECTED_SIGNER':'0x'+'2'*40,
              'WATCH_SECONDS':'900','KEY_SOURCE':'aws'}
        for app in (None,'7'*40):
            context=dict(base)
            if app is not None:context['APP_REVISION']=app
            with patch.dict(os.environ,{'APP_REVISION':'f'*40}):
                env=m.continuation_environment(context,Path('/private/run'),Path('/private/attempt'))
            self.assertEqual(env['APP_REVISION'],app or context['REPAIR_REVISION'])
            command=m.continuation_command(Path('/private/continue.sh'),context,context['REPAIR_REVISION'],context['EXPECTED_SIGNER'])
            self.assertEqual(command[command.index('--revision')+1],'1'*40)
            if app is None:self.assertNotIn('--app-revision',command)
            else:self.assertEqual(command[command.index('--app-revision')+1],app)

    def test_continuation_monitoring_policy_comes_from_saved_run_not_ambient_environment(self):
        from unittest.mock import patch
        m=self.module()
        base={'REPAIR_REVISION':'1'*40}
        with patch.dict(os.environ,{'MONITORING_POLICY':'independent'}):
            value=m.continuation_environment(base,Path('/private/run'),Path('/private/attempt'))
        self.assertEqual(value['MONITORING_POLICY'],'legacy')
        base['MONITORING_POLICY']='independent'
        value=m.continuation_environment(base,Path('/private/run'),Path('/private/attempt'))
        self.assertEqual(value['MONITORING_POLICY'],'independent')

    def test_unknown_script_layout_refused(self):
        m=self.module()
        with self.assertRaises(m.ContinueError):m.resume_script('echo do not execute\n')

    def test_live_or_replaced_or_already_staged_node_is_refused(self):
        m=self.module()
        old={'id':'a'*64,'image_id':'sha256:'+'b'*64}
        for current, staged in [({**old,'running':True},False),
                                ({**old,'id':'c'*64,'running':False},False),
                                ({**old,'image_id':'sha256:'+'c'*64,'running':False},False),
                                ({**old,'running':False},True)]:
            with self.subTest(current=current,staged=staged),self.assertRaises(m.ContinueError):
                m.verify_original_state(old,current,staged)
        m.verify_original_state(old,{**old,'running':False},False)

    def test_private_file_symlink_and_wrong_mode_refused(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';p.write_text('{}');p.chmod(0o600)
            self.assertEqual(m.private_bytes(p),b'{}')
            link=Path(tmp)/'alias';link.symlink_to(p)
            with self.assertRaises(m.ContinueError):m.private_bytes(link)
            p.chmod(0o644)
            with self.assertRaises(m.ContinueError):m.private_bytes(p)

    def test_corrupt_history_or_missing_config_archive_refuses_continuation(self):
        import gzip, hashlib, types
        from unittest.mock import patch
        m=self.module()
        for fault in ('valid','gzip','config'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                run=Path(tmp).resolve();(run/'history').mkdir();(run/'rollback').mkdir()
                old={'id':'a'*64,'image_id':'sha256:'+'b'*64,'started':'2026-10-16T00:00:00Z'}
                def put(path,data):
                    path.write_bytes(data);path.chmod(0o600)
                put(run/'before.json',json.dumps(old).encode())
                configs={}
                for name in ('config.js','mainnet.json','rskmainnet.json','peers.config.js'):
                    put(run/'history'/name,b'original-config')
                    configs[name]=hashlib.sha256(b'original-config').hexdigest()
                data=b'old retained logs\n'
                manifest={'source_id':old['id'],'image_id':old['image_id'],
                    'uncompressed_bytes':len(data),'uncompressed_sha256':hashlib.sha256(data).hexdigest(),
                    'config_sha256':configs}
                put(run/'history/manifest.json',json.dumps(manifest).encode())
                put(run/'history/docker.log.gz',gzip.compress(data) if fault!='gzip' else b'invalid-gzip')
                put(run/'rollback/old-image.tar',b'original-image-placeholder')
                put(run/'rollback/old-image-id.txt',(old['image_id']+'\n').encode())
                if fault=='config':(run/'history/config.js').unlink()
                fake=types.SimpleNamespace(Node=lambda *a:types.SimpleNamespace(inspect=lambda:{**old,'running':False}))
                with patch.dict(sys.modules,{'federator_recovery':fake}):
                    if fault=='valid':m.pre_resume_guard(run,{'FED_REPO':str(run)})
                    else:
                        with self.assertRaises((m.ContinueError,OSError)):
                            m.pre_resume_guard(run,{'FED_REPO':str(run)})

    def test_interactive_continuation_runs_with_a_real_controlling_terminal(self):
        import fcntl, pty, termios
        self.module()
        master,slave=pty.openpty()
        def attach():
            os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
        code=("import os,sys;sys.path.insert(0,"+repr(str(TOOLS))+");"
              "import continue_eth_upgrade as m;"
              "sys.exit(m.run_attached([sys.executable,'-c',"
              "'import sys;print(\"interactive-child=\"+str(sys.stdin.isatty()))'],dict(os.environ)))")
        try:
            process=subprocess.Popen([sys.executable,'-c',code],stdin=slave,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,preexec_fn=attach)
            os.close(slave);slave=None
            out,err=process.communicate(timeout=10)
            self.assertEqual(process.returncode,0,out+'\n'+err)
            self.assertIn('interactive-child=True',out)
        finally:
            os.close(master)
            if slave is not None:os.close(slave)

    def test_context_bindings_and_checksum_are_required(self):
        m=self.module()
        rev='1'*40;signer='0x'+'2'*40
        c={'FED_REPO':'/home/ubuntu/Bridge-SC','CONFIG_DIR':'/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK',
           'REPAIR_REVISION':rev,'FED_IMAGE':'sovryn/fed-tokenbridge:repair@sha256:'+'3'*64,
           'PUBLIC_OPERATOR':'fed_3','EXPECTED_SIGNER':signer,'KEY_SOURCE':'aws','COMPOSE_PROJECT':'bridge-sc',
           'RELEASE_OVERRIDE':'/home/ubuntu/override.json','WATCH_SECONDS':'900','COMPOSE_PLAN_SHA256':'4'*64}
        m.validate_context(c,rev,signer,Path('/home/ubuntu'))
        for key,value in [('REPAIR_REVISION','5'*40),('EXPECTED_SIGNER','0x'+'6'*40),('CONFIG_DIR','/tmp/db'),
                          ('COMPOSE_PLAN_SHA256','invalid'),('WATCH_SECONDS','900; command')]:
            with self.subTest(key=key),self.assertRaises(m.ContinueError):
                m.validate_context({**c,key:value},rev,signer,Path('/home/ubuntu'))

    def test_history_completion_is_after_lock_before_guard_and_key_recovery(self):
        m=self.module();script=m.resume_script((TOOLS/'upgrade-eth-federator.sh').read_text())
        self.assertIn('--finish-history',script)
        boundary=script.split(m.SUFFIX_MARKER,1)[1]
        self.assertLess(boundary.index('--finish-history'),boundary.index('--guard --run'))
        self.assertLess(boundary.index('--guard --run'),boundary.index('\nrestore_key\n'))
        self.assertLess(script.index('flock -n 9'),script.index('--finish-history'))

    def test_verified_incomplete_history_is_retained_then_completed_without_node_actions(self):
        m=self.module()
        from test_upgrade_safety import FakeNode
        import federator_upgrade_safety as safety
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp).resolve();node=FakeNode(run);(node.cfg/'db/side-fed').mkdir(parents=True)
            (node.cfg/'db/lastBlock.txt').write_text('9330278')
            (node.cfg/'db/side-fed/lastBlock.txt').write_text('26206212')
            old=node.inspect()
            for name,value in [('before.json',old),('stopped-state.json',m.stopped_snapshot(node))]:
                (run/name).write_text(json.dumps(value));(run/name).chmod(0o600)
            history=run/'history';history.mkdir(mode=0o700)
            (history/'docker.log.gz.partial').write_bytes(b'partial-original');(history/'docker.log.gz.partial').chmod(0o600)
            original=safety.archive_history
            def complete(n,out):return original(n,out,command=[sys.executable,'-c','print("retained-history")'])
            with patch.object(safety,'archive_history',side_effect=complete):
                result=m.finish_history(run,{'FED_REPO':str(run)},node=node,helper=safety)
            self.assertTrue((history/'manifest.json').exists())
            retained=list(run.glob('history.incomplete-*'));self.assertEqual(len(retained),1)
            self.assertEqual((retained[0]/'docker.log.gz.partial').read_bytes(),b'partial-original')
            self.assertEqual(node.commands,[])
            self.assertFalse(node.state['running'])
            self.assertEqual((node.cfg/'db/lastBlock.txt').read_text(),'9330278')
            with patch.object(safety,'archive_history',side_effect=AssertionError('completed archive must not be repeated')):
                self.assertFalse(m.finish_history(run,{'FED_REPO':str(run)},node=node,helper=safety))

    def test_changed_checkpoint_refuses_before_retaining_or_rebuilding_history(self):
        m=self.module()
        from test_upgrade_safety import FakeNode
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp).resolve();node=FakeNode(run);(node.cfg/'db/side-fed').mkdir(parents=True)
            (node.cfg/'db/lastBlock.txt').write_text('100')
            for name,value in [('before.json',node.inspect()),('stopped-state.json',m.stopped_snapshot(node))]:
                (run/name).write_text(json.dumps(value));(run/name).chmod(0o600)
            (run/'history').mkdir(mode=0o700)
            (node.cfg/'db/lastBlock.txt').write_text('101')
            with self.assertRaises(m.ContinueError):m.finish_history(run,{'FED_REPO':str(run)},node=node)
            self.assertFalse(list(run.glob('history.incomplete-*')))
            self.assertEqual(node.commands,[])


    def test_internal_history_completion_requires_the_same_real_lock_descriptor(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();lock=root/'eth-upgrade.lock';lock.write_text('');lock.chmod(0o600)
            script=('import os,sys,fcntl;from pathlib import Path;sys.path.insert(0,'+repr(str(TOOLS))+');'
                    'import continue_eth_upgrade as m;fd=os.open('+repr(str(lock))+',os.O_WRONLY);'
                    'os.dup2(fd,9);fcntl.flock(9,fcntl.LOCK_EX|fcntl.LOCK_NB);'
                    'm.require_inherited_lock(Path('+repr(str(root))+'));print("LOCK_OK")')
            value=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
            self.assertEqual(value.returncode,0,value.stderr);self.assertIn('LOCK_OK',value.stdout)
            missing=script.replace('os.dup2(fd,9);fcntl.flock(9,fcntl.LOCK_EX|fcntl.LOCK_NB);','')
            value=subprocess.run([sys.executable,'-c',missing],capture_output=True,text=True)
            self.assertNotEqual(value.returncode,0)
            self.assertIn('History completion requires',value.stderr)

    def test_repaired_helper_is_verified_by_digest_before_loading(self):
        m=self.module()
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp).resolve()
            with patch.object(m,'HISTORY_HELPER_SHA256','0'*64):
                with self.assertRaises(m.ContinueError):m.load_history_helper(run)
            helper=m.load_history_helper(run)
            self.assertTrue(callable(helper.database_records))
            self.assertEqual(helper.VERSION,'1.2.0')

    def test_guard_uses_repaired_helper_when_old_saved_helper_has_no_database_support(self):
        import types,gzip,hashlib
        import federator_recovery as recovery
        import federator_upgrade_safety as safety
        from test_upgrade_safety import FakeNode
        from unittest.mock import patch
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp).resolve();node=FakeNode(run);(node.cfg/'db').mkdir();(node.cfg/'db/lastBlock.txt').write_text('100')
            history=run/'history';safety.archive_history(node,history,command=[sys.executable,'-c','print("history")'])
            (run/'rollback').mkdir()
            for name,data in [('before.json',json.dumps(node.inspect()).encode()),('rollback/old-image-id.txt',(node.state['image_id']+'\n').encode()),('rollback/old-image.tar',b'archived-image-placeholder')]:
                p=run/name;p.write_bytes(data);p.chmod(0o600)
            with patch.object(recovery,'Node',return_value=node),patch.dict(sys.modules,{'federator_upgrade_safety':types.SimpleNamespace(VERSION='1.0.0')}):
                m.pre_resume_guard(run,{'FED_REPO':str(run)})


    def test_failed_history_retry_keeps_original_partial_and_never_starts_node(self):
        m=self.module()
        import federator_upgrade_safety as safety
        from test_upgrade_safety import FakeNode
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp).resolve();node=FakeNode(run);(node.cfg/'db').mkdir()
            for name,value in [('before.json',node.inspect()),('stopped-state.json',m.stopped_snapshot(node))]:
                p=run/name;p.write_text(json.dumps(value));p.chmod(0o600)
            (run/'history').mkdir(mode=0o700);(run/'history/docker.log.gz.partial').write_bytes(b'old evidence')
            original=safety.archive_history
            def fail(n,p):return original(n,p,command=[sys.executable,'-c','import sys;sys.exit(1)'])
            with patch.object(safety,'archive_history',side_effect=fail),self.assertRaises(m.ContinueError):
                m.finish_history(run,{'FED_REPO':str(run)},node=node,helper=safety)
            kept=list(run.glob('history.incomplete-*'));self.assertEqual(len(kept),1)
            self.assertEqual((kept[0]/'docker.log.gz.partial').read_bytes(),b'old evidence')
            self.assertFalse((run/'history/manifest.json').exists())
            self.assertEqual(json.loads((run/'history/progress.json').read_text())['failure']['reason'],'LOG_READ_FAILED')
            self.assertEqual(node.commands,[])
            self.assertFalse(node.state['running'])

    def test_real_bash_passes_the_upgrade_lock_to_history_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();lock=root/'eth-upgrade.lock';lock.write_text('');lock.chmod(0o600)
            code='import sys;from pathlib import Path;sys.path.insert(0,'+repr(str(TOOLS))+');import continue_eth_upgrade as m;m.require_inherited_lock(Path('+repr(str(root))+'));print("BASH_LOCK_OK")'
            result=subprocess.run(['bash','-c','exec 9> "$1/eth-upgrade.lock"\nexec "$2" -c "$3"','bash',str(root),sys.executable,code],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('BASH_LOCK_OK',result.stdout)


if __name__=='__main__':unittest.main()
