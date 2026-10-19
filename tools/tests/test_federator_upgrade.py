import os
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'upgrade-eth-federator.sh'


class UpgradeExecutableTests(unittest.TestCase):
    def test_executable_exists(self):
        self.assertTrue(SCRIPT.is_file(), 'upgrade must be a repository executable')
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    @unittest.skipUnless(SCRIPT.exists(), 'executable not implemented')
    def test_bash_syntax(self):
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True)

    @unittest.skipUnless(SCRIPT.exists(), 'executable not implemented')
    def test_frozen_plan_excludes_other_services_and_escapes_literal_dollars(self):
        import re
        text=SCRIPT.read_text()
        code=re.search(r"config --format json \| python3 -c '(.*?)'\nCOMPOSE_PLAN_SHA256",text,re.S)[1]
        with tempfile.TemporaryDirectory() as tmp:
            cfg=tmp+'/config';image='sovryn/fed-tokenbridge:release@sha256:'+'5'*64
            service={'image':image,'container_name':'bridge-sc_federation_1','volumes':[
                {'type':'bind','source':cfg,'target':'/app/federator/config'},
                {'type':'bind','source':cfg+'/db','target':'/app/federator/db'}],
                'ports':[{'published':'4444','target':30303}],'restart':'no','user':'1000:1000',
                'environment':{'TZ':'UTC','LITERAL':'$KEEP_ME'},'logging':{'driver':'json-file','options':{'max-size':'20m','max-file':'5'}}}
            full={'services':{'federation':service,'datadog':{'environment':{'DD_API_KEY':'exclude-this-value'}}}}
            result=subprocess.run([sys.executable,'-c',code],input=json.dumps(full),text=True,capture_output=True,
                env={**os.environ,'OPS_DIR':tmp,'CONFIG_DIR':cfg,'FED_IMAGE':image})
            self.assertEqual(result.returncode,0,result.stderr)
            plan=json.loads((Path(tmp)/'deployment.private.json').read_text())
            self.assertEqual(list(plan['services']),['federation'])
            self.assertEqual(plan['services']['federation']['environment']['LITERAL'],'$$KEEP_ME')
            self.assertNotIn('exclude-this-value',json.dumps(plan))

    def test_help_and_bad_parameters_need_no_docker_or_terminal(self):
        help_result = subprocess.run(['bash', str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0)
        for flag in ('--image', '--override', '--revision', '--no-aws-secrets', '--rollback'):
            self.assertIn(flag, help_result.stdout)
        for arguments in (['--image'], ['--unknown'], ['--watch-seconds','0'], ['--watch-seconds','evil'], ['--monitoring-only','--rollback','/private/run']):
            result = subprocess.run(['bash', str(SCRIPT)] + arguments, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            if '--monitoring-only' in arguments:self.assertIn('Cannot combine',result.stderr)



# These tests run the real shell state machine against disposable command doubles.
# Existing recovery tests separately exercise its actual file/mount/identity guards.
import json
import pty
import tempfile

FAKE_COMMAND = r'''import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name;args=sys.argv[1:]
trace=Path(os.environ['UPGRADE_TRACE'])
def note(value):
 with trace.open('a') as out:out.write(value+'\n')
old='sha256:'+'3'*64;new='sha256:'+'4'*64
if name=='id':print('1000')
elif name=='flock':pass
elif name=='git':
 a=args[2:];note('GIT '+' '.join(a))
 if a[0]=='remote':print('https://github.com/DistributedCollective/Bridge-SC.git')
 elif a[0]=='show':print('{}')
 elif a[0]=='hash-object':print('2'*40)
 elif a[0]=='rev-parse':
  print('2'*40 if ':tools/' in a[-1] else '1'*40)
elif name=='docker':
 a=args[2:];note('DOCKER '+' '.join(a))
 if 'save' in a:
  if os.environ.get('UPGRADE_FAIL')=='backup':sys.exit(1)
  Path(a[a.index('--output')+1]).write_bytes(b'fake-image')
 elif a[:2]==['image','inspect']:
  print(os.environ.get('UPGRADE_IMAGE_REV','1'*40) if 'revision' in a[-1] else old if a[2]==old else new)
 elif 'config' in a and '--format' in a:print('{}')
elif name=='python3':
 if args and args[0].endswith('federator_compose_plan.py'):
  mode=args[1];note('COMPOSE_'+('BASE' if mode=='--base' else 'MODEL'))
  sys.stdin.read();Path(args[2]).write_text('{}')
 elif args and args[0].endswith('federator_signing_key.py'):
  note('KEY_SOURCE='+os.environ['KEY_SOURCE'])
 elif args and args[0].endswith('federator_upgrade_safety.py'):
  action='HISTORY_BACKUP' if '--archive-history' in args else 'START_AND_CLEANUP'
  note(action)
  if os.environ.get('UPGRADE_FAIL')=='history' and action=='HISTORY_BACKUP':sys.exit(1)
  if action=='START_AND_CLEANUP':note('DOCKER start bridge-sc_federation_1')
 elif args and args[0].endswith('federator_upgrade_monitoring.py'):
  action=args[1];note('MONITORING_'+action[2:].upper())
  if action=='--snapshot':Path(args[2]).mkdir()
  if os.environ.get('UPGRADE_FAIL')=='datadog' and action!='--result':sys.exit(1)
 elif args and args[0].endswith('federator_datadog_upgrade.py'):
  action=args[1];note('DATADOG_'+action[2:].upper())
  if os.environ.get('UPGRADE_FAIL')=='datadog' and action=='--inspect':sys.exit(1)
  if action in ('--inspect','--capture'):Path(args[2]).mkdir()
 elif args and args[0].endswith('etherscan_prerequisite.py'):
  note('ETHERSCAN_CHECK')
  if os.environ.get('UPGRADE_FAIL')=='etherscan':sys.exit(1)
 elif args and args[0].endswith('federator_watcher.py'):
  note('WATCHER');dest=Path(args[args.index('--output-dir')+1]);dest.mkdir()
  (dest/'summary.md').write_text('summary');(dest/'report.json').write_text('{}')
 elif args and args[0].endswith('federator_dependencies.py'):
  Path(args[args.index('--output')+1]).write_text('{}')
 else:
  code=args[1] if args and args[0]=='-c' else sys.stdin.read()
  root=Path(os.environ['OPS_DIR'])
  if args and args[0]=='-c' and 'full=json.load' in code:
   sys.stdin.read()
   (root/'deployment.private.json').write_text('{}')
  elif args and args[0]=='-c':
   print('bridge-sc' if 'compose_project' in code else old if 'image_id' in code else 'a'*64)
  elif "fields=('FED_REPO'" in code:
   sys.argv=args;exec(compile(code,'context-fixture','exec'),{})
  elif "import getpass,os,stat" in code:note('KEY_SOURCE='+os.environ['KEY_SOURCE'])
  elif "s['compose_project']=project" in code:
   (root/'before.json').write_text(json.dumps({'id':'a'*64,'image_id':old,'compose_project':'bridge-sc'}))
  elif "print(json.dumps({p:hashlib" in code:exec(compile(code,'image-source-hashes','exec'),{})
  elif "root/'old-image-id.txt'" in code:(root/'rollback'/'old-image-id.txt').write_text(old+'\n')
  elif "path.rename(root/" in code:(root/'rollback'/'old-image.tar.partial').rename(root/'rollback'/'old-image.tar')
  elif "if s['running']:node.runner.run" in code:note('STOP_ORIGINAL')
  elif "p.chmod(0o600)" in code and "replacement.json" in code:note('STAGED_REPLACEMENT')
'''


@unittest.skipUnless(SCRIPT.exists(), 'executable not implemented')
class UpgradeOrchestrationTests(unittest.TestCase):
    def run_upgrade(self, fail=None, rollback=False, tamper=False, app_revision=None, image_revision=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bin_path=root/'bin';bin_path.mkdir()
            for name in ('git','docker','id','python3','flock'):
                path=bin_path/name
                path.write_text('#!'+sys.executable+'\n'+FAKE_COMMAND)
                path.chmod(0o755)
            repo=root/'repo';repo.mkdir();override=root/'override.json';override.write_text('{}')
            trace=root/'trace';trace.touch()
            env=dict(os.environ,HOME=str(root),PATH=str(bin_path)+os.pathsep+os.environ['PATH'],UPGRADE_TRACE=str(trace))
            if fail:env['UPGRADE_FAIL']=fail
            if image_revision:env['UPGRADE_IMAGE_REV']=image_revision
            master,slave=pty.openpty()
            try:
                process=subprocess.Popen(['bash',str(SCRIPT),'--repo',str(repo),'--revision','1'*40,
                    '--image','sovryn/fed-tokenbridge:repair@sha256:'+'5'*64,'--override',str(override),
                    '--operator','fed_1','--expected-signer','0x'+'6'*40,'--watch-seconds','1']+(['--app-revision',app_revision] if app_revision else []),
                    stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
                os.close(slave);slave=None
                os.write(master,b'y\n')
                stdout,stderr=process.communicate(timeout=30)
                if rollback and process.returncode==0:
                    run=next(p for p in (root/'.local/share/bridge-ops').glob('eth-upgrade.*') if p.is_dir())
                    override.unlink()  # A moved original override must not prevent rollback.
                    if tamper:(run/'deployment.private.json').write_text('changed')
                    trace.write_text('')
                    rollback_master,rollback_slave=pty.openpty()
                    try:
                        process=subprocess.Popen(['bash',str(run/'upgrade.sh'),'--rollback',str(run),'--no-aws-secrets','--watch-seconds','1'],
                            stdin=rollback_slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
                        os.close(rollback_slave);rollback_slave=None
                        os.write(rollback_master,b'y\ny\n')
                        stdout,stderr=process.communicate(timeout=30)
                    finally:
                        os.close(rollback_master)
                        if rollback_slave is not None:os.close(rollback_slave)
                return process.returncode,trace.read_text().splitlines(),stdout,stderr
            finally:
                if process.poll() is None:
                    process.kill(); process.communicate(timeout=5)
                os.close(master)
                if slave is not None:os.close(slave)

    def test_new_tools_accept_the_pinned_existing_application_revision(self):
        result,trace,stdout,stderr=self.run_upgrade(app_revision='7'*40,image_revision='7'*40)
        self.assertEqual(result,0,stdout+'\n'+stderr)
        self.assertTrue(any('show '+'7'*40+':sovryn-token-bridge/federator/' in line for line in trace))
        self.assertEqual(trace[-1],'MONITORING_RESULT')

    def test_wrong_application_revision_stops_before_backup_and_services(self):
        result,trace,stdout,stderr=self.run_upgrade(app_revision='7'*40,image_revision='8'*40)
        self.assertNotEqual(result,0)
        self.assertNotIn('STOP_ORIGINAL',trace)
        self.assertFalse(any('image save' in line for line in trace))

    def test_rollback_uses_saved_plan_without_original_override_and_honors_manual_key(self):
        result,trace,stdout,stderr=self.run_upgrade(rollback=True)
        self.assertEqual(result,0,stdout+'\n'+stderr)
        self.assertTrue(any('image load' in line for line in trace))
        self.assertIn('KEY_SOURCE=manual',trace)
        self.assertEqual(sum(line.startswith('DOCKER start ') for line in trace),1)
        self.assertFalse(any(' pull ' in ' '+line+' ' for line in trace))
        self.assertNotIn('ETHERSCAN_CHECK',trace)
        self.assertEqual(trace[-1],'MONITORING_RESULT')
        self.assertIn('HISTORY_BACKUP',trace)
        self.assertIn('START_AND_CLEANUP',trace)

    def test_tampered_rollback_plan_fails_before_any_container_stop_or_load(self):
        result,trace,stdout,stderr=self.run_upgrade(rollback=True,tamper=True)
        self.assertNotEqual(result,0)
        self.assertIn('Read the saved rollback context',stdout)
        self.assertFalse(any('image load' in line or line.startswith('DOCKER start ') for line in trace))
        self.assertNotIn('KEY_SOURCE=manual',trace)

    def test_missing_invalid_etherscan_check_blocks_image_download_and_stop(self):
        result,trace,stdout,stderr=self.run_upgrade('etherscan')
        self.assertNotEqual(result,0)
        self.assertIn('ETHERSCAN_CHECK',trace)
        self.assertFalse(any(' pull ' in ' '+line+' ' for line in trace))
        self.assertNotIn('STOP_ORIGINAL',trace)
        self.assertNotIn('WATCHER',trace)

    def test_failed_image_backup_never_stops_original_or_starts_replacement(self):
        result,trace,stdout,stderr=self.run_upgrade('backup')
        self.assertNotEqual(result,0)
        self.assertIn('ETHERSCAN_CHECK',trace)
        self.assertTrue(any('image save' in line for line in trace))
        self.assertNotIn('STOP_ORIGINAL',trace)
        self.assertFalse(any(line.startswith('DOCKER start ') for line in trace))

    def test_datadog_failure_does_not_prevent_application_start_or_rollback(self):
        result,trace,stdout,stderr=self.run_upgrade('datadog')
        self.assertNotIn('DATADOG_INSPECT',trace)
        self.assertIn('STOP_ORIGINAL',trace)
        self.assertIn('STAGED_REPLACEMENT',trace)
        self.assertIn('START_AND_CLEANUP',trace)
        self.assertIn('MONITORING_RECOVER',trace)
        self.assertIn('WATCHER',trace)
        self.assertLess(trace.index('START_AND_CLEANUP'),trace.index('MONITORING_RECOVER'))
        result,trace,stdout,stderr=self.run_upgrade('datadog',rollback=True)
        self.assertTrue(any('image load' in line for line in trace),stdout+stderr)
        self.assertIn('START_AND_CLEANUP',trace)

    def test_only_app_model_is_interpolated_before_backup_or_stop(self):
        result,trace,stdout,stderr=self.run_upgrade()
        self.assertEqual(result,0,stdout+'\n'+stderr)
        self.assertIn('COMPOSE_BASE',trace)
        self.assertIn('COMPOSE_MODEL',trace)
        uninterpolated=[line for line in trace if 'config --no-interpolate --format json' in line]
        self.assertEqual(len(uninterpolated),1)
        resolved=[line for line in trace if 'config --format json' in line and '--no-interpolate' not in line]
        self.assertEqual(len(resolved),1)
        self.assertIn('federation-input.private.json',resolved[0])
        self.assertNotIn('docker-compose-prod.yml',resolved[0])

    def test_failed_history_backup_never_replaces_or_starts_container(self):
        result,trace,stdout,stderr=self.run_upgrade('history')
        self.assertNotEqual(result,0)
        self.assertIn('HISTORY_BACKUP',trace)
        self.assertNotIn('STAGED_REPLACEMENT',trace)
        self.assertFalse(any(line.startswith('DOCKER start ') for line in trace))

    def test_complete_sequence_checks_key_and_backup_before_stopping_only_eth(self):
        result,trace,stdout,stderr=self.run_upgrade()
        self.assertEqual(result,0,stdout+'\n'+stderr)
        backup=next(i for i,line in enumerate(trace) if 'image save' in line)
        self.assertLess(trace.index('ETHERSCAN_CHECK'),backup)
        self.assertLess(backup,trace.index('STOP_ORIGINAL'))
        self.assertLess(trace.index('STOP_ORIGINAL'),trace.index('HISTORY_BACKUP'))
        self.assertLess(trace.index('HISTORY_BACKUP'),trace.index('STAGED_REPLACEMENT'))
        self.assertLess(trace.index('STAGED_REPLACEMENT'),trace.index('START_AND_CLEANUP'))
        self.assertLess(trace.index('START_AND_CLEANUP'),trace.index('MONITORING_RECOVER'))
        self.assertEqual(sum(line.startswith('DOCKER start ') for line in trace),1)
        self.assertEqual(trace[-1],'MONITORING_RESULT')
        self.assertLess(trace.index('MONITORING_SNAPSHOT'),trace.index('STOP_ORIGINAL'))
        self.assertLess(trace.index('STAGED_REPLACEMENT'),trace.index('MONITORING_RECOVER'))
        self.assertFalse(any('datadog-agent' in line or 'bsc' in line.lower() or ' down' in line or 'prune' in line for line in trace))

if __name__ == '__main__': unittest.main()
