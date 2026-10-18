import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from test_upgrade_eth_node import fixture

TOOLS = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location('federator_environment', TOOLS/'federator_environment.py')
    m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class EnvironmentTests(unittest.TestCase):
    def test_sanitized_fixture_preserves_mismatch_without_exporting_values(self):
        m=module();c,i=fixture()
        i['Config']['Env'].append('TOKEN=PRIVATE_IMAGE_TOKEN')
        c['Config']['Env'].extend(['TOKEN=PRIVATE_CURRENT_TOKEN','PASSWORD=PRIVATE_PASSWORD'])
        c['Config']['Labels']['custom.example/logs']='PRIVATE_LABEL'
        c['Config']['Cmd']=['sh','-c','PRIVATE_COMMAND']
        c['HostConfig']['SecurityOpt']=['PRIVATE_SECURITY_OPTION']
        c['HostConfig']['LogConfig']['Config']['env']='PRIVATE_LOG_OPTION'
        c['Mounts'].append({'Source':'PRIVATE_BIND_SOURCE','Destination':'/PRIVATE_TARGET','Type':'bind','RW':True})
        snap=m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC'))
        text=json.dumps(snap)
        self.assertNotIn('PRIVATE_',text)
        self.assertNotEqual(snap['container']['Config']['Cmd'],snap['image']['Config']['Cmd'])
        ce=dict(x.split('=',1) for x in snap['container']['Config']['Env'])
        ie=dict(x.split('=',1) for x in snap['image']['Config']['Env'])
        self.assertNotEqual(ce['TOKEN'],ie['TOKEN'])
        self.assertEqual(ce['PATH'],ie['PATH'])
        self.assertIn('PASSWORD',ce)
        self.assertEqual(snap['container']['HostConfig']['LogConfig']['Config']['env'],'[withheld]')

    def test_resource_profile_and_linux_metadata_are_reproducible(self):
        m=module();c,i=fixture()
        c['HostConfig'].update(Memory=1024**3,MemorySwappiness=-1,ShmSize=134217728,
                              IpcMode='shareable',Runtime='runc',PidsLimit=256,CpusetCpus='0-1')
        i['Config']['ArgsEscaped']=True
        snap=m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC'))
        for k in ('Memory','MemorySwappiness','ShmSize','IpcMode','Runtime','PidsLimit','CpusetCpus'):
            self.assertEqual(snap['container']['HostConfig'][k],c['HostConfig'][k])
        self.assertTrue(snap['image']['Config']['ArgsEscaped'])
        self.assertNotIn('ArgsEscaped',snap['container']['Config'])

    def test_safe_public_config_never_exports_url_credentials_or_private_literals(self):
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=root/'federator-env/mainnet-ETH-RSK';cfg.mkdir(parents=True)
            (cfg/'config.js').write_text("module.exports={federatorAddress:'0x"+'11'*20+"',minimumPeerAmount:2,privateKey:'PRIVATE_LITERAL',etherscanApiKey:'PRIVATE_API'}")
            (cfg/'mainnet.json').write_text(json.dumps({'host':'https://PRIVATE_USER:PRIVATE_PASSWORD@rpc.example/api/PRIVATE_PATH?apikey=PRIVATE_QUERY','chainId':1,'fromBlock':26148971,'bridge':'0x'+'22'*20,'privateKey':'PRIVATE_JSON','apiKey':'0x'+'aa'*20}))
            (cfg/'rskmainnet.json').write_text(json.dumps({'host':'https://rsk.example/rpc','chainId':30,'fromBlock':9307691}))
            (cfg/'peers.config.js').write_text('module.exports='+json.dumps({'peers':[{'address':'0x'+'33'*20,'ip':'192.0.2.8','port':4444,'password':'PRIVATE_PEER'}]}))
            (cfg/'db/side-fed').mkdir(parents=True)
            (cfg/'db/lastBlock.txt').write_text('9307999')
            (cfg/'db/side-fed/lastBlock.txt').write_text('26149999')
            (cfg/'federator.key').write_text('PRIVATE_SIGNING_KEY')
            data=m.public_configuration(root)
            self.assertNotIn('PRIVATE_',json.dumps(data))
            self.assertNotIn('aa'*20,json.dumps(data))
            self.assertEqual(data['chains']['ethereum']['endpoint']['provider'],'custom')
            self.assertTrue(data['chains']['ethereum']['endpoint']['credentials_or_path_withheld'])
            self.assertEqual(data['cursors']['rootstock'],'9307999')
            self.assertEqual(data['cursors']['ethereum'],'26149999')
            self.assertTrue(data['key_files']['federator.key']['present'])

    def test_public_config_refuses_symlink_and_fifo_without_reading(self):
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=root/'federator-env/mainnet-ETH-RSK';cfg.mkdir(parents=True)
            outside=root/'private';outside.write_text('PRIVATE_OUTSIDE');(cfg/'config.js').symlink_to(outside)
            os.mkfifo(cfg/'mainnet.json')
            data=m.public_configuration(root)
            self.assertNotIn('PRIVATE_OUTSIDE',json.dumps(data))
            self.assertEqual(data['config_status'],'UNAVAILABLE')
            self.assertEqual(data['chains']['ethereum']['status'],'UNAVAILABLE')

    def test_capture_keeps_independent_evidence_after_agent_or_runtime_failure(self):
        m=module();c,i=fixture()
        class Runner:
            def __init__(self):self.calls=[]
            def run(self,args,timeout=20):
                self.calls.append(args)
                if args[:3]==['git','-C',str(Path('/missing'))]:return 'a'*40
                if args[0]=='git':return 'a'*40
                if args[3:]==['version','--format','{{json .}}']:return json.dumps({'Client':{'Version':'20.10.5','ApiVersion':'1.41'},'Server':{'Version':'20.10.5','ApiVersion':'1.41','Os':'linux','Arch':'amd64'}})
                if args[3:]==['compose','version']:return 'Docker Compose version v2.40.3'
                raise RuntimeError('PRIVATE_FAILURE_DO_NOT_PRINT')
        runner=Runner()
        data=m.collect(Path('/missing'),runner,'fed_2',c,i)
        self.assertNotIn('PRIVATE_FAILURE',json.dumps(data))
        self.assertEqual(data['docker']['server_version'],'20.10.5')
        self.assertEqual(data['agent']['status'],'UNAVAILABLE')
        self.assertEqual(data['application_probe']['status'],'UNAVAILABLE')
        self.assertEqual(data['deployment']['container']['HostConfig']['ShmSize'],67108864)
        for args in runner.calls:
            self.assertNotIn('start',args);self.assertNotIn('stop',args);self.assertNotIn('rm',args)
            self.assertNotIn('get-secret-value',args)

    def test_bundle_private_exclusive_and_contains_only_allowlisted_reports(self):
        m=module();c,i=fixture()
        report={'schema':1,'operator':'fed_2','deployment':m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC')),'checks':[{'status':'BLOCKER','summary':'Runtime settings need review'}]}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            bundle=m.write_bundle(report,root)
            self.assertEqual(bundle.stat().st_mode&0o777,0o600)
            with zipfile.ZipFile(bundle) as z:self.assertEqual(set(z.namelist()),{'environment.json','summary.txt'})
            self.assertEqual(m.load_replay(root/'environment.json')['schema'],1)
            with self.assertRaises((FileExistsError,m.EnvironmentError)):
                m.write_bundle(report,root)
            alias=root/'alias.json';alias.symlink_to(root/'environment.json')
            with self.assertRaises(m.EnvironmentError):m.load_replay(alias)

    def test_credential_like_hostname_is_not_exported(self):
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=root/'federator-env/mainnet-ETH-RSK';cfg.mkdir(parents=True)
            (cfg/'mainnet.json').write_text(json.dumps({'host':'https://PRIVATE_HOST_TOKEN.provider.example/'}))
            data=m.public_configuration(root)
            self.assertNotIn('PRIVATE_HOST_TOKEN',json.dumps(data))
            self.assertEqual(data['chains']['ethereum']['endpoint']['provider'],'custom')

    def test_duplicate_env_and_normalized_binds_keep_all_replay_blockers(self):
        from test_upgrade_eth_node import LauncherTests
        launcher=LauncherTests.module(self);m=module()
        for duplicate in (False,True):
            c,i=fixture()
            c['HostConfig']['Binds']=['/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK/:/app/federator/config:rw',
                '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK/db:/app/federator/db:rw']
            if duplicate:c['Config']['Env'].append('PATH=/usr/bin')
            raw=[];launcher.make_override(c,i,Path('/home/ubuntu/Bridge-SC'),issues=raw)
            snap=m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC'));replay=[]
            launcher.make_override(snap['container'],snap['image'],Path(snap['repo']),issues=replay)
            self.assertEqual(raw,replay)

    def test_previous_run_cannot_escape_private_operations_root(self):
        m=module();c,i=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);base=home/'.local/share/bridge-ops';base.mkdir(parents=True)
            outside=home/'outside';(outside/'rollback').mkdir(parents=True);outside.chmod(0o700)
            (outside/'rollback/old-container.private.json').write_text(json.dumps(c))
            target=base/'../../../outside'
            class Runner:
                def run(self,args,timeout=20):
                    if args[3:5]==['image','inspect']:return json.dumps([i])
                    raise RuntimeError()
            with patch.object(m.Path,'home',return_value=home):
                data=m.collect(home,Runner(),'fed_2',c,i,previous_run=target)
            self.assertEqual(data['previous_deployment'],{'status':'UNAVAILABLE'})

    def test_untrusted_nested_probe_fields_are_not_exported(self):
        m=module();c,i=fixture()
        class Runner:
            def run(self,args,timeout=20):
                if '-e' in args:
                    return json.dumps({'status':'OBSERVED','node':'v14.21.3','packages':{'ethers':'PRIVATE_INJECTED','evil':'PRIVATE_EXTRA'},'sources':{},'rpc':{}})
                raise RuntimeError()
        data=m.collect(Path('/missing'),Runner(),'fed_2',c,i)
        self.assertNotIn('PRIVATE_',json.dumps(data))

    def test_only_matching_retained_eth_upgrade_is_discovered(self):
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);repo=home/'Bridge-SC';base=home/'.local/share/bridge-ops';base.mkdir(parents=True)
            good=base/'eth-upgrade.fixture';(good/'rollback').mkdir(parents=True);good.chmod(0o700)
            (good/'upgrade-context.json').write_text(json.dumps({'CONFIG_DIR':str(repo/'federator-env/mainnet-ETH-RSK'),'FED_REPO':str(repo)}))
            (good/'rollback/old-container.private.json').write_text('{}')
            other=base/'eth-upgrade.other';(other/'rollback').mkdir(parents=True);other.chmod(0o700)
            (other/'upgrade-context.json').write_text(json.dumps({'CONFIG_DIR':str(repo/'federator-env/mainnet-BSC-RSK'),'FED_REPO':str(repo)}))
            (other/'rollback/old-container.private.json').write_text('{}')
            alias=base/'eth-upgrade.link';alias.symlink_to(good)
            with patch.object(m.Path,'home',return_value=home):self.assertEqual(m.find_previous_run(repo),good)

    def test_actual_saved_inspect_array_is_collected_with_cached_or_archived_image(self):
        import tarfile,hashlib
        m=module()
        for cached in (True,False):
            with self.subTest(image_cached=cached),tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp);repo=home/'Bridge-SC';root=home/'.local/share/bridge-ops/eth-upgrade.fixture'
                (root/'rollback').mkdir(parents=True);root.chmod(0o700)
                c,i=fixture();c['HostConfig']['IpcMode']='shareable';c['Config']['Env'].append('API_KEY=PRIVATE_RETAINED_VALUE')
                raw=json.dumps({'os':'linux','architecture':'amd64','config':i['Config']}).encode()
                digest=hashlib.sha256(raw).hexdigest();c['Image']=i['Id']='sha256:'+digest
                (root/'upgrade-context.json').write_text(json.dumps({'CONFIG_DIR':str(repo/'federator-env/mainnet-ETH-RSK'),'FED_REPO':str(repo)}))
                # The real upgrader stores raw docker inspect: a one-element array.
                (root/'rollback/old-container.private.json').write_text(json.dumps([c]))
                with tarfile.open(root/'rollback/old-image.tar','w') as archive:
                    item=tarfile.TarInfo(digest+'.json');item.size=len(raw);archive.addfile(item,io.BytesIO(raw))
                class Runner:
                    def run(self,args,timeout=20):
                        if args[3:5]==['image','inspect'] and cached:return json.dumps([i])
                        raise RuntimeError()
                with patch.object(m.Path,'home',return_value=home):data=m.collect(repo,Runner(),'fed_3',c,i)
                self.assertEqual(data['previous_deployment']['container']['HostConfig']['IpcMode'],'shareable')
                self.assertNotIn('PRIVATE_RETAINED_VALUE',json.dumps(data))

    def test_original_image_config_can_be_read_without_loading_archived_layers(self):
        import tarfile,hashlib
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'rollback').mkdir()
            raw=json.dumps({'architecture':'amd64','os':'linux','config':{'Env':['API_KEY=PRIVATE_ARCHIVE_VALUE']}}).encode()
            digest=hashlib.sha256(raw).hexdigest()
            with tarfile.open(root/'rollback/old-image.tar','w') as archive:
                header=tarfile.TarInfo(digest+'.json');header.size=len(raw);archive.addfile(header,io.BytesIO(raw))
                header=tarfile.TarInfo('layer.tar');header.size=65536;archive.addfile(header,io.BytesIO(b'x'*65536))
            value=m.archived_image(root,'sha256:'+digest)
            self.assertEqual(value['Id'],'sha256:'+digest)
            self.assertEqual(value['Config']['Env'],['API_KEY=PRIVATE_ARCHIVE_VALUE'])
            with self.assertRaises(m.EnvironmentError):m.archived_image(root,'--format=unexpected')
            with self.assertRaises(m.EnvironmentError):m.archived_image(root,'sha256:'+'f'*64)

    def test_malformed_peer_rows_do_not_abort_other_capture(self):
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=root/'federator-env/mainnet-ETH-RSK';cfg.mkdir(parents=True)
            (cfg/'config.js').write_text('module.exports={minimumPeerAmount:2,}')
            (cfg/'peers.config.js').write_text('module.exports={"peers":[null]}')
            data=m.public_configuration(root)
            self.assertEqual(data['config_status'],'OBSERVED')
            self.assertEqual(data['peers_status'],'UNAVAILABLE')

    def test_agent_mount_roles_remain_reproducible_without_private_sources(self):
        m=module();c,i=fixture()
        c['Mounts']=[{'Type':'bind','Source':'/var/run/docker.sock','Destination':'/var/run/docker.sock','RW':False},
            {'Type':'volume','Name':'PRIVATE_VOLUME_NAME','Source':'/PRIVATE_VOLUME_SOURCE','Destination':'/var/log/datadog','RW':True},
            {'Type':'bind','Source':'/var/lib/docker/containers','Destination':'/var/lib/docker/containers','RW':False}]
        data=m.sanitize_deployment(c,{},Path('/home/ubuntu/Bridge-SC'),agent=True)
        self.assertEqual([v['Destination'] for v in data['container']['Mounts']],['/var/run/docker.sock','/var/log/datadog','/var/lib/docker/containers'])
        self.assertNotIn('PRIVATE_',json.dumps(data))

    def test_unknown_fields_preserve_presence_without_secret_strings(self):
        m=module();c,i=fixture()
        c['HostConfig']['UnknownSetting']={'password':'PRIVATE_NEW_VALUE'}
        c['NetworkSettings']['Networks']['bridge-sc_default']['DriverOpts']={'password':'PRIVATE_NET'}
        value=m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC'))
        self.assertNotIn('PRIVATE_',json.dumps(value))
        self.assertTrue(value['container']['HostConfig']['UnknownSetting'])
        self.assertTrue(value['container']['NetworkSettings']['Networks']['bridge-sc_default']['DriverOpts'])



