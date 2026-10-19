import copy
import importlib.util
import io
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import pty
import select
import signal
import time
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]


def fixture():
    image_id = 'sha256:eb153b412d54517818953f45990a8a5c8cf552d64e881410134a6c406a0c785c'
    config = {'User': 'node', 'Entrypoint': ['docker-entrypoint.sh'], 'Cmd': ['npm', 'start'],
              'WorkingDir': '/app/federator', 'Env': ['PATH=/usr/bin', 'TZ=UTC'],
              'Hostname': 'a' * 12, 'Domainname': '', 'Labels': {
                  'com.docker.compose.project': 'bridge-sc', 'com.docker.compose.service': 'federation'}}
    container = {'Id': 'a' * 64, 'Name': '/bridge-sc_federation_1', 'Image': image_id,
        'State': {'Status': 'running', 'StartedAt': '2026-10-17T00:00:00Z'}, 'Config': config,
        'HostConfig': {'PortBindings': {'30303/tcp': [{'HostIp': '', 'HostPort': '4444'}]},
            'NetworkMode': 'bridge-sc_default', 'RestartPolicy': {'Name': '', 'MaximumRetryCount': 0},
            'ShmSize': 67108864, 'Runtime': 'runc', 'IpcMode': 'private',
            'LogConfig': {'Type': 'json-file', 'Config': {}}},
        'NetworkSettings': {'Networks': {'bridge-sc_default': {}}},
        'Mounts': [{'Type': 'bind', 'Source': '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK',
                    'Destination': '/app/federator/config', 'RW': True},
                   {'Type': 'bind', 'Source': '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK/db',
                    'Destination': '/app/federator/db', 'RW': True}]}
    image = {'Id': image_id, 'Os': 'linux', 'Architecture': 'amd64', 'Config': copy.deepcopy(config)}
    return container, image


