#!/usr/bin/env python3
"""Replace the Agent with the recovered-node image and fresh log checkpoints."""
import hashlib
import base64
import inspect
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import tarfile
import time

import dd_agent_recovery as r

IMAGE = 'public.ecr.aws/datadog/agent@sha256:6a91c406eca7232125b4df4f638a962500690782a4523ee5bc2201f16d6b31ca'
IMAGE_ID = 'sha256:dd5a13fea6fd412ce447742a6c74400527e06afe10a278fccf52e7eb2de43bc8'


def environment(old, request_key=None):
    values = {}
    discard = {'DD_CONF_PATH','DD_CONFIG_FILE','DD_CONFD_PATH','DD_CONFIG_PROVIDERS','DD_EXTRA_CONFIG_PROVIDERS'}
    for row in old.get('Config', {}).get('Env') or []:
        key, sep, value = row.partition('=')
        if sep and (re.fullmatch(r'DD_[A-Z0-9_]+', key) or key in ('HTTP_PROXY','HTTPS_PROXY','NO_PROXY','http_proxy','https_proxy','no_proxy','SSL_CERT_FILE','SSL_CERT_DIR','CURL_CA_BUNDLE','REQUESTS_CA_BUNDLE')) and key not in discard:
            if any(c in value for c in ('\r','\n','\0')):
                raise r.RepairError('A monitoring setting cannot be represented in a private environment file')
            values[key] = value
    if not re.fullmatch(r'[0-9a-fA-F]{32}', values.get('DD_API_KEY', '')):
        if request_key is None:
            raise r.RepairError('Datadog API key unavailable; private key input is required')
        key = request_key().strip()
        if not re.fullmatch(r'[0-9a-fA-F]{32}', key):
            raise r.RepairError('Datadog API key format invalid; contents withheld')
        values['DD_API_KEY'] = key
    values.update(DD_LOGS_ENABLED='true', DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL='true',
                  DD_LOGS_CONFIG_RUN_PATH=r.PERSISTENT_PATH,
                  DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE='true',
                  DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE='true')
    values['DD_CONTAINER_EXCLUDE_LOGS'] = (values.get('DD_CONTAINER_EXCLUDE_LOGS','')+' name:datadog-agent').strip()
    return values


def registry(cutoffs, when):
    entries = {}
    for path, row in cutoffs.items():
        offset = row.get('offset')
        if type(offset) is not int or not 0 <= offset < 2**63:
            raise r.RepairError('Invalid new log cutoff')
        entries['file:'+path] = {'Offset':str(offset), 'TailingMode':'', 'LastUpdated':when}
    return {'Version':2, 'Registry':entries}


def verify_archive(path, image):
    with tarfile.open(path, 'r:') as archive:
        manifests = json.load(archive.extractfile('manifest.json'))
        if len(manifests) != 1:
            raise r.RepairError('Expected one original Agent image in backup')
        entry = manifests[0]
        member = archive.getmember(entry['Config'])
        if not member.isfile() or member.size > 2*1024*1024:
            raise r.RepairError('Unexpected original image config')
        config = archive.extractfile(member).read()
        if 'sha256:'+hashlib.sha256(config).hexdigest() != image:
            raise r.RepairError('Agent image backup identity mismatch')
        if not entry['Layers'] or any(not archive.getmember(name).isfile() for name in entry['Layers']):
            raise r.RepairError('Agent image backup layers unavailable')


def fresh_log_positions(value):
    if isinstance(value,list):return [fresh_log_positions(child) for child in value]
    if not isinstance(value,dict):return value
    result={key:fresh_log_positions(child) for key,child in value.items()}
    if result.get('start_position') in ('forceBeginning','forceEnd'):
        result['start_position']='end'
    if isinstance(result.get('logs'),list):
        for row in result['logs']:
            if isinstance(row,dict) and row.get('type')=='file':row['start_position']='end'
    return result