class ProbeAndReplayTests(unittest.TestCase):
    def test_all_raw_and_sanitized_profile_blockers_match(self):
        from test_upgrade_eth_node import LauncherTests
        launcher=LauncherTests.module(self);m=module()
        variants=[lambda c,i:None,
            lambda c,i:(i['Config'].pop('Domainname',None),c['Config'].update(Domainname='')),
            lambda c,i:i['Config'].update(ArgsEscaped=True),
            lambda c,i:c['HostConfig'].update(Memory=1024,MemorySwappiness=-1,ShmSize=134217728,IpcMode='shareable',PidsLimit=256),
            lambda c,i:c['Config']['Env'].append('API_KEY=PRIVATE_VALUE'),
            lambda c,i:c['NetworkSettings']['Networks']['bridge-sc_default'].update(IPAMConfig={'IPv4Address':'192.0.2.3'}),
            lambda c,i:c['HostConfig'].update(SecurityOpt=['PRIVATE_PATH'],UnexpectedField={'secret':'PRIVATE_VALUE'})]
        for change in variants:
            c,i=fixture();change(c,i);raw=[];launcher.make_override(c,i,Path('/home/ubuntu/Bridge-SC'),issues=raw)
            snap=m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC'));replay=[]
            launcher.make_override(snap['container'],snap['image'],Path(snap['repo']),issues=replay)
            self.assertEqual(raw,replay)

    def test_offline_replay_never_runs_docker_or_captured_commands(self):
        from test_upgrade_eth_node import LauncherTests
        launcher=LauncherTests.module(self);m=module();c,i=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'must-not-exist'
            c['Config']['Cmd']=['sh','-c','touch '+str(marker)]
            root=Path(tmp);root.chmod(0o700)
            m.write_bundle({'schema':1,'deployment':m.sanitize_deployment(c,i,Path('/home/ubuntu/Bridge-SC'))},root)
            with patch.object(launcher.Runner,'run',side_effect=AssertionError('Offline replay must not access commands')), \
                 patch.object(launcher,'require_operator',side_effect=AssertionError('Replay is offline')), \
                 patch.object(launcher.os,'execv',side_effect=AssertionError('Never execute captured values')), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                status=launcher.main(['--replay-environment',str(root/'environment.json')])
            self.assertEqual(status,1);self.assertFalse(marker.exists());self.assertIn('startup',out.getvalue())

    def test_running_node_probe_uses_only_owned_dummy_rpc_and_never_reads_key(self):
        import http.server,threading,subprocess,shutil
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        m=module();calls=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                req=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.extend(x['method'] for x in req)
                chain='0x1' if self.path.startswith('/ethereum') else '0x1e'
                def result(x):
                    if x['method']=='eth_chainId':return chain
                    if x['method']=='eth_blockNumber':return '0x123'
                    selector=x['params'][0]['data']
                    if selector in ('0x9eab5253','0xa0e67e2b'):
                        return '0x'+format(32,'064x')+format(3,'064x')+''.join('0'*24+v*40 for v in ('1','2','3'))
                    if selector=='0xdc8452cd':return '0x'+format(3,'064x')
                    return '0x'+'0'*24+('f'*40 if selector=='0xea217091' else 'c'*40)
                body=json.dumps([{'id':x['id'],'jsonrpc':'2.0','result':result(x)} for x in req]).encode()
                self.send_response(200);self.end_headers();self.wfile.write(body)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                app=Path(tmp);(app/'config').mkdir();(app/'src/lib').mkdir(parents=True);(app/'src/vendors').mkdir()
                for label,name in [('ethereum','mainnet.json'),('rootstock','rskmainnet.json')]:
                    (app/'config'/name).write_text(json.dumps({'host':'http://user:PRIVATE_AUTH@127.0.0.1:'+str(server.server_address[1])+'/'+label+'?apikey=PRIVATE_QUERY','bridge':'0x'+'b'*40,'federation':'0x'+'f'*40,'multiSig':'0x'+'c'*40}))
                (app/'config/federator.key').write_text('PRIVATE_SIGNING_KEY')
                for name in ('GasPriceAvg','GasPriceFetcher','GasServices','TransactionSender'):(app/'src/lib'/(name+'.js')).write_text('// owned fixture')
                (app/'src/vendors/RSKKeyedAuth.js').write_text('// owned fixture')
                code="const origOpen=require('fs').openSync;require('fs').openSync=function(p,...rest){if(String(p).endsWith('.key'))throw Error('KEY_READ_FORBIDDEN');return origOpen.call(this,p,...rest);};\n"+m.NODE_PROBE.replace('/app/federator',str(app))
                result=subprocess.run([node,'-e',code],cwd=app,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn('PRIVATE_',result.stdout)
                data=json.loads(result.stdout);self.assertEqual(data['rpc']['ethereum']['chainId'],'0x1');self.assertEqual(data['rpc']['rootstock']['chainId'],'0x1e')
                self.assertEqual(sorted(calls),['eth_blockNumber','eth_blockNumber']+['eth_call']*12+['eth_chainId','eth_chainId'])
                self.assertEqual(data['rpc']['ethereum']['members'],['0x'+v*40 for v in ('1','2','3')])
                self.assertEqual(data['rpc']['rootstock']['required'],3)
                self.assertEqual(data['rpc']['ethereum']['administrativeOwners'],['0x'+v*40 for v in ('1','2','3')])
        finally:server.shutdown();server.server_close();thread.join(timeout=3)

    def test_node_probe_rejects_fifo_without_leaving_a_blocked_process(self):
        import subprocess,shutil
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        m=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir();os.mkfifo(root/'config/mainnet.json')
            result=subprocess.run([node,'-e',m.NODE_PROBE.replace('/app/federator',str(root))],capture_output=True,text=True,timeout=2)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['rpc']['ethereum']['status'],'UNAVAILABLE')

    def test_collector_clears_node_preload_before_real_probe_execution(self):
        import subprocess,shutil
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        m=module();c,i=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);marker=root/'preload-ran';coverage=root/'coverage';hook=root/'hook.cjs'
            hook.write_text("require('fs').writeFileSync("+json.dumps(str(marker))+",'bad');")
            class Runner:
                def run(self,args,timeout=20):
                    if '-e' not in args:raise RuntimeError()
                    env={**os.environ,'NODE_OPTIONS':'--require='+str(hook),'NODE_V8_COVERAGE':str(coverage)}
                    for index,arg in enumerate(args):
                        if arg=='--env':
                            key,val=args[index+1].split('=',1);env[key]=val
                    code=args[-1].replace('/app/federator',str(root))
                    result=subprocess.run([node,'-e',code],env=env,cwd=root,text=True,capture_output=True,timeout=10)
                    if result.returncode:raise RuntimeError()
                    return result.stdout
            report=m.collect(root,Runner(),'fed_2',c,i)
            self.assertEqual(report['application_probe']['status'],'OBSERVED')
            self.assertFalse(marker.exists(),'Inherited preload code must not execute')
            self.assertFalse(coverage.exists(),'Read-only helper must not write inherited V8 coverage output')

    @unittest.skipUnless(importlib.util.find_spec('yaml'),'Agent probe requires PyYAML, exercised in Python3.9 suite')
    def test_agent_probe_reads_real_yaml_and_registry_without_exporting_credentials(self):
        import subprocess,sys,yaml
        m=module();cid='a'*64
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cfg').mkdir();(root/'run').mkdir();(root/'bin').mkdir()
            (root/'cfg/datadog.yaml').write_text(json.dumps({'api_key':'PRIVATE_CONFIG_KEY','logs_enabled':True,'logs_config':{'run_path':str(root/'run')}}))
            (root/'run/registry.json').write_text(json.dumps({'Version':2,'Registry':{'file:/var/lib/docker/containers/'+cid+'/'+cid+'-json.log':{'Offset':'1234','TailingMode':''},'PRIVATE_REGISTRY_SOURCE':{'secret':'PRIVATE_REGISTRY_KEY'}}}))
            agent=root/'bin/agent';agent.write_text('#!/bin/sh\nprintf "Agent 7.33.1 - PRIVATE_VERSION_TRAILER\\n"\n');agent.chmod(0o700)
            code=m.AGENT_PROBE.replace('/etc/datadog-agent/datadog.yaml',str(root/'cfg/datadog.yaml')).replace('/opt/datadog-agent/run',str(root/'run')).replace('/var/log/datadog/bridge-log-state',str(root/'run'))
            env={**os.environ,'PATH':str(root/'bin')+os.pathsep+os.environ.get('PATH',''),'DD_API_KEY':'PRIVATE_ENV_KEY'}
            env.pop('DD_LOGS_CONFIG_RUN_PATH',None);env.pop('DD_LOGS_ENABLED',None)
            trap=root/'trap';trap.mkdir();marker=root/'sitecustomize-ran'
            (trap/'sitecustomize.py').write_text('from pathlib import Path;Path('+repr(str(marker))+').write_text("bad")')
            env['PYTHONPATH']=str(trap)
            code='import sys;sys.path.append('+repr(str(Path(yaml.__file__).resolve().parent.parent))+')\n'+code
            result=subprocess.run([sys.executable,'-I','-B','-c',code,cid],env=env,text=True,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn('PRIVATE_',result.stdout)
            data=json.loads(result.stdout);self.assertEqual(data['version'],'7.33.1');self.assertTrue(data['api_key_present'])
            self.assertEqual(data['current_sources'],[{'kind':'file','offset':'1234','tailing_mode':''}])
            self.assertFalse(marker.exists(),'Python isolation must ignore inherited sitecustomize')

if __name__=='__main__':unittest.main()

