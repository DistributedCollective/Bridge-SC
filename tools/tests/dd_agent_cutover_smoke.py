#!/usr/bin/env python3
import argparse,hashlib,importlib.util,io,json,secrets,subprocess,tarfile,tempfile,time
from pathlib import Path

parser=argparse.ArgumentParser(description='Manual isolated Agent cutoff proof; uses only dummy data and an internal network.')
parser.add_argument('--agent-image',required=True,help='already-local official Agent image ID or immutable digest')
parser.add_argument('--upgrade-integration',action='store_true',help='exercise stopped-Agent upgrade preflight/capture/verify and retained restart')
parser.add_argument('--socket-cursor-fixture',action='store_true',help='start recovery with only the selected legacy Docker socket checkpoint')
parser.add_argument('--node-image',default='node:22-bookworm',help='already-local Node image for disposable fixtures')
parser.add_argument('--evidence-dir',type=Path,required=True,help='private local evidence directory')
args=parser.parse_args()
args.evidence_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
SCRIPT=Path(__file__).resolve().parents[1]/'dd_agent_recovery.py'
spec=importlib.util.spec_from_file_location('ddrepair',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
D=['docker','--host','unix:///var/run/docker.sock']
nonce='fed-dd-smoke-'+secrets.token_hex(4);network=nonce+'-net';volume=nonce+'-state';agent=nonce+'-agent';source=nonce+'-source';sink=nonce+'-sink'
AGENT=args.agent_image;NODE=args.node_image
owned=[];owned_volumes=set();results={'tool_sha256':hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),'lab':nonce,'real_datadog_used':False,'production_data_used':False}

def call(args,check=True):
 if args[0] in ('run','create'):args=[args[0],'--pull=never']+args[1:]
 r=subprocess.run(D+args,text=True,capture_output=True,timeout=45)
 if check and r.returncode:raise RuntimeError('docker '+args[0]+' failed: '+r.stderr[:400])
 return r.stdout.strip()
def wait(predicate,label,seconds=70):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if predicate():return
  time.sleep(2)
 raise RuntimeError('Timed out: '+label)
def got():
 return json.loads(call(['exec',sink,'node','-e','fetch("http://127.0.0.1:8080/received").then(r=>r.text()).then(t=>console.log(t))']))
def reset_sink():call(['exec',sink,'node','-e','fetch("http://127.0.0.1:8080/reset").then(r=>r.text()).then(t=>console.log(t))'])

sink_code=r'''const http=require('http'),zlib=require('zlib');let markers=[];http.createServer((q,s)=>{if(q.url==='/received'){s.end(JSON.stringify(markers));return}if(q.url==='/reset'){markers=[];s.end('ok');return}let chunks=[];q.on('data',d=>chunks.push(d));q.on('end',()=>{let b=Buffer.concat(chunks);try{if(q.headers['content-encoding']==='gzip')b=zlib.gunzipSync(b);if(q.headers['content-encoding']==='deflate')b=zlib.inflateSync(b);if(q.headers['content-encoding']==='zstd')b=zlib.zstdDecompressSync(b)}catch(e){}markers.push(...(b.toString().match(/BRIDGE_LAB_(?:HISTORY|FRESH|RESTART|RECREATE)_[0-9]+/g)||[]));s.setHeader('Content-Type','application/json');s.statusCode=q.url.includes('validate')?200:202;s.end(q.url.includes('validate')?'{}':'{}')})}).listen(8080,'0.0.0.0');'''
source_code="const fs=require('fs');let n=0;for(let i=0;i<300;i++)console.log('BRIDGE_LAB_HISTORY_'+n++);setInterval(()=>console.log(fs.readFileSync('/app/federator/config/phase','utf8').trim()+'_'+n++),200)"

