#!/usr/bin/env python3
"""Bounded, secret-free deployment capture and offline replay inputs for ETH operators."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import tarfile
import time
from urllib.parse import urlsplit
import zipfile

SCHEMA = 1
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
CANONICAL_REPO = '/home/ubuntu/Bridge-SC'
MAX_BYTES = 2 * 1024 * 1024


class EnvironmentError(Exception):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def field_name(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:/-]{0,120}', value) else '[withheld-field]'


def presence(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if not value:
        return [] if isinstance(value, list) else {} if isinstance(value, dict) else ''
    return '[withheld]'


def env_pairs(config):
    pairs = {}
    for item in config.get('Env') or []:
        if isinstance(item, str) and '=' in item:
            k, v = item.split('=', 1)
            pairs[field_name(k)] = v
    return pairs


def sanitize_deployment(container, image, repo, agent=False):
    """Preserve guard-relevant values and equality without exporting arbitrary strings."""
    repo = str(Path(repo).absolute())
    cfg = repo + '/federator-env/mainnet-ETH-RSK'
    canonical = CANONICAL_REPO + '/federator-env/mainnet-ETH-RSK'
    c, i = copy.deepcopy(container), copy.deepcopy(image)
    cc, ic = container.get('Config') or {}, image.get('Config') or {}
    def config_value(key, value):
        if key in ('Tty','OpenStdin','StdinOnce','ArgsEscaped','AttachStdin','AttachStdout','AttachStderr','NetworkDisabled','StopTimeout'):
            return presence(value)
        if key == 'Hostname':
            return value if value in (None, '', container.get('Id','')[:12]) else '[custom-hostname]'
        if key == 'Domainname':return '' if not value else '[custom-domain]'
        if key == 'User':return value if value in (None,'','node','1000','1000:1000','root','0') else '[custom-user]'
        if key == 'WorkingDir':return value if value in (None,'','/app/federator') else '[custom-directory]'
        if key == 'StopSignal':return value if value is None or isinstance(value,str) and re.fullmatch(r'SIG[A-Z0-9]{1,12}',value) else '[custom-signal]'
        if key in ('Cmd','Entrypoint'):
            allowed = {'npm','start','node','docker-entrypoint.sh','/usr/local/bin/docker-entrypoint.sh'}
            return value if isinstance(value,list) and all(x in allowed for x in value) else presence(value)
        if key in ('ExposedPorts','Volumes'):
            allowed_key = (lambda k: bool(re.fullmatch(r'[0-9]{1,5}/(?:tcp|udp)',k))) if key == 'ExposedPorts' else (lambda k:k in ('/app/federator/config','/app/federator/db'))
            return {k if allowed_key(k) else '/withheld-'+str(n):presence(v) for n,(k,v) in enumerate((value or {}).items())}
        if key == 'Image':return '[image-reference]'
        return presence(value)
    ci, ii = {}, {}
    for key in cc.keys() | ic.keys():
        if key in ('Env','Labels'):continue
        a, b = cc.get(key), ic.get(key)
        public_b = config_value(key,b)
        if key in ic:ii[field_name(key)] = public_b
        if key in cc:
            value = copy.deepcopy(public_b) if a == b else config_value(key,a)
            if a != b and value == public_b and (a or b):value = '[different-withheld]'
            ci[field_name(key)] = value
    # Preserve duplicate/malformed rows; collapsing to a dict hides real blockers.
    raw_names=[]
    for config in (cc,ic):
        for row in config.get('Env') or []:
            if isinstance(row,str) and '=' in row:raw_names.append(row.split('=',1)[0])
    name_map={}
    for k in raw_names:
        if k not in name_map:
            name_map[k]=k if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',k) else 'WITHHELD_ENV_'+str(len(name_map))
    baseline={row.split('=',1)[0]:row.split('=',1)[1] for row in ic.get('Env') or [] if isinstance(row,str) and '=' in row}
    def rows(config,original=False):
        result=[]
        for row in config.get('Env') or []:
            if not isinstance(row,str) or '=' not in row:
                result.append('[malformed-environment-entry]');continue
            key,value=row.split('=',1)
            public=value if key=='TZ' and value=='UTC' else '[image-value]' if original or key in baseline and value==baseline[key] else '[different-value]'
            result.append(name_map[key]+'='+public)
        return result
    ci['Env'],ii['Env']=rows(cc),rows(ic,True)
    cl, il = cc.get('Labels') or {}, ic.get('Labels') or {}
    def label(k,v,original=False):
        if k in ('com.docker.compose.project','com.docker.compose.service'):
            return v if isinstance(v,str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}',v) else '[custom-label]'
        if not isinstance(v,str):return presence(v)
        if '$' in v:return '$[withheld-label]'
        return '[image-label]' if original or k in il and v == il[k] else '[different-label]'
    ci['Labels'] = {field_name(k):label(k,v) for k,v in cl.items()}
    ii['Labels'] = {field_name(k):label(k,v,True) for k,v in il.items()}
    c['Config'], i['Config'] = ci, ii
    c = {k:c[k] for k in ('Id','Image','State','Config') if k in c}
    c['State'] = {k:container.get('State',{}).get(k) for k in ('Status','Running','Paused','OOMKilled','ExitCode','StartedAt','FinishedAt','Restarting')}
    c['Mounts'] = []
    agent_targets={'/var/run/docker.sock','/var/log/datadog','/var/run/s6','/var/lib/docker/containers','/host/proc','/host/sys/fs/cgroup','/etc/datadog-agent','/etc/datadog-agent/datadog.yaml'}
    allowed_targets={'/app/federator/config','/app/federator/db'} | (agent_targets if agent else set())
    for n,m in enumerate(container.get('Mounts') or []):
        source = m.get('Source')
        source = canonical + source[len(cfg):] if source in (cfg,cfg+'/db') else '[custom-source-'+str(n)+']'
        target = m.get('Destination')
        c['Mounts'].append({'Type':m.get('Type') if m.get('Type') in ('bind','volume','tmpfs') else '[custom-type]',
            'Source':source,'Destination':target if target in allowed_targets else '/withheld-'+str(n),
            'RW':m.get('RW')})
        if 'Propagation' in m:
            c['Mounts'][-1]['Propagation']=m.get('Propagation') if m.get('Propagation') in (None,'','rprivate','private','shared','rshared','slave','rslave') else '[custom-propagation]'
    numeric = {'Memory','MemoryReservation','MemorySwap','NanoCpus','CpuShares','CpuPeriod','CpuQuota','BlkioWeight',
               'PidsLimit','MemorySwappiness','ShmSize','OomScoreAdj','OomKillDisable','Privileged','ReadonlyRootfs','AutoRemove','Init','PublishAllPorts'}
    fixed_strings = {'Runtime':('','runc','docker-runc','crun'),'IpcMode':('','private','shareable','host','none'),
                     'CgroupnsMode':('','host','private'),'Isolation':('','default','process','hyperv')}
    host = {}
    for key,v in (container.get('HostConfig') or {}).items():
        if key in numeric:host[key] = v if v is None or type(v) in (int,bool) else '[invalid-type]'
        elif key in ('CpusetCpus','CpusetMems'):host[key] = v if v is None or isinstance(v,str) and re.fullmatch(r'(?:[0-9]+(?:[-,][0-9]+)*)?',v) else '[custom-affinity]'
        elif key in fixed_strings:host[key] = v if v is None or v in fixed_strings[key] else '[custom-value]'
        elif key in ('MaskedPaths','ReadonlyPaths'):
            host[key] = [p if isinstance(p,str) and re.fullmatch(r'/(?:proc|sys)(?:/[A-Za-z0-9_.-]+)*',p) else '/withheld' for p in v] if isinstance(v,list) else presence(v)
        elif key == 'ConsoleSize':host[key] = v if isinstance(v,list) and all(type(x)is int for x in v) else presence(v)
        elif key == 'NetworkMode':
            project = cl.get('com.docker.compose.project','')
            host[key] = v if v in ('host','none','bridge',project+'_default') else '[custom-network]'
        elif key == 'PortBindings':
            host[key] = {p if re.fullmatch(r'[0-9]{1,5}/(?:tcp|udp)',p) else '[custom-port]':
                [{'HostIp':b.get('HostIp') if b.get('HostIp') in ('','0.0.0.0','127.0.0.1','::') else '[custom-ip]',
                  'HostPort':b.get('HostPort') if isinstance(b.get('HostPort'),str) and b['HostPort'].isdigit() else '[custom-port]'} for b in bindings or []] for p,bindings in (v or {}).items()}
        elif key == 'RestartPolicy':host[key] = {'Name':v.get('Name') if v.get('Name') in ('','no','always','on-failure','unless-stopped') else '[custom-policy]','MaximumRetryCount':presence(v.get('MaximumRetryCount'))} if isinstance(v,dict) else presence(v)
        elif key == 'LogConfig':host[key] = {'Type':v.get('Type') if v.get('Type') in ('','json-file','local','journald','none','syslog','fluentd','awslogs') else '[custom-driver]',
                'Config':{field_name(k):val if k in ('max-size','max-file') and isinstance(val,str) and re.fullmatch(r'[0-9]{1,12}[kKmMgG]?',val) else '[withheld]' for k,val in (v.get('Config') or {}).items()}} if isinstance(v,dict) else presence(v)
        elif key == 'Binds':
            host[key] = []
            for b in v or []:
                parts = b.split(':') if isinstance(b,str) else []
                if len(parts) in (2,3):parts[0],parts[1]=str(Path(parts[0])),str(Path(parts[1]))
                if len(parts) in (2,3) and parts[0] in (cfg,cfg+'/db') and parts[1] in ('/app/federator/config','/app/federator/db'):
                    host[key].append(canonical+parts[0][len(cfg):]+':'+parts[1]+(':'+parts[2] if len(parts)==3 and parts[2] in ('rw','ro','z','Z') else ':custom' if len(parts)==3 else ''))
                else:host[key].append('[custom-bind]')
        else:host[field_name(key)] = presence(v)
    c['HostConfig'] = host
    networks = {}
    project = cl.get('com.docker.compose.project','')
    for n,(name,endpoint) in enumerate((container.get('NetworkSettings',{}).get('Networks') or {}).items()):
        values = {}
        for k,v in endpoint.items():
            if k in ('Aliases','DNSNames'):
                allowed = {container.get('Id','')[:12],'federation','bridge-sc_federation_1'}
                values[k] = [a if a in allowed else '[custom-alias]' for a in v or []]
            else:values[field_name(k)] = presence(v)
        networks[name if name == project+'_default' else 'custom-network-'+str(n)] = values
    c['NetworkSettings'] = {'Networks':networks}
    i = {k:i[k] for k in ('Id','Os','Architecture','Config') if k in i}
    for key in ('Id','Image'):
        if key in c and not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}',str(c[key])):c[key]='[unavailable]'
    return {'repo':CANONICAL_REPO,'container':c,'image':i}


def read_bounded(root, relative, limit=MAX_BYTES):
    root = Path(root).absolute();path = root/relative
    if root.is_symlink() or any((root/Path(*Path(relative).parts[:n])).is_symlink() for n in range(1,len(Path(relative).parts)+1)):
        raise EnvironmentError('Symlinked input withheld')
    if '..' in Path(relative).parts or Path(relative).is_absolute():raise EnvironmentError('Input outside profile')
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise EnvironmentError('Nonregular input withheld')
        data=source.read(limit+1)
    if len(data)>limit:raise EnvironmentError('Input exceeds capture bound')
    return data


def public_configuration(repo):
    cfg=Path(repo)/'federator-env/mainnet-ETH-RSK'
    if (Path(repo)/'federator-env').is_symlink() or cfg.is_symlink():
        return {'config_status':'UNAVAILABLE','chains':{},'cursors':{},'key_files':{},'peers_status':'UNAVAILABLE'}
    out={'config_status':'UNAVAILABLE','chains':{},'cursors':{},'key_files':{},'peers_status':'UNAVAILABLE'}
    try:
        text=read_bounded(cfg,'config.js').decode('utf8')
        text=re.sub(r'(\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\')|//[^\n]*|/\*.*?\*/',lambda m:m.group(1) or ' ',text,flags=re.S)
        address=re.search(r"\bfederatorAddress\s*:\s*['\"](0x[0-9a-fA-F]{40})['\"]",text)
        out['configured_signer']=address[1] if address else None
        for key in ('minimumPeerAmount','runEvery','gasApiRunEvery','avgGasRunEvery','periodAvgGas','signaturesTTL','signatureRequestTimeoutMs','ethGasPriceThresholdGwei'):
            value=re.search(r'\b'+key+r'\s*:\s*(\d+(?:\.\d+)?)\s*[,}]',text)
            out[key]=float(value[1]) if value and '.' in value[1] else int(value[1]) if value else None
        out['etherscan_file_reference']='etherscan.key' in text
        out['config_status']='OBSERVED'
    except (OSError,ValueError,EnvironmentError):pass
    for label,name in (('ethereum','mainnet.json'),('rootstock','rskmainnet.json')):
        item={'status':'UNAVAILABLE'}
        try:
            raw=json.loads(read_bounded(cfg,name))
            item={'status':'OBSERVED'}
            for key,val in raw.items():
                if key in ('chainId','fromBlock','confirmations','gas','gasPrice') and type(val)in(int,float):item[key]=val
                elif key in ('bridge','federation','multiSig','allowTokens','erc777Converter') and isinstance(val,str) and re.fullmatch(r'0x[0-9a-fA-F]{40}',val):item[key]=val
            endpoint=urlsplit(raw.get('host',''))
            hostname=(endpoint.hostname or '').lower()
            provider='Sovryn' if hostname.endswith('.sovryn.app') else 'Infura' if hostname.endswith('.infura.io') else 'Alchemy' if hostname.endswith('.alchemy.com') else 'custom'
            item['endpoint']={'scheme':endpoint.scheme if endpoint.scheme in ('http','https') else '[custom]',
                'provider':provider,'hostname_withheld':True,
                'credentials_or_path_withheld':bool(endpoint.username or endpoint.password or endpoint.path or endpoint.query or endpoint.fragment)}

        except (OSError,ValueError,TypeError,AttributeError,EnvironmentError):pass
        out['chains'][label]=item
    for label,name in (('rootstock','db/lastBlock.txt'),('ethereum','db/side-fed/lastBlock.txt')):
        try:
            value=read_bounded(cfg,name,64).decode('ascii').strip()
            out['cursors'][label]=value if re.fullmatch(r'\d{1,20}',value) else '[invalid]'
        except (OSError,ValueError,EnvironmentError):out['cursors'][label]=None
    for name in ('federator.key','etherscan.key','telegram.key'):
        try:
            info=(cfg/name).lstat()
            out['key_files'][name]={'present':True,'regular':stat.S_ISREG(info.st_mode),'symlink':stat.S_ISLNK(info.st_mode),
                'uid':info.st_uid,'mode':oct(stat.S_IMODE(info.st_mode)),'bytes':info.st_size}
        except OSError:out['key_files'][name]={'present':False}
    try:
        text=read_bounded(cfg,'peers.config.js').decode('utf8')
        match=re.fullmatch(r'\s*module\.exports\s*=\s*(\{.*\})\s*;?\s*',text,re.S)
        peers=json.loads(match[1])['peers'] if match else None
        if not isinstance(peers,list) or len(peers)>100:raise ValueError()
        if not all(isinstance(p,dict) for p in peers):raise ValueError()
        out['peer_count']=len(peers)
        out['peers']=[{'address':p.get('address') if re.fullmatch(r'0x[0-9a-fA-F]{40}',str(p.get('address'))) else None,
            'port':p.get('port') if type(p.get('port'))is int and 0<p['port']<65536 else None,
            'endpoint_present':isinstance(p.get('ip'),str) and bool(p['ip'])} for p in peers]
        out['peers_status']='OBSERVED'
    except (OSError,ValueError,KeyError,TypeError,AttributeError,EnvironmentError):pass
    return out


NODE_PROBE = r'''
const fs=require('fs'),crypto=require('crypto'),http=require('http'),https=require('https');
function file(p,limit=2097152){const fd=fs.openSync(p,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);try{const st=fs.fstatSync(fd);if(!st.isFile()||st.size>limit)throw 0;const b=Buffer.alloc(limit+1);const n=fs.readSync(fd,b,0,b.length,0);if(n>limit)throw 0;return b.subarray(0,n);}finally{fs.closeSync(fd);}}
const hardExit=setTimeout(()=>{process.stdout.write(JSON.stringify({status:'UNAVAILABLE'})+'\n',()=>process.exit(0));},8000);
const out={status:'OBSERVED',node:process.version,arch:process.arch,abi:process.versions.modules,packages:{},sources:{},rpc:{}};
for(const name of ['ethers','ataraxia','ataraxia-tcp','ataraxia-transport','ataraxia-transport-streams','@ethereumjs/tx','@ethereumjs/common']){
 try{const p=require.resolve(name+'/package.json');const v=JSON.parse(file(p,65536)).version;out.packages[name]=/^\d+\.\d+\.\d+[A-Za-z0-9.+-]*$/.test(v)?v:null;}catch(e){out.packages[name]=null;}
}
for(const name of ['GasPriceAvg','GasPriceFetcher','GasServices','TransactionSender']){
 try{out.sources[name]=crypto.createHash('sha256').update(file('/app/federator/src/lib/'+name+'.js')).digest('hex');}catch(e){out.sources[name]=null;}
}
try{out.sources.RSKKeyedAuth=crypto.createHash('sha256').update(file('/app/federator/src/vendors/RSKKeyedAuth.js')).digest('hex');}catch(e){}
function readConfig(name){return file('/app/federator/config/'+name,65536);}
function rpc(file){return new Promise(resolve=>{let u,c;try{c=JSON.parse(readConfig(file));u=new URL(c.host);if(!['http:','https:'].includes(u.protocol))throw 0;}catch(e){return resolve({status:'UNAVAILABLE',reason:'CONFIG'});}
 const jobs=[{jsonrpc:'2.0',id:1,method:'eth_chainId',params:[]},{jsonrpc:'2.0',id:2,method:'eth_blockNumber',params:[]}];
 const addr=v=>typeof v==='string'&&/^0x[0-9a-f]{40}$/i.test(v);
 for(const [id,to,data] of [[3,c.federation,'0x9eab5253'],[4,c.federation,'0xdc8452cd'],[5,c.federation,'0x8da5cb5b'],[6,c.bridge,'0xea217091'],[7,c.multiSig,'0xdc8452cd'],[8,c.multiSig,'0xa0e67e2b']]){
  if(addr(to))jobs.push({jsonrpc:'2.0',id,method:'eth_call',params:[{to,data},'latest']});
 }
 const body=JSON.stringify(jobs);
 function word(v){return typeof v==='string'&&/^0x0{24}[0-9a-f]{40}$/i.test(v)?'0x'+v.slice(-40).toLowerCase():null;}
 function members(v){if(typeof v!=='string'||!/^0x[0-9a-f]+$/i.test(v)||v.length>2+64*52)return null;const b=v.slice(2);if(BigInt('0x'+b.slice(0,64))!==32n)return null;const n=Number(BigInt('0x'+b.slice(64,128)));if(n<1||n>50||b.length!==128+64*n)return null;const a=[];for(let x=0;x<n;x++){const address=word('0x'+b.slice(128+x*64,192+x*64));if(!address)return null;a.push(address);}return a;}

 let done=false;const finish=v=>{if(!done){done=true;resolve(v);}};
 const req=(u.protocol==='https:'?https:http).request(u,{method:'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}},res=>{let b='';res.on('data',c=>{b+=c;if(b.length>65536){res.destroy();finish({status:'UNAVAILABLE',reason:'SIZE'});}});res.on('error',()=>finish({status:'UNAVAILABLE',reason:'RESPONSE'}));res.on('end',()=>{try{if(res.statusCode!==200)throw 0;const a=JSON.parse(b);if(!Array.isArray(a))throw 0;let r={status:'OBSERVED'};for(const [id,k] of [[1,'chainId'],[2,'blockNumber']]){const v=a.find(x=>x.id===id);r[k]=v&&/^0x[0-9a-f]{1,64}$/i.test(v.result)?v.result:null;}
 const get=id=>{const v=a.find(x=>x.id===id);return v&&v.result;};
 r.members=members(get(3));r.owner=word(get(5));r.bridgeFederation=word(get(6));r.administrativeOwners=members(get(8));
 for(const [id,name] of [[4,'required'],[7,'administrativeRequired']]){const v=get(id);const n=typeof v==='string'&&/^0x[0-9a-f]{1,64}$/i.test(v)?BigInt(v):0n;r[name]=n>0n&&n<=50n?Number(n):null;}
 finish(r);}catch(e){finish({status:'UNAVAILABLE',reason:'HTTP_OR_SHAPE'});}});});
 const timer=setTimeout(()=>{req.destroy();finish({status:'UNAVAILABLE',reason:'TIMEOUT'});},4000);req.on('error',()=>finish({status:'UNAVAILABLE',reason:'NETWORK'}));req.on('close',()=>clearTimeout(timer));req.end(body);
});}
Promise.all([rpc('mainnet.json'),rpc('rskmainnet.json')]).then(v=>{out.rpc.ethereum=v[0];out.rpc.rootstock=v[1];clearTimeout(hardExit);process.stdout.write(JSON.stringify(out)+'\n',()=>process.exit(0));});
'''

AGENT_PROBE = r'''
import json,os,re,stat,subprocess,sys,resource
sys.dont_write_bytecode=True
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(8,8))
out={'status':'OBSERVED','config_status':'UNAVAILABLE','registry_status':'UNAVAILABLE'}
def read(path,limit):
 fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as f:
  if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError()
  data=f.read(limit+1)
 if len(data)>limit:raise ValueError()
 return data
try:
 raw=subprocess.check_output(['agent','version'],stderr=subprocess.DEVNULL,timeout=5).decode()
 match=re.search(r'Agent (7\.\d+\.\d+)',raw);out['version']=match[1] if match else None
except Exception:out['version']=None
try:
 import yaml
 cfg=yaml.safe_load(read('/etc/datadog-agent/datadog.yaml',1048576)) or {}
 logs=cfg.get('logs_config') or {};out['config_status']='OBSERVED'
 out['api_key_present']=bool(os.environ.get('DD_API_KEY') or cfg.get('api_key'))
 enabled=os.environ.get('DD_LOGS_ENABLED');out['logs_enabled']=enabled.lower()=='true' if enabled else cfg.get('logs_enabled') is True
 out['collect_all']=os.environ.get('DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL','').lower()=='true' or logs.get('container_collect_all') is True
 path=os.environ.get('DD_LOGS_CONFIG_RUN_PATH') or logs.get('run_path') or '/opt/datadog-agent/run'
 out['persistent_registry']=path=='/var/log/datadog/bridge-log-state'
 if path not in ('/var/log/datadog/bridge-log-state','/opt/datadog-agent/run'):raise ValueError()
 registry=json.loads(read(path+'/registry.json',4194304));out['registry_schema']=registry.get('Version') if type(registry.get('Version'))is int else None
 entries=registry.get('Registry') or {};out['registry_entries']=len(entries)
 cid=__import__('sys').argv[1];out['current_sources']=[]
 for key,val in entries.items():
  if cid in key and isinstance(val,dict):
   offset=val.get('Offset');mode=val.get('TailingMode')
   out['current_sources'].append({'kind':'file' if key.startswith('file:') else 'other','offset':offset if isinstance(offset,str) and re.fullmatch(r'\d{1,20}',offset) else None,'tailing_mode':mode if mode in (None,'','beginning','end') else '[custom]'})
 out['registry_status']='OBSERVED'
except Exception:pass
print(json.dumps(out))
'''


def sanitize_application_probe(value):
    if not isinstance(value,dict):raise EnvironmentError('Unexpected application probe shape')
    def matched(v,pattern):return v if isinstance(v,str) and re.fullmatch(pattern,v) else None
    out={'status':'OBSERVED' if value.get('status')=='OBSERVED' else 'UNAVAILABLE','node':matched(value.get('node'),r'v[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'),
         'arch':value.get('arch') if value.get('arch') in ('x64','arm64','ia32','arm') else None,
         'abi':matched(value.get('abi'),r'[0-9]{1,4}'),'packages':{},'sources':{},'rpc':{}}
    packages=value.get('packages') if isinstance(value.get('packages'),dict) else {}
    for name in ('ethers','ataraxia','ataraxia-tcp','ataraxia-transport','ataraxia-transport-streams','@ethereumjs/tx','@ethereumjs/common'):
        v=packages.get(name);match=re.match(r'^([0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4})(?:[-+][A-Za-z0-9.-]+)?$',v) if isinstance(v,str) else None
        out['packages'][name]=match[1] if match else None
    sources=value.get('sources') if isinstance(value.get('sources'),dict) else {}
    for name in ('GasPriceAvg','GasPriceFetcher','GasServices','TransactionSender','RSKKeyedAuth'):
        out['sources'][name]=matched(sources.get(name),r'[0-9a-f]{64}')
    rpc=value.get('rpc') if isinstance(value.get('rpc'),dict) else {}
    for label in ('ethereum','rootstock'):
        r=rpc.get(label) if isinstance(rpc.get(label),dict) else {}
        out['rpc'][label]={'status':r.get('status') if r.get('status') in ('OBSERVED','UNAVAILABLE') else 'UNAVAILABLE',
            'chainId':r.get('chainId') if r.get('chainId') in ('0x1','0x1e') else None,
            'blockNumber':matched(r.get('blockNumber'),r'0x[0-9a-fA-F]{1,16}')}
        for field in ('owner','bridgeFederation'):
            out['rpc'][label][field]=matched(r.get(field),r'0x[0-9a-fA-F]{40}')
        for field in ('required','administrativeRequired'):
            out['rpc'][label][field]=r.get(field) if type(r.get(field))is int and 0<r[field]<=50 else None
        for field in ('members','administrativeOwners'):
            rows=r.get(field)
            out['rpc'][label][field]=rows if isinstance(rows,list) and 0<len(rows)<=50 and all(matched(v,r'0x[0-9a-fA-F]{40}') for v in rows) else None

    return out


def sanitize_agent_probe(value):
    if not isinstance(value,dict):raise EnvironmentError('Unexpected Agent probe shape')
    out={'status':'OBSERVED'}
    for field in ('config_status','registry_status'):
        out[field]=value.get(field) if value.get(field) in ('OBSERVED','UNAVAILABLE') else 'UNAVAILABLE'
    v=value.get('version');out['version']=v if isinstance(v,str) and re.fullmatch(r'7\.[0-9]{1,3}\.[0-9]{1,3}',v) else None
    for field in ('api_key_present','logs_enabled','collect_all','persistent_registry'):
        if type(value.get(field))is bool:out[field]=value[field]
    for field in ('registry_schema','registry_entries'):
        if type(value.get(field))is int and 0<=value[field]<1000000:out[field]=value[field]
    out['current_sources']=[]
    for row in value.get('current_sources',[])[:100] if isinstance(value.get('current_sources'),list) else []:
        if not isinstance(row,dict):continue
        offset=row.get('offset');mode=row.get('tailing_mode')
        out['current_sources'].append({'kind':row.get('kind') if row.get('kind') in ('file','other') else 'other',
            'offset':offset if isinstance(offset,str) and re.fullmatch(r'[0-9]{1,20}',offset) else None,
            'tailing_mode':mode if mode in (None,'','beginning','end') else '[custom]'})
    return out


def archived_image(root, image_id):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',str(image_id)):raise EnvironmentError('Invalid saved image identity')
    root=Path(root)
    if (root/'rollback').is_symlink():raise EnvironmentError('Symlinked archive directory')
    fd=os.open(root/'rollback/old-image.tar',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    deadline=time.monotonic()+10
    with os.fdopen(fd,'rb') as source:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):raise EnvironmentError('Nonregular image archive')
        with tarfile.open(fileobj=source,mode='r:') as archive:
            for index,member in enumerate(archive):
                if index>=512 or time.monotonic()>deadline:raise EnvironmentError('Image metadata scan bound reached')
                if member.name not in (image_id[7:]+'.json','blobs/sha256/'+image_id[7:]):continue
                if not member.isfile() or not 0<member.size<=MAX_BYTES:raise EnvironmentError('Image metadata shape unsupported')
                saved=archive.extractfile(member)
                with saved:raw=saved.read(MAX_BYTES+1)
                if 'sha256:'+hashlib.sha256(raw).hexdigest()!=image_id:raise EnvironmentError('Saved image config digest mismatch')
                value=json.loads(raw)
                if not isinstance(value.get('config'),dict):raise EnvironmentError('Saved image config missing')
                return {'Id':image_id,'Os':value.get('os'),'Architecture':value.get('architecture'),'Config':value['config']}
    raise EnvironmentError('Saved image metadata unavailable')


def find_previous_run(repo):
    base=Path.home()/'.local/share/bridge-ops'
    if any(p.is_symlink() for p in (Path.home()/'.local',Path.home()/'.local/share',base)):return None
    try:candidates=sorted(base.glob('eth-upgrade.*'),key=lambda p:p.lstat().st_mtime,reverse=True)[:32]
    except OSError:return None
    for root in candidates:
        try:
            info=root.lstat()
            if root.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:continue
            saved=json.loads(read_bounded(root,'upgrade-context.json',65536))
            if saved.get('CONFIG_DIR')!=str(Path(repo)/'federator-env/mainnet-ETH-RSK') or saved.get('FED_REPO')!=str(repo):continue
            item=root/'rollback/old-container.private.json'
            if item.is_symlink() or not item.is_file():continue
            return root
        except (OSError,ValueError,TypeError,AttributeError,EnvironmentError):continue
    return None


def collect(repo, runner, operator, container, image, previous_run=None, progress=None):
    if not re.fullmatch(r'fed_[1-5]',operator):raise EnvironmentError('Invalid anonymous operator label')
    report={'schema':SCHEMA,'utc':utc(),'operator':operator,'purpose':'ENVIRONMENT_CAPTURE_NOT_UPGRADE_APPROVAL',
        'deployment':sanitize_deployment(container,image,repo),'configuration':public_configuration(repo),
        'host':{'os':platform.system(),'architecture':platform.machine(),'uid':os.getuid(),'cpus':os.cpu_count()},
        'docker':{'status':'UNAVAILABLE'},'agent':{'status':'UNAVAILABLE'},'application_probe':{'status':'UNAVAILABLE'},
        'checks':[],'unchecked':['Signing key contents and AWS secret access','Etherscan credential validity','Historical RPC availability, live P2P connectivity and all transaction settlement','Datadog intake/indexing proof','Application upgrade and startup under replacement image']}
    def announce(message):
        if progress is not None:progress(message)
    deadline=time.monotonic()+90
    announce('Collecting Docker and Compose versions')
    def run(args,timeout=15):
        remaining=deadline-time.monotonic()
        if remaining<1:raise EnvironmentError('Collection deadline reached')
        return runner.run(args,timeout=min(timeout,remaining))
    try:
        value=json.loads(run(DOCKER+['version','--format','{{json .}}']))
        def version(x):
            found=re.match(r'\d+\.\d+(?:\.\d+)?',str(x or ''));return found[0] if found else None
        report['docker']={'status':'OBSERVED','server_version':version(value.get('Server',{}).get('Version')),'client_version':version(value.get('Client',{}).get('Version')),
            'server_api':version(value.get('Server',{}).get('ApiVersion')),'client_api':version(value.get('Client',{}).get('ApiVersion'))}
    except Exception:pass
    try:
        value=run(DOCKER+['compose','version']);match=re.search(r'v?(\d+\.\d+\.\d+)',value)
        report['docker']['compose_version']=match[1] if match else None
    except Exception:report['docker']['compose_version']=None
    announce('Collecting host resources and repository identity')
    try:
        commit=run(['git','-C',str(repo),'rev-parse','HEAD']).strip()
        report['host']['checkout_commit']=commit if re.fullmatch(r'[0-9a-f]{40}',commit) else None
    except Exception:report['host']['checkout_commit']=None
    try:
        disk=os.statvfs(repo)
        report['host'].update(free_disk_bytes=disk.f_bavail*disk.f_frsize,free_inodes=disk.f_favail)
    except OSError:pass
    try:
        release=read_bounded(Path('/etc'),'os-release',65536).decode()
        for key,target in (('ID','distribution'),('VERSION_ID','distribution_version')):
            match=re.search(r'^'+key+r'="?([a-zA-Z0-9_.-]{1,32})"?$',release,re.M)
            if match:report['host'][target]=match[1]
        kernel=re.match(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?',platform.release())
        report['host']['kernel_version']=kernel[0] if kernel else None
    except (OSError,ValueError,EnvironmentError):pass
    try:
        values=read_bounded(Path('/proc'),'meminfo',65536).decode()
        for name in ('MemTotal','MemAvailable','SwapTotal','SwapFree'):
            match=re.search(r'^'+name+r':\s*(\d+)\s+kB$',values,re.M)
            if match:report['host'][name+'_bytes']=int(match[1])*1024
    except (OSError,EnvironmentError):pass
    announce('Collecting application versions and public chain state; bounded read-only probe')
    try:
        value=json.loads(run(DOCKER+['exec','--env','NODE_OPTIONS=','--env','NODE_PATH=','--env','NODE_V8_COVERAGE=','--env','NODE_DEBUG=','--env','NODE_DEBUG_NATIVE=','--env','LD_PRELOAD=','--env','LD_LIBRARY_PATH=','--env','LD_AUDIT=',
            '--workdir','/app/federator',container['Id'],'/usr/local/bin/node','-e',NODE_PROBE],timeout=15))
        # The fixed probe emits only versions, public source hashes and two numeric RPC reads.
        expected={'status','node','arch','abi','packages','sources','rpc'}
        if not isinstance(value,dict) or set(value)-expected:raise EnvironmentError('Unexpected runtime output')
        report['application_probe']=sanitize_application_probe(value)
    except Exception:pass
    announce('Collecting Datadog version, credential presence and logging checkpoint metadata')
    try:
        agent=json.loads(run(DOCKER+['inspect','datadog-agent']))[0]
        safe_agent=sanitize_deployment(agent,{},repo,agent=True)['container']
        log_path=container.get('LogPath') or ''
        log_root=str(Path(log_path).parent.parent) if log_path else None
        mounts=agent.get('Mounts') or []
        def covered(path,m):
            source=m.get('Source') or ''
            return bool(path and source and (path==source.rstrip('/') or path.startswith(source.rstrip('/')+'/')))
        report['agent']={'status':'OBSERVED','deployment':safe_agent,'layout':{
            'docker_socket_present':any(m.get('Destination')=='/var/run/docker.sock' for m in mounts),
            'persistent_volume_present':any(m.get('Destination')=='/var/log/datadog' and m.get('Type')=='volume' for m in mounts),
            'current_log_file_covered':any(covered(log_path,m) for m in mounts),
            'replacement_log_root_covered':any(covered(log_root,m) for m in mounts)}}
        if agent.get('State',{}).get('Running'):
            value=json.loads(run(DOCKER+['exec','--env','LD_PRELOAD=','--env','LD_LIBRARY_PATH=','--env','LD_AUDIT=',
                '--env','PATH=/opt/datadog-agent/embedded/bin:/opt/datadog-agent/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                'datadog-agent','python3','-I','-B','-c',AGENT_PROBE,container['Id']],timeout=20))
            expected={'status','version','config_status','registry_status','api_key_present','logs_enabled','collect_all','persistent_registry','registry_schema','registry_entries','current_sources'}
            if not isinstance(value,dict) or set(value)-expected:raise EnvironmentError('Unexpected Agent output')
            report['agent']['collection']=sanitize_agent_probe(value)
    except Exception:pass
    announce('Checking that the source process stayed the same during capture')
    try:
        again=json.loads(run(DOCKER+['inspect','bridge-sc_federation_1']))[0]
        report['source_consistency']={'status':'MATCH' if all(again.get(k)==container.get(k) for k in ('Id','Image')) and
            again.get('State',{}).get('StartedAt')==container.get('State',{}).get('StartedAt') else 'CHANGED'}
    except Exception:report['source_consistency']={'status':'UNAVAILABLE'}
    if previous_run is None:previous_run=find_previous_run(repo)
    if previous_run is not None:
        announce('Collecting the retained original deployment; no image layers will be loaded')
        try:
            root=Path(previous_run).expanduser().absolute()
            if '..' in root.parts:raise EnvironmentError('History traversal refused')
            expected=Path.home()/'.local/share/bridge-ops'
            root.relative_to(expected)
            root.resolve().relative_to(expected.resolve())
            for part in (expected,root)+tuple(p for p in root.parents if p!=expected and expected in p.parents):
                if part.is_symlink():raise EnvironmentError('Symlinked history directory')
            info=root.lstat()
            if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:raise EnvironmentError('Nonprivate history directory')
            previous=json.loads(read_bounded(root,'rollback/old-container.private.json'))
            if isinstance(previous,list):
                if len(previous)!=1 or not isinstance(previous[0],dict):raise EnvironmentError('Saved inspection must identify exactly one container')
                previous=previous[0]
            if not isinstance(previous,dict):raise EnvironmentError('Malformed original container inspection')
            if not re.fullmatch(r'sha256:[0-9a-f]{64}',str(previous.get('Image'))):raise EnvironmentError('Invalid original image identity')
            try:
                old_image=json.loads(run(DOCKER+['image','inspect',previous['Image']]))[0]
                if old_image.get('Id')!=previous['Image']:raise EnvironmentError('Cached original image identity differs')
            except Exception:old_image=archived_image(root,previous['Image'])
            report['previous_deployment']=sanitize_deployment(previous,old_image,repo)
        except Exception:report['previous_deployment']={'status':'UNAVAILABLE'}
    return report


def write_private(path, body):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as out:
        out.write(body);out.flush();os.fsync(out.fileno())


def summary(report):
    lines=['Federator environment capture','UTC: '+str(report.get('utc','unknown')),
           'Purpose: deployment reproduction; this is not upgrade approval.','No production service was changed.']
    for item in report.get('checks',[]):
        lines.append(str(item.get('status','UNKNOWN'))+': '+str(item.get('summary','Check unavailable')))
    lines+=['','Not established by this capture:']+['- '+x for x in report.get('unchecked',[])]
    lines+=['','Send only federator-environment.zip. Do not attach raw config, logs, keys or databases.']
    return '\n'.join(lines)+'\n'


def write_bundle(report, output):
    output=Path(output).absolute()
    directory=os.open(output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        info=os.fstat(directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
            raise EnvironmentError('Output must be an owned private directory')
        body=(json.dumps(report,indent=2)+'\n').encode()
        if len(body)>MAX_BYTES:raise EnvironmentError('Capture exceeds report bound')
        contents={'environment.json':body,'summary.txt':summary(report).encode()}
        for name,data in contents.items():
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
            with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        name='federator-environment.zip'
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        with os.fdopen(fd,'wb') as out:
            with zipfile.ZipFile(out,'w') as bundle:
                for member,data in contents.items():
                    entry=zipfile.ZipInfo(member,date_time=datetime.now(timezone.utc).timetuple()[:6])
                    entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o600<<16
                    bundle.writestr(entry,data)
            out.flush();os.fsync(out.fileno())
        now=output.lstat()
        if (now.st_dev,now.st_ino)!=(info.st_dev,info.st_ino):raise EnvironmentError('Output directory changed')
        return output/name
    finally:os.close(directory)


def load_replay(path):
    path=Path(path).absolute()
    value=json.loads(read_bounded(path.parent,path.name))
    if not isinstance(value,dict) or type(value.get('schema'))is not int or value.get('schema')!=SCHEMA or not isinstance(value.get('deployment'),dict):
        raise EnvironmentError('Unsupported replay packet')
    d=value['deployment']
    if not all(isinstance(d.get(k),dict) for k in ('container','image')) or not isinstance(d.get('repo'),str):
        raise EnvironmentError('Malformed deployment fixture')
    return value
