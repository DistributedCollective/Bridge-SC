import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import federator_agent_replacement as m
except ImportError:
    m=None


class AgentReplacementTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(m,'clean Agent replacement is not implemented')

    def test_credentials_and_tags_are_reused_but_old_registry_settings_are_replaced(self):
        old={'Config':{'Env':['DD_API_KEY='+'a'*32,'DD_TAGS=FED_ID:original-host',
            'DD_LOGS_CONFIG_RUN_PATH=/old/private/path','DD_CONFIG_FILE=/etc/datadog-agent/datadog.yaml','LD_PRELOAD=old.so']}}
        value=m.environment(old)
        self.assertEqual(value['DD_API_KEY'],'a'*32)
        self.assertEqual(value['DD_TAGS'],'FED_ID:original-host')
        self.assertEqual(value['DD_LOGS_CONFIG_RUN_PATH'],'/var/log/datadog/bridge-log-state')
        self.assertNotIn('LD_PRELOAD',value);self.assertNotIn('DD_CONFIG_FILE',value)
        self.assertEqual(value['DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE'],'true')

    def test_only_a_missing_key_requests_hidden_input_and_newlines_are_refused(self):
        requests=[]
        value=m.environment({'Config':{'Env':[]}},lambda:requests.append(True) or 'b'*32)
        self.assertEqual(requests,[True]);self.assertEqual(value['DD_API_KEY'],'b'*32)
        with self.assertRaises(m.r.RepairError):
            m.environment({'Config':{'Env':['DD_API_KEY='+'a'*32,'DD_TAGS=x\nDD_API_KEY=private']}})

    def test_fresh_registry_is_built_from_explicit_file_cutoffs_without_old_registry(self):
        cid='a'*64;path='/var/lib/docker/containers/'+cid+'/'+cid+'-json.log'
        result=m.registry({path:{'offset':123,'last_record_utc':'2026-10-19T14:00:00Z'}},'2026-10-19T14:01:00Z')
        self.assertEqual(result['Version'],2)
        self.assertEqual(result['Registry']['file:'+path]['Offset'],'123')
        self.assertEqual(result['Registry']['file:'+path]['TailingMode'],'')
        for bad in (-1,True,2**63):
            with self.subTest(bad=bad),self.assertRaises(m.r.RepairError):
                m.registry({path:{'offset':bad}},'2026-10-19T14:01:00Z')

    def test_custom_log_mount_is_carried_into_the_fresh_agent(self):
        self.assertTrue(hasattr(m,'extra_mounts'),'integration dependency mount preservation is missing')
        old={'Mounts':[{'Type':'bind','Source':'/srv/monitoring','Destination':'/logs','RW':False},
                       {'Type':'volume','Name':'old-run-state','Destination':'/var/run/s6','RW':True},
                       {'Type':'bind','Source':'/srv/private-ca.pem','Destination':'/etc/datadog-agent/certs/private-ca.pem','RW':False}]} 
        values=m.extra_mounts(old,'/var/lib/docker/containers')
        self.assertIn('type=bind,source=/srv/monitoring,target=/logs,readonly',values)
        self.assertFalse(any('old-run-state' in v for v in values))
        self.assertIn('type=bind,source=/srv/private-ca.pem,target=/etc/datadog-agent/certs/private-ca.pem,readonly',values)

    def test_container_identity_dns_aliases_and_custom_labels_are_preserved(self):
        self.assertTrue(hasattr(m,'runtime_settings'),'Agent container settings preservation is missing')
        old={'Id':'b'*64,'Config':{'Hostname':'logging-node','Domainname':'example.internal','Labels':{'deployment.owner':'node-opaque','com.docker.compose.service':'datadog'}},
             'HostConfig':{'NetworkMode':'bridge-sc_default','Dns':['10.0.0.2'],'DnsSearch':['example.internal'],'DnsOptions':['ndots:1'],'ExtraHosts':['intake.example:10.0.0.5']},
             'NetworkSettings':{'Networks':{'bridge-sc_default':{'Aliases':['datadog','b'*12],'IPAMConfig':None,'DriverOpts':None}}}}
        argv,labels=m.runtime_settings(old)
        for flag,value in [('--hostname','logging-node'),('--domainname','example.internal'),('--dns','10.0.0.2'),('--dns-search','example.internal'),('--dns-option','ndots:1'),('--add-host','intake.example:10.0.0.5'),('--network-alias','datadog')]:
            self.assertEqual(argv[argv.index(flag)+1],value)
        self.assertEqual(labels['com.docker.compose.service'],'datadog')
        self.assertEqual(labels['deployment.owner'],'node-opaque')

    def test_live_provider_and_custom_config_paths_refuse_before_replacement(self):
        for row in ('DD_CONFIG_PROVIDERS=["custom"]','DD_EXTRA_CONFIG_PROVIDERS=remote','DD_CONF_PATH=/custom/agent','DD_CONFD_PATH=/custom/integrations'):
            with self.subTest(row=row),self.assertRaises(m.r.RepairError):
                m.environment({'Config':{'Env':['DD_API_KEY='+'a'*32,row]}})

    def test_secondary_networks_refuse_instead_of_being_silently_dropped(self):
        self.assertTrue(hasattr(m,'runtime_settings'),'Agent container settings preservation is missing')
        with self.assertRaises(m.r.RepairError):
            m.runtime_settings({'Config':{},'HostConfig':{'NetworkMode':'primary'},'NetworkSettings':{'Networks':{'primary':{},'second':{}}}})

    def test_generated_cutoff_reader_executes_on_real_nonempty_json_log(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            cid='a'*64;root=Path(tmp)/'containers';folder=root/cid;folder.mkdir(parents=True)
            path=folder/(cid+'-json.log')
            body=b'{"time":"2026-10-19T14:00:00Z","log":"historical\\n","stream":"stdout"}\n'
            path.write_bytes(body)
            source={'id':cid,'log_path':str(path),'log_config':{'Type':'json-file'}}
            class Docker:
                def call(self,args):return (cid+'\n').encode()
                def inspect(self,name):return source
                def helper(self,image,code,mounts,**kwargs):
                    return subprocess.check_output([sys.executable,'-c',code])
            result=m.log_cutoffs(Docker(),'fixture-image',source)
            self.assertEqual(result[str(path)]['offset'],len(body))
            self.assertEqual(path.read_bytes(),body)

    def test_preserved_file_settings_use_current_start_without_changing_keys_or_tags(self):
        value={'api_key':'a'*32,'site':'datadoghq.eu','tags':['keep:tag'],'logs':[{'type':'file','path':'/logs/old.log','start_position':'forceBeginning'}]}
        self.assertTrue(hasattr(m,'fresh_log_positions'),'fresh file-start configuration is missing')
        result=m.fresh_log_positions(value)
        self.assertEqual(result['logs'][0]['start_position'],'end')
        self.assertEqual(result['api_key'],'a'*32);self.assertEqual(result['site'],'datadoghq.eu')
        self.assertEqual(result['tags'],['keep:tag'])
        self.assertEqual(value['logs'][0]['start_position'],'forceBeginning')

    def test_full_replacement_restores_yaml_and_integrations_before_start(self):
        import copy
        from unittest.mock import patch
        from test_dd_agent_apply_retry import archive
        config=b'{}';old_image='sha256:'+hashlib.sha256(config).hexdigest()
        source={'id':'a'*64,'image':'sha256:'+'d'*64,'state':{'Running':True,'Paused':False,'StartedAt':'2026-10-19T14:00:00Z'},
                'mounts':[],'log_path':'/var/lib/docker/containers/'+'a'*64+'/'+'a'*64+'-json.log','log_config':{'Type':'json-file'}}
        original={'id':'b'*64,'image':old_image,'state':{'Running':False,'Paused':False,'Status':'exited','StartedAt':'2026-10-19T13:00:00Z'},'mounts':[],'env_fingerprint':'old'}
        old={'Id':'b'*64,'Image':old_image,'Config':{'Env':['DD_API_KEY='+'a'*32],'Hostname':'preserved-host','Labels':{'deployment.owner':'opaque'}},'HostConfig':{'NetworkMode':'bridge','Dns':['10.0.0.2'],'RestartPolicy':{'Name':'always'}}}
        main=json.dumps({'api_key':'a'*32,'site':'datadoghq.eu','hostname':'fixture-node','tags':['host:fixture']}).encode()
        integrations=archive('conf.d/custom.d/conf.yaml',b'logs: []')
        class Docker:
            def __init__(self):self.agent=copy.deepcopy(original);self.main=None;self.integrations=None;self.started=False;self.restart_disabled=False
            def inspect(self,name,agent=False):return copy.deepcopy(self.agent if agent else source)
            def call(self,args,**kwargs):
                if args[:2]==['image','inspect']:
                    return json.dumps([{'Id':m.IMAGE_ID,'Os':'linux','Architecture':'amd64'}] if args[2]==m.IMAGE else [{'Id':old_image,'Size':1}]).encode()
                if args[:2]==['image','save']:
                    with tarfile.open(args[3],'w') as out:
                        for name,data in [('manifest.json',json.dumps([{'Config':'cfg.json','Layers':['layer.tar']}]).encode()),('cfg.json',config),('layer.tar',b'x')]:
                            row=tarfile.TarInfo(name);row.size=len(data);out.addfile(row,io.BytesIO(data))
                if args[:2]==['update','--restart=no']:self.restart_disabled=True
                if args[0]=='create':
                    self.create_args=args
                    self.labels=Path(args[args.index('--label-file')+1]).read_text()
                    self.agent.update(id='e'*64,image=m.IMAGE_ID);return ('e'*64).encode()
                if args[0]=='cp':
                    if args[-1]=='-':return archive('datadog.yaml',link=m.r.DOCKER_CONFIG)
                    path=Path(args[1])
                    if path.is_dir():self.registry=(path/'registry.json').read_bytes()
                    else:self.main=path.read_bytes()
                if args[0]=='start':
                    if self.main!=main or self.integrations!=integrations:raise AssertionError('Configuration was lost before startup')
                    self.started=True;self.agent['state']['Running']=True
                return b''
            def copy_config_archive(self,cid,path):self.integrations=path.read_bytes()
            def copy_out(self,cid,path,destination):return self.registry
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp).resolve();(output/'config.private.yaml').write_bytes(main);(output/'config.private.yaml').chmod(0o600)
            (output/'integrations.private.tar').write_bytes(integrations);(output/'integrations.private.tar').chmod(0o600)
            docker=Docker()
            with patch.object(m,'log_cutoffs',return_value={source['log_path']:{'offset':500}}), \
                 patch.object(m,'prepared_configuration',return_value=(output/'config.private.yaml',output/'integrations.private.tar',0)):
                manifest,new=m.replace(docker,output,old)
            self.assertTrue(docker.started)
            self.assertEqual(docker.create_args[docker.create_args.index('--hostname')+1],'preserved-host')
            self.assertEqual(docker.create_args[docker.create_args.index('--dns')+1],'10.0.0.2')
            self.assertEqual(docker.labels,'deployment.owner=opaque\n')
            self.assertTrue(docker.restart_disabled,'retained old Agent must not restart after daemon reboot')
            self.assertEqual(json.loads(docker.main)['site'],'datadoghq.eu')
            self.assertEqual(docker.integrations,integrations)
            self.assertEqual(manifest['source_cutoff'],500)

    def test_auto_removal_refuses_before_stopping_the_original_agent(self):
        old={'Id':'b'*64,'Image':'sha256:'+'c'*64,'HostConfig':{'AutoRemove':True}}
        class Docker:
            def inspect(self,name,agent=False):
                return {'id':'b'*64,'image':old['Image'],'state':{'Running':True,'Paused':False,'Status':'running'},'mounts':[]}
            def call(self,*a,**kw):raise AssertionError('No Agent mutation or image operation is allowed')
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(m.r.RepairError):
            m.replace(Docker(),Path(tmp).resolve(),old)

    def test_integration_archive_cannot_escape_the_new_agent_config_tree(self):
        from test_dd_agent_apply_retry import archive
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'integrations.tar'
            for data in (archive('../escape',b'private'),archive('conf.d/link',link='/etc/private'),archive('conf.d/self',link='self')):
                path.write_bytes(data);path.chmod(0o600)
                with patch.object(m.r.subprocess,'run',side_effect=AssertionError('Unsafe archive must not reach Docker')),self.assertRaises(m.r.RepairError):
                    m.r.Docker().copy_config_archive('e'*64,path)

    def test_generated_yaml_guard_refuses_live_providers_and_noncanonical_integrations(self):
        import subprocess
        from test_dd_agent_apply_retry import archive
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp).resolve();work=output/'work';work.mkdir()
            (output/'integrations.private.tar').write_bytes(archive('conf.d/custom.yaml',b'{}'))
            class Docker:
                def helper(self,image,code,mounts,**kwargs):
                    # JSON fixtures are a YAML subset; execute the actual generated guard.
                    for source,target in mounts:code=code.replace(repr(target),repr(source))
                    shim="import sys,types,json;sys.modules['yaml']=types.SimpleNamespace(safe_load=json.loads,safe_dump=lambda v,**kw:json.dumps(v))\n"
                    return subprocess.check_output([sys.executable,'-c',shim+code])
            for config in ({'config_providers':[{'name':'remote'}]},{'extra_config_providers':['remote']},{'confd_path':'/custom/integrations'}):
                (output/'config.private.yaml').write_text(json.dumps(config))
                with self.subTest(config=config),self.assertRaises(m.r.RepairError):m.prepared_configuration(Docker(),output,work)
                self.assertFalse((work/'active-config.private.yaml').exists())

    def test_two_link_cycle_is_rejected_before_docker_extraction(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'integrations.tar'
            with tarfile.open(path,'w') as archive:
                for name,target in [('conf.d/a','b'),('conf.d/b','a')]:
                    row=tarfile.TarInfo(name);row.type=tarfile.SYMTYPE;row.linkname=target;archive.addfile(row)
            path.chmod(0o600)
            with patch.object(m.r.subprocess,'run',side_effect=AssertionError('Cyclic archive must not reach Docker')),self.assertRaises(m.r.RepairError):
                m.r.Docker().copy_config_archive('e'*64,path)

    def test_unsupported_provider_refuses_before_image_or_agent_operations(self):
        old={'Id':'b'*64,'Image':'sha256:'+'c'*64,'Config':{'Env':['DD_CONFIG_PROVIDERS=remote']}}
        class Docker:
            def inspect(self,name,agent=False):
                return {'id':'b'*64,'image':old['Image'],'state':{'Running':True,'Paused':False,'Status':'running'},'mounts':[]}
            def call(self,*a,**kw):raise AssertionError('No Agent mutation or image operation is allowed')
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(m.r.RepairError):
            m.replace(Docker(),Path(tmp).resolve(),old)

    def test_image_archive_must_match_original_config_and_contain_layers(self):
        config=b'{"owned":"fixture"}';image='sha256:'+hashlib.sha256(config).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'image.tar'
            with tarfile.open(path,'w') as archive:
                for name,data in [('manifest.json',json.dumps([{'Config':'cfg.json','Layers':['layer.tar']}]).encode()),('cfg.json',config),('layer.tar',b'layer')]:
                    row=tarfile.TarInfo(name);row.size=len(data);archive.addfile(row,io.BytesIO(data))
            m.verify_archive(path,image)
            with self.assertRaises(m.r.RepairError):m.verify_archive(path,'sha256:'+'0'*64)

if __name__=='__main__':unittest.main()
