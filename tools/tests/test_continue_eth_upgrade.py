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

if __name__=='__main__':unittest.main()