class LauncherTests(unittest.TestCase):
    def module(self):
        path = TOOLS / 'upgrade_eth_node.py'
        self.assertTrue(path.exists(), 'single-file automatic ETH upgrade launcher missing')
        spec = importlib.util.spec_from_file_location('upgrade_eth_node', path)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_supported_host_generates_complete_eth_only_override(self):
        m = self.module();container, image = fixture()
        result = m.make_override(container, image, Path('/home/ubuntu/Bridge-SC'))
        self.assertEqual(list(result['services']), ['federation'])
        service = result['services']['federation']
        self.assertEqual(service['image'], m.APP_IMAGE)
        self.assertEqual(service['environment'], {'TZ': 'UTC'})
        self.assertEqual(service['logging']['options'], {'max-size': '20m', 'max-file': '5'})
        self.assertEqual(service['volumes'][0]['source'], container['Mounts'][0]['Source'])
        self.assertNotIn('DATADOG', json.dumps(result))

    def test_existing_shareable_ipc_is_preserved_without_host_namespace_access(self):
        m=self.module();c,i=fixture()
        c['HostConfig']['IpcMode']='shareable'
        result=m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))
        service=result['services']['federation']
        self.assertEqual(service['ipc'],'shareable')
        self.assertNotIn('privileged',service)
        for unsafe in ('host','container:unrelated','service:unrelated'):
            c['HostConfig']['IpcMode']=unsafe
            with self.subTest(ipc=unsafe),self.assertRaises(m.LaunchError):
                m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))

    def test_private_ipc_is_explicit_in_replacement_plan(self):
        m=self.module();c,i=fixture()
        self.assertEqual(m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))['services']['federation']['ipc'],'private')

    def test_stopped_or_paused_agent_is_a_reported_blocker_even_if_inspect_succeeded(self):
        import types
        m=self.module();c,i=fixture()
        for state in ({'Status':'exited','Running':False,'Paused':False,'ExitCode':255},
                      {'Status':'running','Running':True,'Paused':True}):
            report={'agent':{'status':'OBSERVED','deployment':{'State':state},'collection':None},
                    'configuration':{'config_status':'OBSERVED'},'docker':{'compose_version':'2.40.3'}}
            component=types.SimpleNamespace(collect=lambda *a,**kw:copy.deepcopy(report))
            with self.subTest(state=state),patch.object(m,'environment_component',return_value=component):
                result=m.capture_snapshot(Path('/home/ubuntu/Bridge-SC'),None,'fed_2',c,i)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertTrue(any(x['status']=='BLOCKER' and 'Datadog Agent is not running' in x['summary'] for x in result['checks']))
            self.assertTrue(any(x['status']=='UNKNOWN' and 'checkpoint' in x['summary'] for x in result['checks']))

    def test_running_agent_does_not_gain_stopped_agent_blocker(self):
        import types
        m=self.module();c,i=fixture()
        report={'agent':{'status':'OBSERVED','deployment':{'State':{'Status':'running','Running':True,'Paused':False}},
                         'collection':{'version':'7.33.1','api_key_present':True,'logs_enabled':True,'registry_schema':2}},
                'configuration':{'config_status':'OBSERVED'},'docker':{'compose_version':'2.40.3'}}
        component=types.SimpleNamespace(collect=lambda *a,**kw:copy.deepcopy(report))
        with patch.object(m,'environment_component',return_value=component):
            result=m.capture_snapshot(Path('/home/ubuntu/Bridge-SC'),None,'fed_3',c,i)
        self.assertFalse(any(x['status']=='BLOCKER' for x in result['checks']))

    def test_incompatible_host_stops_without_exporting_private_environment(self):
        m = self.module()
        variants = [('environment', lambda c: c['Config']['Env'].append('PRIVATE_PROVIDER_KEY=DUMMY_PRIVATE')),
            ('startup', lambda c: c['Config'].update(Cmd=['sh', '-c', 'echo DUMMY_PRIVATE'])),
            ('mount', lambda c: c['Mounts'].append({'Type': 'bind', 'Source': '/private', 'Destination': '/app/private', 'RW': True})),
            ('port', lambda c: c['HostConfig']['PortBindings']['30303/tcp'][0].update(HostPort='5555')),
            ('network', lambda c: c['HostConfig'].update(NetworkMode='host')),
            ('limits', lambda c: c['HostConfig'].update(Memory=1024)),
            ('restart', lambda c: c['HostConfig']['RestartPolicy'].update(Name='always')),
            ('healthcheck', lambda c: c['Config'].update(Healthcheck={'Test':['CMD','true']})),
            ('staticIP', lambda c: c['NetworkSettings']['Networks']['bridge-sc_default'].update(IPAMConfig={'IPv4Address':'10.1.2.3'})),
            ('disklimits', lambda c: c['HostConfig'].update(BlkioDeviceWriteBps=[{'Path':'/dev/x','Rate':1}])),
            ('loglabels', lambda c: c['HostConfig']['LogConfig'].update(Config={'labels':'custom'})),
            ('newHostField', lambda c: c['HostConfig'].update(UnexpectedNonempty='custom'))]
        for label, mutate in variants:
            with self.subTest(label=label):
                c, i = fixture();mutate(c)
                with self.assertRaises(m.LaunchError) as caught:
                    m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))
                self.assertNotIn('DUMMY_PRIVATE', str(caught.exception))
                self.assertIn('existing services', str(caught.exception))

    def test_linux_legacy_argsescaped_metadata_does_not_block_matching_runtime(self):
        # The pinned public Linux image has ArgsEscaped=true; Docker omits it on containers.
        # This flag affects Windows command-line interpretation, not our pinned Linux runtime.
        m = self.module()
        for observed in (None, False, True):
            with self.subTest(container_argsescaped=observed):
                c, i = fixture();i['Config']['ArgsEscaped'] = True
                if observed is not None:c['Config']['ArgsEscaped'] = observed
                plan = m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))
                self.assertEqual(plan['services']['federation']['image'], m.APP_IMAGE)
        for invalid in ('true', 1, {}, []):
            c, i = fixture();c['Config']['ArgsEscaped'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(m.LaunchError):
                m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))
        c, i = fixture();i['Config']['ArgsEscaped'] = True;c['Config']['Cmd'] = ['other-command']
        with self.assertRaises(m.LaunchError):m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))
        c, i = fixture();i['Config']['ArgsEscaped'] = True;i['Os'] = 'windows'
        with self.assertRaises(m.LaunchError):m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))

    def test_unknown_config_refusal_names_field_without_values(self):
        m = self.module();c, i = fixture()
        c['Config']['Healthcheck'] = {'Test': ['CMD', 'DUMMY_PRIVATE_VALUE']}
        with self.assertRaises(m.LaunchError) as caught:
            m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))
        self.assertIn('Healthcheck', str(caught.exception))
        self.assertNotIn('DUMMY_PRIVATE_VALUE', str(caught.exception))
        c, i = fixture();c['Config']['DUMMY_PRIVATE_FIELD=secret'] = 'DUMMY_PRIVATE_VALUE'
        with self.assertRaises(m.LaunchError) as caught:
            m.make_override(c, i, Path('/home/ubuntu/Bridge-SC'))
        self.assertNotIn('DUMMY_PRIVATE', str(caught.exception))

    def test_deployment_audit_reports_all_independent_blockers_together(self):
        m=self.module();c,i=fixture()
        c['Config']['Env'].append('SECRET=PRIVATE_VALUE')
        c['HostConfig'].update(Memory=1024,IpcMode='host')
        c['NetworkSettings']['Networks']['bridge-sc_default']['IPAMConfig']={'IPv4Address':'192.0.2.3'}
        issues=[]
        self.assertIsNone(m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'),issues=issues))
        joined='\n'.join(issues)
        for name in ('environment','addressing','Memory','IpcMode'):self.assertIn(name,joined)
        self.assertNotIn('PRIVATE_VALUE',joined)
        with self.assertRaises(m.LaunchError) as caught:m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))
        for name in ('environment','addressing','Memory','IpcMode'):self.assertIn(name,str(caught.exception))

    def test_changed_process_is_not_handed_to_upgrader(self):
        m = self.module();c, _ = fixture()
        m.same_process(c, copy.deepcopy(c))
        for field in ('Id', 'Image'):
            other = copy.deepcopy(c);other[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(m.LaunchError):m.same_process(c, other)
        other = copy.deepcopy(c);other['State']['StartedAt'] = '2026-10-17T00:01:00Z'
        with self.assertRaises(m.LaunchError):m.same_process(c, other)

    def test_mount_order_only_does_not_invalidate_the_same_process(self):
        m=self.module();c,i=fixture();other=copy.deepcopy(c);other['Mounts'].reverse()
        m.same_process(c,other)
        other['Mounts'][0]['RW']=False
        with self.assertRaises(m.LaunchError):m.same_process(c,other)

    def test_plan_uses_original_approved_bundle_and_manual_key_mode(self):
        m = self.module()
        args = m.upgrade_command(Path('/private/run'), Path('/home/ubuntu/Bridge-SC'), 'fed_1', '0x'+'11'*20, True)
        self.assertEqual(args[0], '/bin/bash')
        self.assertIn('--no-aws-secrets', args)
        self.assertEqual(args[args.index('--revision')+1], 'ba94a39855c97c81345c6dc5c3b835a9ffa7f900')
        self.assertEqual(args[args.index('--override')+1], '/private/run/override.json')
        self.assertEqual(args[args.index('--image')+1], m.APP_IMAGE)
        self.assertNotIn('--no-aws-secrets', m.upgrade_command(Path('/x'),Path('/y'),'fed_2','0x'+'22'*20,False))

    def test_private_packet_refuses_overwrite_and_contains_no_raw_inspection(self):
        m = self.module();c,i=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();packet=m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))
            m.write_private(root/'override.json', json.dumps(packet).encode())
            self.assertEqual((root/'override.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises((m.LaunchError,FileExistsError)):m.write_private(root/'override.json',b'changed')
            self.assertEqual(json.loads((root/'override.json').read_text()),packet)


    def test_standard_docker20_fields_and_automatic_network_aliases_are_supported(self):
        m=self.module();c,i=fixture()
        c['Config'].update(ExposedPorts={'30303/tcp':{}},AttachStdout=True)
        c['HostConfig'].update(Binds=[
            '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK/:/app/federator/config:rw',
            '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK/db:/app/federator/db:rw'],
            CgroupnsMode='host',ConsoleSize=[0,0],Isolation='',VolumeDriver='',
            BlkioDeviceReadBps=None,KernelMemory=0,Annotations={},
            MaskedPaths=['/proc/asound','/proc/acpi','/proc/kcore','/proc/keys','/proc/latency_stats',
                '/proc/timer_list','/proc/timer_stats','/proc/sched_debug','/proc/scsi','/sys/firmware'],
            ReadonlyPaths=['/proc/bus','/proc/fs','/proc/irq','/proc/sys','/proc/sysrq-trigger'])
        c['NetworkSettings']['Networks']['bridge-sc_default']={
            'IPAMConfig':None,'Links':None,'Aliases':['a'*12,'federation'],
            'NetworkID':'b'*64,'EndpointID':'c'*64,'Gateway':'172.18.0.1',
            'IPAddress':'172.18.0.2','IPPrefixLen':16,'MacAddress':'02:42:ac:12:00:02'}
        override=m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))
        self.assertEqual(override['services']['federation']['cgroup'],'host')

    def test_custom_discovery_labels_are_preserved_in_private_override(self):
        m=self.module();c,i=fixture()
        label='com.datadoghq.ad.logs';value='[{"source":"nodejs","service":"bridge-eth-federator"}]'
        c['Config']['Labels'][label]=value
        self.assertEqual(m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))['services']['federation']['labels'][label],value)