with tempfile.TemporaryDirectory(prefix='dd-agent-cutover-lab-') as td:
 root=Path(td).resolve();cfg=root/'federator-env/mainnet-ETH-RSK';(cfg/'db').mkdir(parents=True);(cfg/'phase').write_text('BRIDGE_LAB_HISTORY');(cfg/'db/keep').write_text('preserve database fixture');(cfg/'keep').write_text('preserve configuration fixture')
 logs_cfg=root/'log-source';logs_cfg.mkdir();original=root/'datadog.json';reg=root/'registry.json'
 try:
  call(['network','create','--internal','--label','bridge-dd-lab='+nonce,network])
  call(['run','-d','--name',sink,'--label','bridge-dd-lab='+nonce,'--network',network,'--network-alias','sink','--log-opt','max-size=1m','--entrypoint','node',NODE,'-e',sink_code]);owned.append(sink)
  call(['run','-d','--name',source,'--label','bridge-dd-lab='+nonce,'--network','none','--log-driver','json-file','--log-opt','max-size=2m','--log-opt','max-file=2','--mount','type=bind,source='+str(cfg)+',target=/app/federator/config','--mount','type=bind,source='+str(cfg/'db')+',target=/app/federator/db','--entrypoint','node',NODE,'-e',source_code]);owned.append(source)
  source_meta=json.loads(call(['inspect',source]))[0];log_path=source_meta['LogPath'];log_dir=str(Path(log_path).parent.parent if args.upgrade_integration else Path(log_path).parent)
  original.write_text(json.dumps({'api_key':'0'*32,'hostname':nonce,'logs_enabled':True,'logs_config':{'run_path':'/opt/datadog-agent/run','logs_dd_url':'sink:8080','logs_no_ssl':True,'force_use_http':True,'container_collect_all':False},'enable_payloads':{'series':False,'events':False,'service_checks':False,'sketches':False}}));original.chmod(0o600)
  (logs_cfg/'conf.yaml.default').write_text(json.dumps({'logs':[{'type':'file','path':log_path,'service':'bridge-dd-lab','source':'docker'}]}))
  def create_agent(recreated=False):
   a=['create','--name',agent,'--label','bridge-dd-lab='+nonce,'--network',network,'-e','DD_API_KEY='+'0'*32,'-e','DD_HOSTNAME='+nonce,'-e','DD_APM_ENABLED=false','-e','DD_PROCESS_AGENT_ENABLED=false','-e','DD_LOG_LEVEL=error','-e','DD_ENABLE_PAYLOADS_SERIES=false','-e','DD_ENABLE_PAYLOADS_EVENTS=false','-e','DD_ENABLE_PAYLOADS_SERVICE_CHECKS=false','-e','DD_ENABLE_PAYLOADS_SKETCHES=false','--mount','type=bind,source='+log_dir+',target='+log_dir+',readonly','--log-opt','max-size=2m']
   if recreated:a+=['-e','DD_LOGS_CONFIG_RUN_PATH='+m.PERSISTENT_PATH,'-e','DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE=true','--mount','type=volume,source='+volume+',target=/var/log/datadog']
   a+=[AGENT];call(a);owned.append(agent)
   for mount in json.loads(call(['inspect',agent]))[0]['Mounts']:
    if mount['Type']=='volume':owned_volumes.add(mount['Name'])
   call(['cp',str(original),agent+':'+m.DOCKER_CONFIG])
   alias=root/'config-alias.tar'
   with tarfile.open(alias,'w') as archive:
    row=tarfile.TarInfo('datadog.yaml');row.type=tarfile.SYMTYPE;row.linkname=m.DOCKER_CONFIG;archive.addfile(row)
   with alias.open('rb') as f:
    r=subprocess.run(D+['cp','-',agent+':/etc/datadog-agent'],stdin=f,capture_output=True,timeout=30)
    if r.returncode:raise RuntimeError('Cannot create standard configuration-alias fixture')
   call(['cp',str(logs_cfg),agent+':/etc/datadog-agent/conf.d/bridge_lab.d'])
  create_agent();volume=next(x['Name'] for x in json.loads(call(['inspect',agent]))[0]['Mounts'] if x['Destination']=='/var/log/datadog');results['original_volume_anonymous']=True;call(['start',agent])
  wait(lambda:len(got())>10,'first real Agent delivery');call(['stop',agent])
  call(['cp',agent+':/opt/datadog-agent/run/registry.json',str(reg)])
  registry=json.loads(reg.read_text());key='file:'+log_path
  if registry.get('Version')!=2 or key not in registry.get('Registry',{}):raise RuntimeError('Unexpected real Agent source schema: '+str(list(registry)))
  assert registry['Registry'][key]['TailingMode']=='', 'Expected real Agent default empty mode'
  results['default_empty_tailing_mode']=True
  results['registry_schema']=registry['Version'];results['agent_version']=call(['run','--rm','--network','none','--log-driver','none','--entrypoint','agent',AGENT,'version'])
  registry['Registry'][key]['Offset']='0'
  if args.socket_cursor_fixture:
   registry['Registry'].pop(key);registry['Registry']['docker:'+source_meta['Id']]={'Offset':'2025-11-19T16:00:00Z','TailingMode':''};results['started_with_socket_only_checkpoint']=True
  reg.write_text(json.dumps(registry));call(['cp',str(reg),agent+':/opt/datadog-agent/run/registry.json'])
  reset_sink();(cfg/'phase').write_text('BRIDGE_LAB_FRESH')
  wait(lambda:'BRIDGE_LAB_FRESH' in call(['logs','--tail','1',source]),'new source phase',15)
  class LabDocker(m.Docker):
   def __init__(self):self.operations=[];self.interruption=None;self.checks=0
   def call(self,args,*a,**kw):
    self.operations.append(list(args))
    target=args[-1] if args[0]=='cp' else ''
    registry_write=target.endswith(':'+m.PERSISTENT_PATH)
    config_write=target.endswith(':'+m.DOCKER_CONFIG)
    if registry_write and self.interruption=='before-registry':
     self.interruption=None;raise m.RepairError('Injected before-registry')
    result=super().call(args,*a,**kw)
    if (registry_write and self.interruption=='after-registry') or (config_write and self.interruption=='after-config'):
     phase=self.interruption;self.interruption=None;raise m.RepairError('Injected '+phase)
    return result
   def inspect(self,name,agent=False):
    result=super().inspect(globals()['agent'] if name=='datadog-agent' else globals()['source'] if name=='bridge-sc_federation_1' else name,agent)
    self.checks+=1
    if self.checks%2:result['mounts'].reverse()
    return result
  docker=LabDocker();out=root/'repair'
  if args.upgrade_integration:
   spec=importlib.util.spec_from_file_location('dd_upgrade_smoke',SCRIPT.with_name('federator_datadog_upgrade.py'))
   u=importlib.util.module_from_spec(spec)
   import sys
   sys.path.insert(0,str(SCRIPT.parent))
   spec.loader.exec_module(u);u.r=m
   before_ops=len(docker.operations)
   preflight=u.inspect(docker,root/'preflight')
   assert preflight['agent_running'] is False
   assert not any(op[0] in ('start','stop') for op in docker.operations[before_ops:])
   state=u.capture(docker,root/'upgrade-capture');u.verify(docker,root/'upgrade-capture')
   assert state['agent_repaired_now']
   results['stopped_upgrade_preflight_read_only']=True;results['upgrade_capture_and_verify_passed']=True
  else:
   forced = json.loads((logs_cfg/'conf.yaml.default').read_text());forced['logs'][0]['start_position']='forceBeginning'
   (logs_cfg/'conf.yaml.default').write_text(json.dumps(forced));call(['cp',str(logs_cfg),agent+':/etc/datadog-agent/conf.d/bridge_lab.d'])
   try:
    m.prepare(docker,root/'forced-refused')
    raise AssertionError('Forced beginning accepted')
   except m.RepairError:
    results['force_beginning_preparation_refused']=True
    assert not any(op[0] in ('start','stop') for op in docker.operations)
   forced['logs'][0].pop('start_position');(logs_cfg/'conf.yaml.default').write_text(json.dumps(forced));call(['cp',str(logs_cfg),agent+':/etc/datadog-agent/conf.d/bridge_lab.d'])
   assert m.config_path(docker,docker.inspect('datadog-agent',agent=True))==m.DOCKER_CONFIG
   m.prepare(docker,out)
   for phase in ('before-registry','after-registry','after-config'):
    docker.interruption=phase
    try:
     m.apply(docker,out);raise AssertionError('Expected interruption '+phase)
    except m.RepairError as error:
     assert str(error)=='Injected '+phase,str(error)
    assert not docker.inspect('datadog-agent',agent=True)['state']['Running']
    assert (out/'apply-started.json').is_file()
   m.apply(docker,out)
   results['prestart_interruptions_resumed']=['before-registry','after-registry','after-config']
   results['per_attempt_evidence_preserved']=len(list(out.glob('attempt-*')))==4
   results['mount_permutations_supported']=True
  assert m.config_path(docker,docker.inspect('datadog-agent',agent=True))==m.DOCKER_CONFIG
  results['standard_configuration_symlink_preserved']=True
  wait(lambda:any('BRIDGE_LAB_FRESH' in x for x in got()),'fresh delivery')
  assert not any('BRIDGE_LAB_HISTORY' in x for x in got()),'Historical logs replayed after cutoff'
  results['fresh_after_cutover']=len(got());results['historical_after_cutover']=0
  call(['stop',agent]);reset_sink();(cfg/'phase').write_text('BRIDGE_LAB_RESTART')
  if args.upgrade_integration:
   u.capture(docker,root/'retained-restart');u.verify(docker,root/'retained-restart');results['retained_upgrade_restart_passed']=True
  else:call(['start',agent])
  wait(lambda:any('BRIDGE_LAB_RESTART' in x for x in got()),'same Agent restart')
  assert not any('BRIDGE_LAB_HISTORY' in x for x in got())
  results['ordinary_restart_preserved_offsets']=True
  call(['stop',agent]);call(['rm',agent]);owned.remove(agent);reset_sink();(cfg/'phase').write_text('BRIDGE_LAB_RECREATE');create_agent(recreated=True);call(['start',agent])
  wait(lambda:any('BRIDGE_LAB_RECREATE' in x for x in got()),'Agent recreation with explicit state volume')
  assert not any('BRIDGE_LAB_HISTORY' in x for x in got())
  results['recreation_preserved_offsets']=True
  final=json.loads(call(['inspect',source]))[0]
  assert final['Id']==source_meta['Id'] and final['State']['StartedAt']==source_meta['State']['StartedAt'] and final['State']['Running']
  assert (cfg/'db/keep').read_text()=='preserve database fixture' and (cfg/'keep').read_text()=='preserve configuration fixture'
  assert 'BRIDGE_LAB_HISTORY_0' in call(['logs',source])
  assert not any(a[0] in ['stop','start','restart','rm','rename'] and source_meta['Id'] in a for a in docker.operations)
  results['source_container_unchanged']=True;results['local_history_preserved']=True;results['database_configuration_preserved']=True
  (args.evidence_dir/'result.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2),flush=True)
 except Exception as error:
  print('LOCAL LAB FAILURE:',type(error).__name__,str(error),flush=True)
  print(call(['logs','--tail','45',agent],check=False),flush=True)
  raise
 finally:
  for name in reversed(owned):call(['rm','-f','-v',name],check=False)
  call(['network','rm',network],check=False)
  for v in owned_volumes:call(['volume','rm',v],check=False)
  results['cleanup_complete']=True
  (args.evidence_dir/'cleanup.json').write_text(json.dumps(results,indent=2)+'\n')