def prepared_configuration(docker, output, work):
    config_file=output/'config.private.yaml';integrations=output/'integrations.private.tar'
    code='import json,yaml,tarfile,io,base64\n'+inspect.getsource(fresh_log_positions)+"""
body=open('/old-config.yaml','rb').read();cfg=yaml.safe_load(body);new=fresh_log_positions(cfg);changed=int(cfg!=new)
if new!=cfg:body=yaml.safe_dump(new,default_flow_style=False).encode()
buf=io.BytesIO()
with tarfile.open('/old-integrations.tar','r:') as original,tarfile.open(fileobj=buf,mode='w') as target:
 rows=original.getmembers()
 if len(rows)>10000:raise ValueError('Integration archive exceeds bound')
 for row in rows:
  data=original.extractfile(row).read() if row.isfile() else None
  if data is not None and row.name.endswith(('.yaml','.yml','.yaml.default')):
   value=yaml.safe_load(data);replacement=fresh_log_positions(value)
   if replacement!=value:data=yaml.safe_dump(replacement,default_flow_style=False).encode();changed+=1
  if data is not None:row.size=len(data)
  target.addfile(row,io.BytesIO(data) if data is not None else None)
print(json.dumps({'config':base64.b64encode(body).decode(),'integrations':base64.b64encode(buf.getvalue()).decode(),'fresh_start_settings':changed}))
"""
    value=json.loads(docker.helper(IMAGE,code,[(str(config_file),'/old-config.yaml'),(str(integrations),'/old-integrations.tar')]))
    cfg=work/'active-config.private.yaml';confd=work/'active-integrations.private.tar'
    r.write_private_bytes(cfg,base64.b64decode(value['config'],validate=True))
    r.write_private_bytes(confd,base64.b64decode(value['integrations'],validate=True))
    return cfg,confd,value['fresh_start_settings']


def log_cutoffs(docker, image, source):
    ids = docker.call(['ps','--all','--quiet','--no-trunc']).decode().splitlines()
    if not 1 <= len(ids) <= 128 or any(not re.fullmatch(r'[0-9a-f]{64}', cid) for cid in ids):
        raise r.RepairError('Docker source inventory exceeds the supported bound')
    root = str(Path(source['log_path']).parent.parent)
    paths = []
    for cid in sorted(set(ids)):
        row = docker.inspect(cid)
        for key,value in (row.get('labels') or {}).items():
            if key.endswith('.logs') and key.startswith('com.datadoghq.ad.'):
                r.ensure_registry_start_modes(json.loads(value))
        path = row.get('log_path')
        if not path: continue
        if row.get('log_config',{}).get('Type') != 'json-file' or path != root+'/'+cid+'/'+cid+'-json.log':
            raise r.RepairError('A log source does not use the expected Docker JSON file location')
        paths.append(path)
    if source['log_path'] not in paths:
        raise r.RepairError('Current federator log is missing from the cutoff inventory')
    code = 'import json,os,re\nclass RepairError(Exception):pass\n'+inspect.getsource(r.tail_boundary)+'''
rows={}
for p in '''+repr(paths)+''':
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd);base=max(0,s.st_size-131072);os.lseek(fd,base,os.SEEK_SET)
  data=os.read(fd,s.st_size-base)
  row=tail_boundary(data,base) if s.st_size else {'offset':0,'last_record_utc':None}
  row.update(device=s.st_dev,inode=s.st_ino,size=s.st_size);rows[p]=row
 finally:os.close(fd)
print(json.dumps(rows))
'''
    return json.loads(docker.helper(image, code, [(root,root)], user='0:0'))


def extra_mounts(old, root):
    values=[]
    replaced={'/var/log/datadog','/var/run/s6','/opt/datadog-agent/run','/var/run/docker.sock','/host/proc','/host/sys/fs/cgroup',root}
    for row in old.get('Mounts') or []:
        target=row.get('Destination','')
        if target in replaced:continue
        # Effective config and conf.d are copied into the new container, not shadowed by old bindings.
        if target in ('/etc','/etc/datadog-agent'):
            raise r.RepairError('Broad Agent config binding contains dependencies outside copied YAML/integrations; original Agent retained')
        if target in (r.AGENT_CONFIG,r.DOCKER_CONFIG,'/etc/datadog-agent/conf.d') or target.startswith('/etc/datadog-agent/conf.d/'):continue
        if not target.startswith('/') or '..' in Path(target).parts or any(c in target for c in (',','\n','\r','\0')):
            raise r.RepairError('An integration dependency mount has an invalid destination')
        if target.startswith('/var/log/datadog/') or '/var/log/datadog'.startswith(target.rstrip('/')+'/'):
            raise r.RepairError('An old dependency mount would shadow the fresh monitoring state')
        kind=row.get('Type');source=row.get('Source') if kind=='bind' else row.get('Name')
        if kind not in ('bind','volume') or not isinstance(source,str) or not source or any(c in source for c in (',','\n','\r','\0')):
            raise r.RepairError('An integration dependency mount cannot be preserved')
        if kind=='volume' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',source):
            raise r.RepairError('An integration volume has an invalid name')
        values.append('type='+kind+',source='+source+',target='+target+(',readonly' if row.get('RW') is False else ''))
    return values