class FakeRunner:
    def __init__(self, repo, changed=False, custom=False, compose=True):
        self.repo=repo;self.calls=[];self.inspect_count=0
        self.container,self.image=fixture()
        for mount in self.container['Mounts']:
            mount['Source']=str(repo/'federator-env/mainnet-ETH-RSK')+('/db' if mount['Destination'].endswith('/db') else '')
        if custom:self.container['Config']['Env'].append('KEY=DUMMY_PRIVATE_VALUE')
        self.changed,self.compose=changed,compose
        self.script=b'#!/bin/bash\nexit 0\n'

    def run(self,args,timeout=20):
        self.calls.append(args)
        if args[0]=='git':
            action=args[3]
            if action=='remote':return 'https://github.com/DistributedCollective/Bridge-SC.git\n'
            if action=='show':return self.script.decode()
            if action in ('hash-object','rev-parse'):return 'b'*40+'\n'
            return ''
        action=args[3:]
        if action==['inspect','bridge-sc_federation_1']:
            self.inspect_count+=1;c=copy.deepcopy(self.container)
            if self.changed and self.inspect_count>1:c['State']['StartedAt']='2026-10-17T01:00:00Z'
            return json.dumps([c])
        if action[:2]==['image','inspect']:return json.dumps([self.image])
        if action==['compose','version']:
            if not self.compose:raise self.error('unavailable')
            return 'Docker Compose version v2.40.3'
        raise AssertionError('Unexpected command: '+repr(args))


