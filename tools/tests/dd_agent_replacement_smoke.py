#!/usr/bin/env python3
"""Manual, isolated Agent replacement proof; no real keys, services or public intake."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

TOOLS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOLS))
import dd_agent_recovery as r
import federator_agent_replacement as fresh
import federator_upgrade_monitoring as monitoring

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--force-start',action='store_true')
args=parser.parse_args()
args.output.mkdir(mode=0o700,parents=True,exist_ok=True)
D=['docker','--host','unix:///var/run/docker.sock']
nonce='bridge-clean-lab-'+secrets.token_hex(4)
network=nonce+'-net';source=nonce+'-source';agent=nonce+'-agent';sink=nonce+'-sink'
owned=set();volumes=set();result={'utc':r.utc(),'real_datadog_used':False,'production_data_used':False,
    'image':fresh.IMAGE,'tool_sha256':hashlib.sha256((TOOLS/'federator_agent_replacement.py').read_bytes()).hexdigest()}


def call(argv,check=True):
    p=subprocess.run(D+argv,text=True,capture_output=True,timeout=120)
    if check and p.returncode:raise RuntimeError('Lab Docker '+argv[0]+' failed; raw output withheld')
    return p.stdout.strip()


def metadata(name):return json.loads(call(['inspect',name]))[0]


def track(name):
    owned.add(name)
    for mount in metadata(name)['Mounts']:
        if mount['Type']=='volume':volumes.add(mount['Name'])


def received():
    return json.loads(call(['exec',sink,'node','-e','fetch("http://127.0.0.1:8080/received").then(r=>r.text()).then(console.log)']))

sink_code=r'''const http=require('http'),zlib=require('zlib');let records=[];http.createServer((q,s)=>{if(q.url==='/received'){s.end(JSON.stringify(records));return}let chunks=[];q.on('data',d=>chunks.push(d));q.on('end',()=>{let b=Buffer.concat(chunks);try{if(q.headers['content-encoding']==='gzip')b=zlib.gunzipSync(b);if(q.headers['content-encoding']==='deflate')b=zlib.inflateSync(b)}catch(e){}records.push(...(b.toString().match(/BRIDGE_CLEAN_(?:HISTORY|FRESH|RESTART)_[0-9]+/g)||[]));s.statusCode=q.url.includes('validate')?200:202;s.end('{}')})}).listen(8080,'0.0.0.0')'''
source_code="const fs=require('fs');let n=0;for(let i=0;i<300;i++)console.log('BRIDGE_CLEAN_HISTORY_'+n++);setInterval(()=>console.log(fs.readFileSync('/app/federator/config/phase','utf8').trim()+'_'+n++),200)"

with tempfile.TemporaryDirectory(prefix='clean-dd-lab-') as tmp:
    root=Path(tmp).resolve();cfg=root/'federator-env/mainnet-ETH-RSK';(cfg/'db').mkdir(parents=True)
    (cfg/'phase').write_text('BRIDGE_CLEAN_HISTORY');(cfg/'db/keep').write_text('database fixture')
    try:
        assert json.loads(call(['image','inspect',fresh.IMAGE]))[0]['Id']==fresh.IMAGE_ID
        call(['network','create','--internal','--label','bridge-clean-lab='+nonce,network])
        call(['run','-d','--name',sink,'--label','bridge-clean-lab='+nonce,'--network',network,'--network-alias','sink',
              '--entrypoint','node','node:22-bookworm','-e',sink_code]);track(sink)
        call(['run','-d','--name',source,'--label','bridge-clean-lab='+nonce,'--network','none',
              '--log-driver','json-file','--log-opt','max-size=2m','--mount','type=bind,source='+str(cfg)+',target=/app/federator/config',
              '--mount','type=bind,source='+str(cfg/'db')+',target=/app/federator/db','--entrypoint','node','node:22-bookworm','-e',source_code]);track(source)
        src=metadata(source);log=src['LogPath']
        env=['DD_HOSTNAME='+nonce,'DD_APM_ENABLED=false','DD_PROCESS_AGENT_ENABLED=false','DD_LOG_LEVEL=error',
             'DD_LOGS_CONFIG_LOGS_DD_URL=sink:8080','DD_LOGS_CONFIG_LOGS_NO_SSL=true','DD_LOGS_CONFIG_FORCE_USE_HTTP=true',
             'DD_ENABLE_PAYLOADS_SERIES=false','DD_ENABLE_PAYLOADS_EVENTS=false','DD_ENABLE_PAYLOADS_SERVICE_CHECKS=false','DD_ENABLE_PAYLOADS_SKETCHES=false']
        argv=['create','--platform','linux/amd64','--name',agent,'--label','bridge-clean-lab='+nonce,'--network',network,'--restart','always']
        for value in env:argv+=['-e',value]
        call(argv+[fresh.IMAGE]);track(agent)
        main=root/'original.yaml'
        main.write_text(json.dumps({'api_key':'0'*32,'hostname':nonce,'site':'datadoghq.eu','tags':['lab:clean-replacement'],
            'logs_enabled':True,'logs_config':{'logs_dd_url':'sink:8080','logs_no_ssl':True,'force_use_http':True}}));main.chmod(0o600)
        call(['cp',str(main),agent+':'+r.DOCKER_CONFIG])
        call(['cp',str(main),agent+':'+r.AGENT_CONFIG])
        conf=root/'bridge_lab.d';conf.mkdir()
        (conf/'conf.yaml').write_text(json.dumps({'logs':[{'type':'file','path':log,'service':'bridge-clean-lab','source':'docker',
            'start_position':'forceBeginning' if args.force_start else 'beginning'}]}))
        call(['cp',str(conf),agent+':/etc/datadog-agent/conf.d/bridge_lab.d'])
        call(['start',agent]);time.sleep(2);call(['stop',agent])
        bad=root/'old-registry.json';bad.write_bytes(b'invalid old registry\0')
        call(['cp',str(bad),agent+':/opt/datadog-agent/run/registry.json'])
        old_id=metadata(agent)['Id'];source_id=src['Id'];old_volumes=set(volumes)

        class LabDocker(r.Docker):
            def call(self,argv,**kwargs):
                argv=list(argv)
                if argv[0]=='pull':return b'already verified local pinned image'
                if argv[:4]==['ps','--all','--quiet','--no-trunc']:
                    return (source_id+'\n'+old_id+'\n').encode()
                if argv[0]=='inspect' and len(argv)>1:
                    if argv[1]=='datadog-agent':argv[1]=agent
                    if argv[1]=='bridge-sc_federation_1':argv[1]=source
                if argv[0]=='rename':
                    argv[2]=nonce+'-'+argv[2];owned.add(argv[2]);owned.discard(agent)
                if argv[0]=='create':
                    argv[argv.index('--name')+1]=agent
                    # The real file collector is tested; do not expose unrelated host metadata to the lab.
                    clean=[];i=0
                    while i<len(argv):
                        if argv[i]=='--mount' and any(t in argv[i+1] for t in ('target=/var/run/docker.sock','target=/host/proc','target=/host/sys/fs/cgroup')):i+=2;continue
                        clean.append(argv[i]);i+=1
                    argv=clean
                try:value=super().call(argv,**kwargs)
                except r.RepairError:
                    print('LAB_DOCKER_PHASE:',argv[:3],flush=True)
                    raise
                if argv[0]=='create':track(agent)
                if argv[:2]==['volume','create']:volumes.add(value.decode().strip())
                return value
        docker=LabDocker();packet=root/'monitoring'
        monitoring.snapshot(docker,packet)
        (cfg/'phase').write_text('BRIDGE_CLEAN_FRESH')
        before=metadata(source)['State']['StartedAt']
        original_replace=fresh.replace
        def debug_replace(*a,**kw):
            try:return original_replace(*a,**kw)
            except r.RepairError as error:
                print('LAB_REPLACEMENT_ERROR:',str(error),flush=True)
                raise
        fresh.replace=debug_replace
        value=monitoring.recover(docker,packet,request_key=lambda:(_ for _ in ()).throw(RuntimeError('existing YAML key was not reused')))
        if value['status']!='TRACKING_CONFIGURED':raise RuntimeError('Clean replacement failed: '+value.get('failure_type',value['reason']))
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            got=received()
            if sum('FRESH' in x for x in got)>5:break
            time.sleep(2)
        got=received();history=sum('HISTORY' in x for x in got);fresh_count=sum('FRESH' in x for x in got)
        if history or fresh_count<5:raise RuntimeError('Delivery/cutoff proof failed: historical='+str(history)+' fresh='+str(fresh_count))
        # Ordinary Agent restart retains its new registry; no application restart.
        (cfg/'phase').write_text('BRIDGE_CLEAN_RESTART');call(['restart',agent])
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if sum('RESTART' in x for x in received())>3:break
            time.sleep(2)
        got=received()
        assert not any('HISTORY' in x for x in got)
        assert sum('RESTART' in x for x in got)>3
        assert metadata(source)['State']['StartedAt']==before
        assert (cfg/'db/keep').read_text()=='database fixture'
        retained=metadata(old_id)
        assert retained['State']['Running'] is False and retained['HostConfig']['RestartPolicy']['Name']=='no'
        for volume in old_volumes:assert call(['volume','inspect',volume])
        saved=root/'new-config.yaml';effective=r.config_path(docker,docker.inspect('datadog-agent',agent=True));call(['cp',agent+':'+effective,str(saved)])
        copied=json.loads(saved.read_text());assert copied['site']=='datadoghq.eu' and copied['tags']==['lab:clean-replacement']
        result.update(status='PASS',fresh_records=fresh_count,historical_records=history,restart_records=sum('RESTART' in x for x in got),
                      application_unchanged=True,retained_agent_restart_disabled=True,existing_yaml_key_reused=True,site_tags_preserved=True,old_volumes_retained=old_volumes.issubset(volumes),
                      production_docker_autodiscovery_tested=False,static_file_collector_tested=True,forced_start_fixture=args.force_start)
    except BaseException as error:
        result.update(status='FAIL',failure_type=type(error).__name__,reason=str(error) if isinstance(error,RuntimeError) else 'Evidence assertion failed')
        raise
    finally:
        for name in list(owned):call(['rm','-f','-v',name],check=False)
        for name in list(volumes):call(['volume','rm',name],check=False)
        call(['network','rm',network],check=False)
        result['cleanup_complete']=all(not call(['ps','-aq','--filter','name='+name],check=False) for name in owned)
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        (args.output/'result.json').chmod(0o600)
print(json.dumps(result,indent=2))