def replace(docker, output, old, request_key=None, progress=lambda stage:None):
    """Only Agent containers are stopped/renamed/created; old volumes remain retained."""
    from federator_datadog_upgrade import stable, require_same_source
    source = docker.inspect('bridge-sc_federation_1')
    if not source['state'].get('Running') or source['state'].get('Paused'):
        raise r.RepairError('The application must be running before monitoring replacement')
    r.ensure_output_outside_source(output, source)
    token = secrets.token_hex(8)
    work = output/('replacement-'+token); work.mkdir(mode=0o700)
    before = docker.inspect('datadog-agent', agent=True)
    if before['id'] != old['Id'] or before['image'] != old['Image']:
        raise r.RepairError('Original Agent identity changed; retained state left unchanged')
    if old.get('HostConfig',{}).get('AutoRemove'):
        raise r.RepairError('Original Agent uses automatic removal; retain its state before replacing it')
    if before['state'].get('Paused'):
        raise r.RepairError('Agent is paused; it was not replaced automatically')
    if before['state'].get('Status') not in ('running','exited'):
        raise r.RepairError('Original Agent is not in a replaceable lifecycle state')
    progress('DOWNLOAD_AGENT_IMAGE')
    docker.call(['pull','--platform','linux/amd64',IMAGE], timeout=300)
    target = json.loads(docker.call(['image','inspect',IMAGE]))[0]
    if (target.get('Id'),target.get('Os'),target.get('Architecture')) != (IMAGE_ID,'linux','amd64'):
        raise r.RepairError('Pinned replacement Agent identity/platform mismatch')
    # Recover a YAML-supplied credential using the new pinned image, not the old runtime.
    values = dict(row.split('=',1) for row in old.get('Config',{}).get('Env',[]) if '=' in row)
    if not values.get('DD_API_KEY'):
        config_file = output/'config.private.yaml'
        if config_file.is_file() and not config_file.is_symlink():
            try:
                code = 'import json,yaml;v=yaml.safe_load(open("/input.yaml"));print(json.dumps(v.get("api_key") if isinstance(v,dict) else None))'
                key = json.loads(docker.helper(IMAGE,code,[(str(config_file),'/input.yaml')]))
                if isinstance(key,str) and re.fullmatch(r'[0-9a-fA-F]{32}',key):
                    old = json.loads(json.dumps(old))
                    old.setdefault('Config',{}).setdefault('Env',[]).append('DD_API_KEY='+key)
            except (r.RepairError,OSError,ValueError,TypeError):pass
    progress('RECOVER_MONITORING_CREDENTIAL')
    env = environment(old,request_key)
    env_file = work/'agent.env.private'
    r.write_private_bytes(env_file, ''.join(k+'='+v+'\n' for k,v in sorted(env.items())).encode())
    progress('BACKUP_ORIGINAL_AGENT_IMAGE')
    original = json.loads(docker.call(['image','inspect',before['image']]))[0]
    size = original.get('Size')
    if type(size) is not int or size <= 0 or shutil.disk_usage(work).free < size*2+2*1024**3:
        raise r.RepairError('Insufficient reserve for a verified original Agent image archive')
    archive = work/'old-agent-image.tar'
    fd=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
    docker.call(['image','save','--output',str(archive),before['image']], timeout=600)
    os.chmod(archive,0o600); verify_archive(archive,before['image'])
    digest = hashlib.sha256()
    with archive.open('rb') as data:
        for chunk in iter(lambda:data.read(1024*1024),b''): digest.update(chunk)
    r.write_private(work/'image-backup.json', {'image':before['image'],'sha256':digest.hexdigest()})
    network = old.get('HostConfig',{}).get('NetworkMode') or 'bridge'
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',network) or network in ('host','none'):
        raise r.RepairError('A named Docker bridge network is required for the new Agent')
    current = docker.inspect('datadog-agent',agent=True)
    if stable(current) != stable(before):
        raise r.RepairError('Original Agent changed during backup')
    require_same_source(source,docker.inspect('bridge-sc_federation_1'))
    root = str(Path(source['log_path']).parent.parent)
    progress('PREPARE_PRESERVED_CONFIGURATION')
    dependencies=extra_mounts(old,root)
    config_file,integrations,fresh_settings=prepared_configuration(docker,output,work)
    progress('CAPTURE_CURRENT_LOG_CUTOFFS')
    cutoffs = log_cutoffs(docker,IMAGE,source)
    marker = output/'replacement-started.json'
    if marker.exists() or marker.is_symlink():
        raise r.RepairError('Replacement already attempted; retain and inspect this packet')
    r.write_private(marker, {'utc':r.utc(),'old_agent_id':before['id'],'work':str(work)})
    progress('STOP_ORIGINAL_AGENT')
    docker.call(['update','--restart=no',before['id']])
    if before['state'].get('Running'):docker.call(['stop','--time','30',before['id']],timeout=45)
    when = r.utc(); seed = registry(cutoffs,when)
    r.write_private(work/'cutoffs.json',{'utc':when,'files':cutoffs,'scope':'All retained Docker JSON log sources start at their current complete-record boundary; local history is unchanged'})
    stage = work/'bridge-log-state';stage.mkdir(mode=0o700)
    r.write_private(stage/'registry.json',seed)
    stopped = dict(stable(before),running=False)
    if stable(docker.inspect('datadog-agent',agent=True)) != stopped:
        raise r.RepairError('Old Agent changed after stop; no replacement started')
    backup_name = 'datadog-agent-before-'+token
    progress('RETAIN_ORIGINAL_AGENT')
    docker.call(['rename',before['id'],backup_name])
    volume = 'bridge-dd-state-'+token
    docker.call(['volume','create','--label',r.LABEL+'='+token,volume])
    root = str(Path(source['log_path']).parent.parent)
    args = ['create','--platform','linux/amd64','--name','datadog-agent',
            '--label',r.LABEL+'='+token,'--network',network,'--env-file',str(env_file),'--restart','unless-stopped',
            '--log-driver','json-file','--log-opt','max-size=20m','--log-opt','max-file=5',
            '--mount','type=volume,source='+volume+',target=/var/log/datadog',
            '--mount','type=bind,source='+root+',target='+root+',readonly',
            '--mount','type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock,readonly',
            '--mount','type=bind,source=/proc,target=/host/proc,readonly',
            '--mount','type=bind,source=/sys/fs/cgroup,target=/host/sys/fs/cgroup,readonly',IMAGE]
    for mount in dependencies:args[-1:-1]=['--mount',mount]
    progress('CREATE_REPLACEMENT_AGENT')
    new_id = docker.call(args).decode().strip()
    if not re.fullmatch(r'[0-9a-f]{64}',new_id):
        raise r.RepairError('New Agent identity unavailable; inspect the saved packet')
    manifest = {'utc':when,'old_agent_id':before['id'],'backup_name':backup_name,
                'new_agent_id':new_id,'image':IMAGE,'image_id':IMAGE_ID,'volume':volume,
                'source_id':source['id'],'source_cutoff':cutoffs[source['log_path']]['offset'],
                'local_logs_deleted':False,'old_volumes_deleted':False,'fresh_start_settings':fresh_settings,'work':str(work)}
    r.write_private(output/'replacement.json',manifest)
    progress('INSTALL_PRESERVED_CONFIGURATION')
    # Preserve effective settings and custom integrations; only collector state is fresh.
    if config_file.is_file() and not config_file.is_symlink():
        # The pinned image creates datadog.yaml at first startup; seed both standard paths.
        docker.call(['cp',str(config_file),new_id+':'+r.DOCKER_CONFIG])
        docker.call(['cp',str(config_file),new_id+':'+r.AGENT_CONFIG])
    if integrations.is_file() and not integrations.is_symlink():
        docker.copy_config_archive(new_id,integrations)
    progress('INSTALL_FRESH_CHECKPOINTS')
    docker.call(['cp',str(stage),new_id+':/var/log/datadog/'])
    copied = json.loads(docker.copy_out(new_id,r.PERSISTENT_PATH+'/registry.json',work/'installed-registry.private.json'))
    if copied != seed:raise r.RepairError('New Agent checkpoint installation did not verify')
    require_same_source(source,docker.inspect('bridge-sc_federation_1'))
    progress('START_REPLACEMENT_AGENT')
    docker.call(['start',new_id])
    progress('VERIFY_REPLACEMENT_AGENT')
    agent = docker.inspect('datadog-agent',agent=True)
    if agent['id']!=new_id or agent['image']!=IMAGE_ID or not agent['state'].get('Running'):
        raise r.RepairError('Replacement Agent did not remain running')
    require_same_source(source,docker.inspect('bridge-sc_federation_1'))
    return manifest, agent