class LauncherFlowTests(unittest.TestCase):
    module = LauncherTests.module
    def invoke(self,m,root,runner,upgrade=False):
        argv=['--repo',str(root/'repo'),'--operator','fed_1','--expected-signer','0x'+'11'*20,'--no-aws-secrets']
        argv.append('--upgrade' if upgrade else '--prepare-only')
        with patch.object(m,'require_operator'),patch.object(m,'private_base',return_value=root), \
             patch.object(m.sys.stdin,'isatty',return_value=True),patch.object(m.platform,'system',return_value='Linux'), \
             patch.object(m.platform,'machine',return_value='x86_64'),patch.object(m.os,'execv') as execute, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result=m.main(argv,runner)
        return result,execute,output.getvalue()

    def test_collect_only_needs_no_signer_or_custody_and_never_hands_off(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.error=m.LaunchError
            runner.container['HostConfig'].update(Memory=1024,IpcMode='host')
            with patch.object(m,'require_operator'),patch.object(m,'private_base',return_value=root), \
                 patch('builtins.input',side_effect=AssertionError('No secret or identity questions permitted')), \
                 patch.object(m.os,'execv') as execute,contextlib.redirect_stdout(io.StringIO()) as out:
                status=m.main(['--repo',str(root/'repo'),'--collect-only','--operator','fed_2'],runner)
            self.assertEqual(status,0);execute.assert_not_called()
            bundles=list(root.glob('environment.*/federator-environment.zip'))
            self.assertEqual(len(bundles),1)
            self.assertIn('Memory',out.getvalue());self.assertIn('IpcMode',out.getvalue())
            self.assertFalse(any(a[0]=='git' and 'fetch' in a for a in runner.calls))
            self.assertFalse(list(root.glob('auto-eth-upgrade.*/override.json')))

    def test_collect_only_retains_host_packet_if_docker_is_unavailable(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            class Down(FakeRunner):
                def run(self,args,timeout=20):
                    if args[0]=='docker':raise m.LaunchError('Docker unavailable')
                    return super().run(args,timeout)
            runner=Down(root/'repo')
            with patch.object(m,'require_operator'),patch.object(m,'private_base',return_value=root), \
                 patch.object(m.os,'execv') as execute,contextlib.redirect_stdout(io.StringIO()):
                status=m.main(['--repo',str(root/'repo'),'--collect-only','--operator','fed_2'],runner)
            self.assertEqual(status,0);execute.assert_not_called()
            self.assertEqual(len(list(root.glob('environment.*/federator-environment.zip'))),1)

    def test_normal_wizard_saves_all_blockers_before_refusing_and_never_hands_off(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.error=m.LaunchError
            runner.container['HostConfig'].update(Memory=1024,IpcMode='host')
            with self.assertRaises(m.LaunchError):self.invoke(m,root,runner,upgrade=True)
            reports=list(root.glob('environment.*/environment.json'));self.assertEqual(len(reports),1)
            report=json.loads(reports[0].read_text())
            text=json.dumps(report['checks']);self.assertIn('Memory',text);self.assertIn('IpcMode',text)
            self.assertFalse(list(root.glob('auto-eth-upgrade.*/override.json')))

    def test_prepare_checks_locally_and_never_starts_or_stops_a_service(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.error=m.LaunchError
            result,execute,output=self.invoke(m,root,runner)
            self.assertEqual(result,0);execute.assert_not_called()
            self.assertEqual(len(list(root.glob('auto-eth-upgrade.*/override.json'))),1)
            self.assertIn('Preparation only',output)
            for call in runner.calls:
                if call[0]=='docker':self.assertIn(call[3],('inspect','image','compose','version','exec'))

    def test_upgrade_executes_only_the_verified_original_bundle_with_generated_override(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.error=m.LaunchError
            _,execute,output=self.invoke(m,root,runner,upgrade=True)
            execute.assert_called_once()
            executable,args=execute.call_args[0]
            self.assertEqual(executable,'/bin/bash')
            self.assertEqual(Path(args[1]).read_bytes(),runner.script)
            self.assertIn('--no-aws-secrets',args)
            self.assertTrue(Path(args[args.index('--override')+1]).is_file())
            self.assertIn('Host checks passed',output)

    def test_custom_launch_and_restarted_process_do_not_reach_service_mutation(self):
        m=self.module()
        for flags in ({'custom':True},{'changed':True}):
            with self.subTest(flags=flags),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();runner=FakeRunner(root/'repo',**flags);runner.error=m.LaunchError
                with patch.object(m.os,'execv') as execute,self.assertRaises(m.LaunchError) as error:
                    self.invoke(m,root,runner,upgrade=True)
                execute.assert_not_called();self.assertNotIn('DUMMY_PRIVATE_VALUE',str(error.exception))
                self.assertFalse(list(root.glob('auto-eth-upgrade.*/override.json')))

    def test_missing_compose_gives_exact_same_file_install_command_before_fetch_or_stop(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo',compose=False);runner.error=m.LaunchError
            with self.assertRaises(m.LaunchError) as error:self.invoke(m,root,runner,upgrade=True)
            self.assertIn('--install-compose',str(error.exception))
            self.assertIn('Neither service was changed',str(error.exception))
            self.assertFalse(any('fetch' in a for a in runner.calls))

    def test_already_approved_image_is_not_replaced(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.container['Image']=m.APP_IMAGE_ID;runner.image['Id']=m.APP_IMAGE_ID
            _,execute,output=self.invoke(m,root,runner,upgrade=True)
            execute.assert_not_called();self.assertIn('already installed',output)

    def test_compose_installer_checks_digest_and_never_overwrites_existing_plugin(self):
        m=self.module();payload=b'dummy-compose-binary'
        for valid in (False,True):
            with self.subTest(valid=valid),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();response=io.BytesIO(payload)
                with patch.object(m.Path,'home',return_value=root),patch.dict(os.environ,DOCKER_CONFIG=str(root/'.docker')), \
                     patch.object(m.platform,'system',return_value='Linux'), \
                     patch.object(m.platform,'machine',return_value='x86_64'), \
                     patch.object(m.urllib.request,'build_opener') as opener, \
                     patch.object(m,'COMPOSE_SHA256',hashlib.sha256(payload if valid else b'other').hexdigest()), \
                     patch.object(m.Runner,'run',return_value='Docker Compose version v2.40.3'), \
                     contextlib.redirect_stdout(io.StringIO()):
                    opener.return_value.open.return_value=response
                    if valid:m.install_compose()
                    else:
                        with self.assertRaisesRegex(m.LaunchError,'checksum'):m.install_compose()
                    target=root/'.docker/cli-plugins/docker-compose'
                    self.assertEqual(target.exists(),valid)
                    if valid:
                        self.assertEqual(target.stat().st_mode&0o777,0o755)
                        with self.assertRaises(m.LaunchError):m.install_compose()
                        self.assertEqual(target.read_bytes(),payload)
                    self.assertEqual(list(target.parent.glob('.compose-download-*')),[])

    def test_compose_installer_honors_effective_docker_config(self):
        m=self.module();payload=b'fixture-compose';digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();custom=root/'custom-config'
            with patch.object(m.Path,'home',return_value=root),patch.dict(os.environ,DOCKER_CONFIG=str(custom)), \
                 patch.object(m.platform,'system',return_value='Linux'),patch.object(m.platform,'machine',return_value='x86_64'), \
                 patch.object(m.urllib.request,'build_opener') as opener,patch.object(m,'COMPOSE_SHA256',digest), \
                 patch.object(m.Runner,'run',return_value='Docker Compose version v2.40.3'),contextlib.redirect_stdout(io.StringIO()):
                opener.return_value.open.return_value=io.BytesIO(payload);m.install_compose()
            self.assertTrue((custom/'cli-plugins/docker-compose').is_file())
            self.assertFalse((root/'.docker/cli-plugins/docker-compose').exists())

    def test_unloadable_installed_plugin_is_removed_for_safe_retry(self):
        m=self.module();payload=b'fixture-compose';digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            with patch.object(m.Path,'home',return_value=root),patch.dict(os.environ,DOCKER_CONFIG=str(root/'.docker')), \
                 patch.object(m.platform,'system',return_value='Linux'),patch.object(m.platform,'machine',return_value='x86_64'), \
                 patch.object(m.urllib.request,'build_opener') as opener,patch.object(m,'COMPOSE_SHA256',digest), \
                 patch.object(m.Runner,'run',side_effect=m.LaunchError('CLI unavailable')):
                opener.return_value.open.return_value=io.BytesIO(payload)
                with self.assertRaisesRegex(m.LaunchError,'could not load'):m.install_compose()
            self.assertFalse((root/'.docker/cli-plugins/docker-compose').exists())

    def test_installer_failure_preserves_a_concurrently_replaced_plugin(self):
        m=self.module();payload=b'fixture-compose';digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();target=root/'.docker/cli-plugins/docker-compose';link=m.os.link
            def replace_after_link(source,dest,**kwargs):
                link(source,dest,**kwargs)
                Path(dest).unlink();Path(dest).write_bytes(b'other-installation')
            with patch.object(m.Path,'home',return_value=root),patch.dict(os.environ,DOCKER_CONFIG=str(root/'.docker')), \
                 patch.object(m.platform,'system',return_value='Linux'),patch.object(m.platform,'machine',return_value='x86_64'), \
                 patch.object(m.urllib.request,'build_opener') as opener,patch.object(m,'COMPOSE_SHA256',digest), \
                 patch.object(m.Runner,'run',side_effect=m.LaunchError('CLI unavailable')),patch.object(m.os,'link',side_effect=replace_after_link):
                opener.return_value.open.return_value=io.BytesIO(payload)
                with self.assertRaises(m.LaunchError):m.install_compose()
            self.assertTrue(target.exists(),'Another installation must survive failed validation of this attempt')
            self.assertEqual(target.read_bytes(),b'other-installation')

    def test_real_controlling_terminal_survives_exec_to_the_approved_script(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.error=m.LaunchError
            runner.script=b'#!/bin/bash\nread -r -p "APPROVE_UPGRADE" answer\n[[ "$answer" == y ]] || exit 4\nprintf "APPROVED_WITH_TTY\\n"\n'
            pid,master=pty.fork()
            if pid==0:
                # pytest replaces sys.stdin; the forked child must bind its actual PTY.
                sys.stdin = os.fdopen(os.dup(0), 'r')
                sys.stdout = os.fdopen(os.dup(1), 'w', buffering=1)
                sys.stderr = os.fdopen(os.dup(2), 'w', buffering=1)
                try:
                    with patch.object(m,'require_operator'),patch.object(m,'private_base',return_value=root):
                        m.main(['--repo',str(root/'repo'),'--operator','fed_1',
                                '--expected-signer','0x'+'11'*20,'--no-aws-secrets','--upgrade'],runner)
                except BaseException:
                    os._exit(8)
                os._exit(9)
            output=b'';answered=False;finished=False;deadline=time.monotonic()+10
            try:
                while time.monotonic()<deadline:
                    if select.select([master],[],[],.1)[0]:
                        try:chunk=os.read(master,8192)
                        except OSError:break
                        if not chunk:break
                        output+=chunk
                        if b'APPROVE_UPGRADE' in output and not answered:
                            os.write(master,b'y\n');answered=True
                        if b'APPROVED_WITH_TTY' in output:finished=True;break
                self.assertTrue(finished,output.decode(errors='replace'))
                _,status=os.waitpid(pid,0);pid=None
                self.assertEqual(os.waitstatus_to_exitcode(status),0)
            finally:
                os.close(master)
                if pid is not None:
                    try:os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    os.waitpid(pid,0)

    def test_real_wizard_prompts_continue_into_the_same_terminal_without_restarting_checks(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=FakeRunner(root/'repo');runner.error=m.LaunchError
            runner.script=b'#!/bin/bash\nread -r -p "APPROVE_UPGRADE" answer\n[[ "$answer" == y ]] || exit 4\nprintf "APPROVED_WITH_TTY\\n"\n'
            pid,master=pty.fork()
            if pid==0:
                sys.stdin = os.fdopen(os.dup(0), 'r')
                sys.stdout = os.fdopen(os.dup(1), 'w', buffering=1)
                sys.stderr = os.fdopen(os.dup(2), 'w', buffering=1)
                try:
                    with patch.object(m,'require_operator'),patch.object(m,'private_base',return_value=root):
                        m.main(['--repo',str(root/'repo')],runner)
                except BaseException:os._exit(8)
                os._exit(9)
            responses=[(b'Node label',b'fed_1\n'),(b'Existing PUBLIC',('0x'+'11'*20+'\n').encode()),
                       (b'Original signing-key custody',b'manual\n'),(b'Open the approved upgrade now?',b'y\n'),
                       (b'APPROVE_UPGRADE',b'y\n')]
            output=b'';index=0;deadline=time.monotonic()+5;finished=False
            try:
                while time.monotonic()<deadline:
                    if select.select([master],[],[],.1)[0]:
                        try:chunk=os.read(master,8192)
                        except OSError:break
                        if not chunk:break
                        output+=chunk
                        if index<len(responses) and responses[index][0] in output:
                            os.write(master,responses[index][1]);index+=1
                        if b'APPROVED_WITH_TTY' in output:finished=True;break
                self.assertTrue(finished,output.decode(errors='replace'))
                self.assertEqual(index,5)
                _,status=os.waitpid(pid,0);pid=None;self.assertEqual(os.waitstatus_to_exitcode(status),0)
            finally:
                os.close(master)
                if pid is not None:
                    try:os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    os.waitpid(pid,0)


class WizardTests(unittest.TestCase):
    def module(self):
        if not hasattr(self,'loaded_module'):
            self.loaded_module = LauncherTests.module(self)
        return self.loaded_module

    def invoke(self,inputs,extra=(),runner_type=FakeRunner,interactive=True):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();runner=runner_type(root/'repo');runner.error=m.LaunchError
            with patch.object(m,'require_operator'),patch.object(m,'private_base',return_value=root), \
                 patch.object(m.sys.stdin,'isatty',return_value=interactive),patch('builtins.input',side_effect=inputs) as prompt, \
                 patch.object(m.os,'execv') as execute,contextlib.redirect_stdout(io.StringIO()) as output:
                result=m.main(['--repo',str(root/'repo')]+list(extra),runner)
            packets=len(list(root.glob('auto-eth-upgrade.*/override.json')))
            return result,execute,prompt,output.getvalue(),runner.calls,packets

    def test_missing_identity_reprompts_and_continues_without_rerunning_checks(self):
        private_shape='f'*64
        result,execute,prompt,output,calls,_=self.invoke(['fed_99','fed_1',private_shape,'0x'+'11'*20,'manual','y'])
        self.assertEqual(result,0);execute.assert_called_once()
        args=execute.call_args[0][1]
        self.assertIn('--no-aws-secrets',args)
        self.assertEqual(args[args.index('--expected-signer')+1],'0x'+'11'*20)
        self.assertNotIn(private_shape,output)
        self.assertEqual(sum('fetch' in c for c in calls),1)
        self.assertEqual(prompt.call_count,6)
        for number in range(1,5):self.assertIn('['+str(number)+'/4]',output)

    def test_declining_wizard_stops_after_preparation_and_does_not_execute(self):
        result,execute,_,output,calls,packets=self.invoke(['fed_1','0x'+'11'*20,'manual','n'])
        self.assertEqual(result,0);execute.assert_not_called();self.assertEqual(packets,1)
        self.assertIn('No upgrade started',output)
        self.assertFalse(any(c[0]=='docker' and c[3] in ('start','stop','rm','run','pull') for c in calls))

    def test_explicit_preparation_never_asks_to_activate(self):
        result,execute,prompt,output,_,_=self.invoke([],extra=['--prepare-only','--operator','fed_1',
            '--expected-signer','0x'+'11'*20,'--no-aws-secrets'])
        self.assertEqual(result,0);execute.assert_not_called();prompt.assert_not_called()
        self.assertIn('Preparation only',output)

    def test_noninteractive_full_inputs_prepare_without_asking(self):
        result,execute,prompt,_,_,_=self.invoke([],extra=['--operator','fed_1',
            '--expected-signer','0x'+'11'*20,'--no-aws-secrets'],interactive=False)
        self.assertEqual(result,0);execute.assert_not_called();prompt.assert_not_called()

    def test_invalid_custody_and_confirmation_answers_are_reprompted(self):
        _,execute,prompt,_,_,_=self.invoke(['fed_2','0x'+'22'*20,'unknown','aws','maybe','yes'])
        execute.assert_called_once();self.assertNotIn('--no-aws-secrets',execute.call_args[0][1])
        self.assertEqual(prompt.call_count,6)

    def test_default_empty_confirmation_declines(self):
        _,execute,_,output,_,_=self.invoke(['fed_1','0x'+'11'*20,'manual',''])
        execute.assert_not_called();self.assertIn('No upgrade started',output)

    def test_process_change_while_waiting_for_confirmation_blocks_handoff(self):
        class ChangedAfterDecision(FakeRunner):
            def run(self,args,timeout=20):
                result=super().run(args,timeout)
                if args[0]=='docker' and args[3:]==['inspect','bridge-sc_federation_1'] and self.inspect_count==3:
                    value=json.loads(result);value[0]['State']['StartedAt']='2026-10-17T02:00:00Z';return json.dumps(value)
                return result
        m=self.module()
        with self.assertRaises(m.LaunchError):
            self.invoke(['fed_1','0x'+'11'*20,'manual','y'],runner_type=ChangedAfterDecision)

    def test_help_explains_wizard_preparation_and_version_modes(self):
        m=self.module()
        with patch.object(m,'require_operator',side_effect=AssertionError('Help must work without Docker/account')), \
             contextlib.redirect_stdout(io.StringIO()) as output,self.assertRaises(SystemExit) as exit:
            m.main(['--help'])
        self.assertEqual(exit.exception.code,0)
        for word in ('wizard','--prepare-only','--version'):self.assertIn(word,output.getvalue())

    def test_baseline_mismatch_reports_public_image_ids_without_extra_manual_probe(self):
        m=self.module();c,i=fixture();observed='sha256:'+'b'*64;c['Image']=observed;i['Id']=observed
        with self.assertRaises(m.LaunchError) as error:m.make_override(c,i,Path('/home/ubuntu/Bridge-SC'))
        self.assertIn(observed,str(error.exception));self.assertIn(m.BASE_IMAGE_ID,str(error.exception))


if __name__ == '__main__': unittest.main()
