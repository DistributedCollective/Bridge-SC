#!/usr/bin/env python3
"""Bounded local federator/Datadog observations; never repairs the application."""
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import secrets
import signal
import stat
import subprocess
import sys
import time

import federator_dependencies as fd

VERSION = '1.0.2'
SITES = ('datadoghq.com', 'datadoghq.eu', 'us3.datadoghq.com', 'us5.datadoghq.com',
         'ap1.datadoghq.com', 'ap2.datadoghq.com', 'uk1.datadoghq.com', 'ddog-gov.com', 'us2.ddog-gov.com')
OPERATORS = ('fed_2', 'fed_1', 'fed_3', 'fed_4', 'fed_5', 'unspecified')
CID = re.compile(r'[0-9a-f]{64}\Z')
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')

class ProbeError(fd.DiagnosticError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

class Runner:
    """Stream-cap both pipes and kill the local command group on deadline/overflow."""
    deadline = None
    cancelled = None
    def run(self, args, timeout=10, input_text=None, limit=1024*1024):
        if self.cancelled and self.cancelled():raise ProbeError('INTERRUPTED')
        if args[0] == 'docker':
            args = ['docker', '--host', 'unix:///var/run/docker.sock'] + list(args[1:])
        budget = min(timeout, self.deadline-time.monotonic()) if self.deadline is not None else timeout
        if budget <= 0:
            raise ProbeError('DEADLINE')
        payload = (input_text or '').encode('utf-8')
        if len(payload) > 256*1024:
            raise ProbeError('INPUT_LIMIT')
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True)
        except OSError:
            raise ProbeError('COMMAND_UNAVAILABLE') from None
        sel = selectors.DefaultSelector()
        output, total, pos = [], 0, 0
        deadline = time.monotonic()+budget
        try:
            for pipe in (proc.stdout, proc.stderr):
                os.set_blocking(pipe.fileno(), False)
                sel.register(pipe, selectors.EVENT_READ)
            if payload:
                os.set_blocking(proc.stdin.fileno(), False)
                sel.register(proc.stdin, selectors.EVENT_WRITE)
            else:
                proc.stdin.close()
            while sel.get_map():
                if self.cancelled and self.cancelled():raise ProbeError('INTERRUPTED')
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise ProbeError('TIMEOUT')
                for key, _ in sel.select(min(.1, remaining)):
                    pipe = key.fileobj
                    if pipe is proc.stdin:
                        try:
                            pos += os.write(pipe.fileno(), payload[pos:pos+4096])
                        except BrokenPipeError:
                            pos = len(payload)
                        if pos == len(payload):
                            sel.unregister(pipe); pipe.close()
                    else:
                        chunk = os.read(pipe.fileno(), 4096)
                        if not chunk:
                            sel.unregister(pipe); pipe.close(); continue
                        total += len(chunk)
                        if total > limit:
                            raise ProbeError('OUTPUT_LIMIT')
                        # Never let stderr contaminate a JSON response; it still counts toward the cap.
                        if pipe is proc.stdout or args[3:4] == ['logs']:
                            output.append(chunk)
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise ProbeError('TIMEOUT')
            if proc.wait(timeout=remaining) != 0:
                raise ProbeError('COMMAND_FAILED')
            return b''.join(output).decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            raise ProbeError('TIMEOUT') from None
        finally:
            # The group may still own live descendants after the direct child exits.
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
            sel.close()
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if not pipe.closed: pipe.close()

def no_symlinks(path):
    path = Path(os.path.abspath(str(Path(path).expanduser())))
    for part in reversed((path,) + tuple(path.parents)):
        if part.is_symlink(): raise ProbeError('SYMLINK_PATH')
    return path

def parent_fd(path, create=False):
    path = no_symlinks(path)
    current = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            if create:
                try: os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError: pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current); current = child
        return current
    except OSError:
        os.close(current); raise ProbeError('PATH_UNAVAILABLE') from None

class Store:
    def __init__(self, root, segment_limit=8*1024*1024):
        self.root = no_symlinks(root)
        self.segment_limit = segment_limit
        parent = parent_fd(self.root, create=True)
        try:
            try: os.mkdir(self.root.name, 0o700, dir_fd=parent)
            except FileExistsError: raise ProbeError('OUTPUT_EXISTS') from None
            self.fd = os.open(self.root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        finally: os.close(parent)
        meta = os.fstat(self.fd); self.identity = (meta.st_dev, meta.st_ino)
    def __del__(self):
        if hasattr(self, 'fd'):
            try: os.close(self.fd)
            except OSError: pass
    def guard(self):
        no_symlinks(self.root)
        meta = os.fstat(self.fd)
        if (meta.st_dev, meta.st_ino) != self.identity or meta.st_uid != os.getuid() or meta.st_mode & 0o777 != 0o700:
            raise ProbeError('OUTPUT_REPLACED')
    def append(self, record):
        self.guard()
        data = (json.dumps(record,separators=(',',':'),sort_keys=True)+'\n').encode()
        if len(data) > self.segment_limit: raise ProbeError('RECORD_LIMIT')
        name = 'timeline.jsonl'
        try:
            meta = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o777 != 0o600:
                raise ProbeError('TIMELINE_PERMISSIONS')
            if meta.st_size + len(data) > self.segment_limit:
                os.rename(name, 'timeline.previous.jsonl', src_dir_fd=self.fd, dst_dir_fd=self.fd)
        except FileNotFoundError: pass
        f = os.open(name, os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        with os.fdopen(f, 'ab') as out:
            meta = os.fstat(out.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o777 != 0o600: raise ProbeError('TIMELINE_PERMISSIONS')
            out.write(data)
    def atomic(self, name, text):
        self.guard()
        temporary = '.'+name+'.'+secrets.token_hex(6)
        f = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
        with os.fdopen(f,'w') as out:out.write(text)
        os.rename(temporary,name,src_dir_fd=self.fd,dst_dir_fd=self.fd)
    def write(self, report):
        data = json.dumps(report,indent=2,sort_keys=True)
        if len(data.encode()) > 4*1024*1024: raise ProbeError('REPORT_LIMIT')
        self.atomic('report.json',data+'\n');self.atomic('summary.md',summary(report))

def summary(report):
    last=report.get('samples',[{}])[-1] if report.get('samples') else {}
    lines=['# Federator watcher', '', 'Status: '+last.get('assessment',{}).get('status','UNKNOWN'),
        'Started UTC: '+report.get('started','UNKNOWN'), 'Finished UTC: '+report.get('finished','IN PROGRESS'),
        'Samples retained: '+str(len(report.get('samples',[]))), '',
        'Direct HTTP202 proves intake acceptance only. Aggregate Agent counters are not source delivery proof.',
        'Missing/error/empty search evidence is unknown. Single-host peer timing does not establish historical cause.', '']
    rows=report.get('samples',[])
    observations=[]
    for row in rows:
        for kind in ('source','agent'):
            state=row.get(kind,{})
            if state.get('running') is False or state.get('oom') or row.get(kind+'_changed_during_sample'):
                observations.append(row.get('utc','UNKNOWN')+' '+kind+' '+state.get('status','unknown')+(' OOM' if state.get('oom') else '')+(' identity changed' if row.get(kind+'_changed_during_sample') else ''))
        for event in row.get('events',{}).get('events',[]):
            observations.append(event.get('utc','UNKNOWN')+' '+event.get('role','unknown')+' '+event.get('action','unknown'))
    if observations:lines+=['', 'Observed lifecycle findings:']+list(dict.fromkeys(observations))[-20:]
    classes={}
    for row in rows:
        for item in row.get('markers',[]):classes.setdefault(item['class'],[]).append(item['utc'])
    historical=report.get('historical',{})
    for row in historical.get('containers',{}).values():
        for item in row.get('markers',[]):classes.setdefault(item['class'],[]).append(item['utc'])
    if classes:
        lines+=['','Observed application markers:']
        for cls,stamps in sorted(classes.items()):lines.append(cls+': '+str(len(stamps))+' observations, '+min(stamps)+' to '+max(stamps))
    deep=report.get('deep',[])
    if deep:
        failed=[x for x in deep[-1].get('evidence',{}).get('checks',[]) if x.get('status') in ('FAIL','WARN','SKIP')]
        if failed:
            lines+=['','Latest dependency checks requiring attention:']
            for check in failed[:30]:lines.append(str(check.get('name','unknown'))+' '+check['status']+' '+str(check.get('failure','')))
            lines.append('Check failed RPC/fee/history/contract boundaries before expecting scan/signature progress; no transaction was sent.')
    if report.get('merged_timeline'):
        lines+=['','Merged marker chronology (UTC, correlation only):']
        for item in report['merged_timeline'][-30:]:lines.append(item['utc']+' '+item['operator']+' '+item['class']+' ('+item['scope']+')')
    for kind,result in report.get('tests',{}).items():
        lines.append(kind+': '+str(result.get('status','UNKNOWN')))
    for name,query in report.get('human_queries',{}).items():lines.append(name+': `'+query+'`')
    actions = {
        'SOURCE_NOT_RUNNING': 'Check the federator exit/OOM and current application markers before arranging any operator restart.',
        'SOURCE_MISSING': 'Check whether the named federator container was removed or its deployment name changed.',
        'AGENT_MISSING': 'Check the Agent container deployment name and Docker access; no collection proof is available.',
        'AGENT_NOT_RUNNING': 'Check the Agent container exit/OOM evidence; direct intake does not repair the Agent sender.',
        'SOURCE_PROFILE_UNVERIFIED': 'Check that config/database mounts match the selected profile; deep probes were withheld.',
        'CONTAINER_CHANGED_DURING_SAMPLE': 'Check the next stable container epoch; this sample cannot prove source-specific delivery.',
        'APPLICATION_MARKERS': 'Check the UTC marker timeline and dependency failures; cross-node timing remains correlation.',
        'DELIVERY_REQUIRES_SOURCE_SPECIFIC_EVIDENCE': 'Check exact source/canary search visibility and source-specific tailer deltas; aggregate counters alone are insufficient.'}
    lines += ['', '## Next checks', '', actions.get(last.get('assessment',{}).get('reason'), 'Check unavailable observations before drawing a health conclusion.')]
    collection=last.get('collection',{})
    if collection.get('site_status') in ('MISMATCH','UNKNOWN'):lines.append('Check Agent DD_SITE against its effective Logs Agent endpoint; authenticated probes were withheld.')
    if collection.get('api_key_status')=='INVALID':lines.append('Check the Agent API key authorization and intended Datadog organization; do not substitute a signing key.')
    for hypothesis in last.get('delta',{}).get('hypotheses',[]):
        if hypothesis=='COLLECTION_STALL':lines.append('Source bytes grew while source-specific reading did not: check tailer registration, readability, filters and sender backpressure.')
        if hypothesis=='SENDER_STALL':lines.append('Aggregate processing advanced while sending did not: check Agent auth, network and forwarder retry/drop counters.')
    return '\n'.join(lines)+'\n'

def read_app_key(path):
    path=no_symlinks(path)
    if path.name!='datadog-read.key':raise ProbeError('READ_KEY_PATH')
    parent=parent_fd(path) if path.parent.exists() else None
    if parent is None:return None
    try: f=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
    except FileNotFoundError:return None
    except OSError:raise ProbeError('READ_KEY_UNAVAILABLE') from None
    finally:os.close(parent)
    with os.fdopen(f,'rb') as out:
        meta=os.fstat(out.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.getuid() or meta.st_mode&0o777!=0o600 or meta.st_size>512:
            raise ProbeError('READ_KEY_PERMISSIONS')
        value=out.read(513).decode('ascii',errors='replace').strip()
    if not re.fullmatch(r'[0-9a-fA-F]{40}',value):raise ProbeError('READ_KEY_SHAPE')
    return value

def markers(text, started=None):
    rows=text.splitlines()[-2000:]
    out=[]
    patterns=(('DNS_ERROR',r'\b(?:ENOTFOUND|EAI_AGAIN)\b'),
        ('PROCESS_FATAL',r'uncaughtException|UnhandledPromiseRejection|npm ERR!|FATAL ERROR|heap out of memory'),
        ('MISSING_KEY',r'ENOENT.*federator\.key'))
    known=('RSKKeyedAuthTCPTransport.addPeer','Buffer.concat','sendInitialAuth','receiveAuth','GasPriceFetcher','TransactionSender','Federator','Scheduler')
    for n,row in enumerate(rows):
        stamp=fd.parse_time(row.split(' ',1)[0])
        if stamp is None or (started is not None and stamp < started):continue
        nearby='\n'.join(rows[n:n+12])
        classes=[]
        if 'TypeError' in row and ('RSKKeyedAuth' in nearby or ('Buffer.concat' in nearby and 'null' in row)):
            classes.append('AUTH_STREAM_NULL')
        # A subsystem name or signing request is not evidence of a failure.
        message=re.sub(r'(?:\x1b)?\[[0-9;]*m','',row)
        problem=re.search(r'(?i)\[(?:ERROR|FATAL|WARN)\]|\b(?:error|failed|failure|invalid|unavailable|deprecated|stale|timeout|rejected|insufficient)\b|\b(?:timed out|not enough|not ready|not available)\b',message)
        if problem:
            if re.search(r'(?i)etherscan|gaspricefetcher|gaspriceavg|gasservices|fee readiness|base fee',message):
                classes.append('GAS_ERROR')
            if re.search(r'(?i)signature|getTransactionIdU',message):
                classes.append('SIGNATURE_ERROR')
        classes.extend(name for name,pat in patterns if re.search(pat,row))
        for cls in classes:
            out.append({'utc':stamp.isoformat().replace('+00:00','Z'),'class':cls,
                'frames':[frame for frame in known if frame in nearby][:8]})
    return out[-100:]

def epoch_since(session,started):
    instants=[fd.parse_time(x) for x in (session,started)]
    if any(x is None for x in instants):raise ProbeError('PROCESS_TIME_UNVERIFIED')
    return max(instants).isoformat().replace('+00:00','Z')

def compare(old,new):
    out={'hypotheses':[],'confidence':'LOW','aggregate':{},'source_delivery':'UNKNOWN'}
    for name in ('source','agent'):
        before=old.get(name,{}) or {};after=new.get(name,{}) or {}
        out[name+'_epoch']='SAME' if before.get('id') and all(before.get(k)==after.get(k) for k in ('id','started')) else 'CHANGED'
    if out['source_epoch']!='SAME' or out['agent_epoch']!='SAME':
        out['hypotheses'].append('CONTAINER_EPOCH_CHANGED');return out
    before=old.get('collection',{});after=new.get('collection',{})
    out['reader_epoch']='SAME' if before.get('source_inode')==after.get('source_inode') else 'CHANGED'
    if out['reader_epoch']=='CHANGED':
        out['hypotheses'].append('SOURCE_FILE_ROTATION');return out
    if new.get('source_changed_during_sample') or new.get('agent_changed_during_sample'):
        out['hypotheses'].append('CONTAINER_EPOCH_CHANGED');return out
    for key,val in after.get('counters',{}).items():
        prev=before.get('counters',{}).get(key)
        if type(val)is int and type(prev)is int:out['aggregate'][key]=val-prev if val>=prev else 'RESET'
    for key in ('source_bytes','tailer_bytes'):
        a,b=before.get(key),after.get(key)
        out[key+'_delta']=b-a if type(a)is int and type(b)is int and b>=a else ('ROTATED_OR_RESET' if type(a)is int and type(b)is int else None)
    if out.get('source_bytes_delta',0) and isinstance(out['source_bytes_delta'],int) and out['source_bytes_delta']>0 and out.get('tailer_bytes_delta')==0:
        out['hypotheses'].append('COLLECTION_STALL')
    if type(out['aggregate'].get('LogsProcessed'))is int and out['aggregate']['LogsProcessed']>0 and out['aggregate'].get('LogsSent')==0:
        out['hypotheses'].append('SENDER_STALL')
    if 'RESET' in out['aggregate'].values():out['hypotheses'].append('COUNTER_RESET')
    return out

def assess(sample):
    source=sample.get('source',{});agent=sample.get('agent',{})
    if source.get('running') is False:return {'status':'FAIL','reason':'SOURCE_NOT_RUNNING'}
    if source.get('status')=='missing':return {'status':'FAIL','reason':'SOURCE_MISSING'}
    if agent.get('status')=='missing':return {'status':'FAIL','reason':'AGENT_MISSING'}
    if agent.get('running') is False:return {'status':'FAIL','reason':'AGENT_NOT_RUNNING'}
    if sample.get('source_guard')=='FAIL':return {'status':'FAIL','reason':'SOURCE_PROFILE_UNVERIFIED'}
    if sample.get('source_changed_during_sample') or sample.get('agent_changed_during_sample'):return {'status':'FAIL','reason':'CONTAINER_CHANGED_DURING_SAMPLE'}
    if sample.get('markers'):return {'status':'WARN','reason':'APPLICATION_MARKERS'}
    return {'status':'UNKNOWN','reason':'DELIVERY_REQUIRES_SOURCE_SPECIFIC_EVIDENCE'}

def arguments(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operator',choices=OPERATORS,default='unspecified')
    p.add_argument('--profile',choices=tuple(fd.PROFILES),default='eth-rsk')
    p.add_argument('--repo',default='~/Bridge-SC');p.add_argument('--container',default='bridge-sc_federation_1')
    p.add_argument('--agent',default='datadog-agent');p.add_argument('--duration',type=int,default=900)
    p.add_argument('--interval',type=int,default=60);p.add_argument('--deep-every',type=int,default=300,help='deep dependency checks every 60..86400 seconds (default 300)')
    p.add_argument('--output-dir');p.add_argument('--dd-app-key-file',default='~/.config/bridge-eth/datadog-read.key')
    p.add_argument('--incident-since');p.add_argument('--incident-until');p.add_argument('--analyze',nargs='+')
    args=p.parse_args(argv)
    if args.duration<0 or args.duration>86400 or not 1<=args.interval<=3600 or not 60<=args.deep_every<=86400:p.error('Invalid observation bounds')
    for name in ('container','agent'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',getattr(args,name)):p.error('Invalid container name')
    if bool(args.incident_since)!=bool(args.incident_until):p.error('Historical window needs both UTC endpoints')
    for field in ('incident_since','incident_until'):
        value=getattr(args,field)
        if value and (not value.endswith('Z') or fd.parse_time(value) is None):p.error('Historical timestamps must be explicit UTC Z instants')
    if args.incident_since and fd.parse_time(args.incident_since)>=fd.parse_time(args.incident_until):p.error('Invalid historical window')
    return args

# Fixed code runs only in the existing Agent. No credential is put in argv or env overrides.
AGENT_CODE = r'''
import json, os, re, selectors, signal, socket, ssl, stat, subprocess, sys, threading, time
import urllib.request, urllib.error
from datetime import datetime, timezone
SITES=('datadoghq.com','datadoghq.eu','us3.datadoghq.com','us5.datadoghq.com','ap1.datadoghq.com','ap2.datadoghq.com','uk1.datadoghq.com','ddog-gov.com','us2.ddog-gov.com')
COUNTERS=('LogsProcessed','LogsSent','LogsDropped','BytesSent','BytesSentUncompressed','RetryQueueSize','Dropped','Retries','RetryCount','DroppedCount')

def parse_status(raw,cid,configured):
    hosts=re.findall(r'(?<![A-Za-z0-9.-])(?:agent-http-intake|http-intake)\.logs\.([a-z0-9.-]+)',raw)
    sites=sorted(set(x.rstrip('.') for x in hosts if x.rstrip('.') in SITES))
    site=sites[0] if len(sites)==1 else None
    env_site=configured.strip() or 'datadoghq.com'
    out={'site':site,'site_status':'MATCH' if site==env_site else ('MISMATCH' if site else 'UNKNOWN'),
         'source_registered':cid in raw if cid else None,'tailer_bytes':None,'counters':{},'api_key_status':'UNKNOWN'}
    for key in COUNTERS:
        m=re.search(r'(?m)^\s*'+key+r'\s*:\s*([0-9][0-9,]*)\s*$',raw)
        if m:out['counters'][key]=int(m.group(1).replace(',',''))
    if re.search(r'(?i)API key[^\n]*(?:invalid|unauthor|forbidden)',raw):out['api_key_status']='INVALID'
    elif re.search(r'(?i)API key[^\n]*valid',raw):out['api_key_status']='VALID'
    # A source-specific byte count is used only under an exact source identity.
    blocks=re.split(r'\n\s*\n|(?=^\s*Type:)',raw,flags=re.M)
    matches=[]
    for block in blocks:
        identities=set(re.findall(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',block))
        if cid and identities=={cid}:
            values=re.findall(r'\bBytes Read\s*:\s*([0-9][0-9,]*)',block)
            if len(values)==1:matches.append(int(values[0].replace(',','')))
    if len(matches)==1:out['tailer_bytes']=matches[0]
    return out

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def search_result(body,kind=None,identifier=None,since=None):
    if not isinstance(body,dict) or not isinstance(body.get('data'),list):return {'status':'UNKNOWN','failure':'JSON_SHAPE'}
    rows=body['data']
    if len(rows)>100:return {'status':'UNKNOWN','failure':'RESPONSE_LIMIT'}
    stamps=[];matched=0
    for row in rows:
        attributes=row.get('attributes') if isinstance(row,dict) else None
        value=attributes.get('timestamp') if isinstance(attributes,dict) else None
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z',value):return {'status':'UNKNOWN','failure':'JSON_SHAPE'}
        try:instant=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:return {'status':'UNKNOWN','failure':'JSON_SHAPE'}
        if since and instant<datetime.fromisoformat(since.replace('Z','+00:00')):continue
        if kind in ('direct','canary'):
            message=attributes.get('message','')
            if not isinstance(message,str) or not re.search(r'(?<![A-Za-z0-9_-])'+re.escape(identifier)+r'(?![A-Za-z0-9_-])',message) or attributes.get('service')!='bridge-federator-watcher':continue
        elif kind=='source':
            fields=attributes.get('attributes',{})
            if not isinstance(fields,dict):continue
            container=fields.get('container',{})
            ids=[fields.get('container_id'),container.get('id') if isinstance(container,dict) else None]
            tags=attributes.get('tags',[])
            if identifier not in ids and ('container_id:'+identifier) not in (tags if isinstance(tags,list) else []):continue
        matched+=1;stamps.append(instant.isoformat().replace('+00:00','Z'))
    return {'status':'FOUND' if matched else 'UNKNOWN','count':matched,'count_is_lower_bound':len(rows)==100,
        'first_utc':min(stamps) if stamps else None,'last_utc':max(stamps) if stamps else None}

def safe_flags():
    out={}
    for key in ('DD_LOGS_ENABLED','DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL','DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE','DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE'):
        val=os.environ.get(key,'').strip().lower()
        out[key]='TRUE' if val=='true' else ('FALSE' if val=='false' else 'UNKNOWN')
    out['exclusion_present']=bool(os.environ.get('DD_CONTAINER_EXCLUDE') or os.environ.get('DD_CONTAINER_EXCLUDE_LOGS'))
    out['inclusion_present']=bool(os.environ.get('DD_CONTAINER_INCLUDE_LOGS'))
    out['proxy_present']=any(os.environ.get(k) for k in ('HTTP_PROXY','HTTPS_PROXY','DD_PROXY_HTTP','DD_PROXY_HTTPS'))
    return out

def status_read(cid,source_path=None):
    proc=subprocess.Popen(['agent','status'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
    out=[];total=0;sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ);deadline=time.monotonic()+8
    try:
        os.set_blocking(proc.stdout.fileno(),False)
        while sel.get_map():
            if time.monotonic()>=deadline:return {'status':'UNKNOWN','failure':'STATUS_TIMEOUT'}
            for key,_ in sel.select(.1):
                chunk=os.read(key.fileobj.fileno(),4096)
                if not chunk:sel.unregister(key.fileobj);continue
                total+=len(chunk)
                if total>1024*1024:return {'status':'UNKNOWN','failure':'STATUS_LIMIT'}
                out.append(chunk)
        if proc.wait(timeout=max(.01,deadline-time.monotonic()))!=0:return {'status':'UNKNOWN','failure':'STATUS_UNAVAILABLE'}
        result=parse_status(b''.join(out).decode('utf8','replace'),cid,os.environ.get('DD_SITE',''))
        result['status']='OBSERVED';result['flags']=safe_flags()
        result['agent_docker_socket_present']=os.path.exists('/var/run/docker.sock')
        if cid and re.fullmatch('[0-9a-f]{64}',cid):
            path=source_path
            if not isinstance(path,str) or not path.endswith('/containers/'+cid+'/'+cid+'-json.log') or not path.startswith(('/var/lib/docker/containers/','/host/var/lib/docker/containers/')):
                result['source_readable']=None;return result
            try:
                parts=path.split('/')
                if any(os.path.islink('/'.join(parts[:n])) for n in range(2,len(parts)+1)):raise OSError()
                meta=os.lstat(path)
                if stat.S_ISREG(meta.st_mode):
                    f=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                    with os.fdopen(f,'rb') as stream:
                        s=os.fstat(stream.fileno())
                        result.update(source_bytes=s.st_size,source_mtime_utc=datetime.fromtimestamp(s.st_mtime,timezone.utc).isoformat().replace('+00:00','Z'),source_inode=s.st_ino,source_readable=True)
                else:result['source_readable']=False
            except OSError:result['source_readable']=False
        return result
    finally:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait();proc.stdout.close();sel.close()

def perform(p):
    if p.get('op')=='snapshot':return status_read(p.get('cid',''),p.get('source_path'))
    site=p.get('site');configured=os.environ.get('DD_SITE','').strip() or 'datadoghq.com'
    if site not in SITES or configured!=site:return {'status':'UNKNOWN','failure':'SITE_MISMATCH'}
    key=os.environ.get('DD_API_KEY','').strip()
    if not re.fullmatch(r'[0-9a-fA-F]{32}',key):return {'status':'UNKNOWN','failure':'API_KEY_SHAPE'}
    headers={'Content-Type':'application/json','DD-API-KEY':key}
    if p.get('op')=='direct':
        marker=p.get('marker','');operator=p.get('operator','')
        if not re.fullmatch(r'fw-direct-[0-9a-f]{24}',marker) or operator not in ('fed_2','fed_1','fed_3','fed_4','fed_5','unspecified'):return {'status':'UNKNOWN','failure':'INPUT_SHAPE'}
        payload=[{'message':marker+' synthetic watcher intake test','service':'bridge-federator-watcher','ddsource':'federator-watcher','ddtags':'diagnostic:true,operator:'+operator}]
        body=json.dumps(payload,separators=(',',':')).encode()
        if len(body)>=1024:return {'status':'UNKNOWN','failure':'INPUT_LIMIT'}
        url='https://http-intake.logs.'+site+'/api/v2/logs'
    elif p.get('op')=='search':
        app=p.get('app_key','')
        if not re.fullmatch(r'[0-9a-fA-F]{40}',app):return {'status':'UNKNOWN','failure':'READ_KEY_SHAPE'}
        headers['DD-APPLICATION-KEY']=app
        kind=p.get('kind');identifier=p.get('identifier','');since=p.get('since','')
        if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z',since):return {'status':'UNKNOWN','failure':'INPUT_SHAPE'}
        if kind in ('direct','canary') and re.fullmatch(r'fw-(?:direct|canary-marker)-[0-9a-f]{24}',identifier):query='service:bridge-federator-watcher "'+identifier+'"'
        elif kind=='source' and re.fullmatch(r'[0-9a-f]{64}',identifier):query='container_id:'+identifier
        else:return {'status':'UNKNOWN','failure':'INPUT_SHAPE'}
        body=json.dumps({'filter':{'query':query,'from':since,'to':'now'},'page':{'limit':100},'sort':'timestamp'}).encode()
        url='https://api.'+site+'/api/v2/logs/events/search'
    else:return {'status':'UNKNOWN','failure':'INPUT_SHAPE'}
    try:
        request=urllib.request.Request(url,data=body,headers=headers,method='POST')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(request,timeout=7) as response:
            code=response.status
            if p['op']=='direct':return {'status':'ACCEPTED' if code==202 else 'UNKNOWN','http_status':code}
            raw=response.read(128*1024+1)
            if len(raw)>128*1024:return {'status':'UNKNOWN','failure':'RESPONSE_LIMIT','http_status':code}
            try:result=search_result(json.loads(raw),p.get('kind'),p.get('identifier'),p.get('since'))
            except (ValueError,TypeError):result={'status':'UNKNOWN','failure':'JSON_SHAPE'}
            result['http_status']=code;return result
    except urllib.error.HTTPError as exc:
        code=exc.code;exc.close();return {'status':'UNKNOWN','failure':'HTTP_STATUS','http_status':code}
    except (socket.timeout,TimeoutError):return {'status':'UNKNOWN','failure':'TIMEOUT'}
    except urllib.error.URLError as exc:
        reason=exc.reason
        failure='DNS' if isinstance(reason,socket.gaierror) else ('TLS' if isinstance(reason,ssl.SSLError) else ('TIMEOUT' if isinstance(reason,(TimeoutError,socket.timeout)) else 'NETWORK'))
        return {'status':'UNKNOWN','failure':failure}
    except (ValueError,TypeError):return {'status':'UNKNOWN','failure':'INPUT_SHAPE'}
    except Exception:return {'status':'UNKNOWN','failure':'NETWORK'}

if __name__=='__main__':
    # This handler belongs solely to this disposable diagnostic process, not the application.
    def deadline():
        sys.stdout.write('{"status":"UNKNOWN","failure":"AGENT_DEADLINE"}\n');sys.stdout.flush();os._exit(0)
    watchdog=threading.Timer(12,deadline);watchdog.daemon=True;watchdog.start()
    try:
        data=sys.stdin.buffer.read(4097)
        result=perform(json.loads(data)) if len(data)<=4096 else {'status':'UNKNOWN','failure':'INPUT_LIMIT'}
    except Exception:result={'status':'UNKNOWN','failure':'INPUT_SHAPE'}
    sys.stdout.write(json.dumps(result,separators=(',',':'))+'\n');sys.stdout.flush();os._exit(0)
'''

def agent_call(runner,identity,payload):
    if not CID.fullmatch(identity):raise ProbeError('AGENT_IDENTITY')
    try:
        raw=runner.run(['docker','exec','-i',identity,'/opt/datadog-agent/embedded/bin/python','-c',AGENT_CODE],
            timeout=14,input_text=json.dumps(payload,separators=(',',':')),limit=16384)
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValueError()
        return clean_agent(result)
    except (fd.DiagnosticError,ValueError,TypeError):return {'status':'UNKNOWN','failure':'AGENT_PROBE_UNAVAILABLE'}

def clean_agent(value):
    fixed={'status':('OBSERVED','UNKNOWN','FOUND','ACCEPTED'),'failure':('SITE_MISMATCH','API_KEY_SHAPE','READ_KEY_SHAPE','INPUT_SHAPE','INPUT_LIMIT','RESPONSE_LIMIT','JSON_SHAPE','HTTP_STATUS','DNS','TLS','TIMEOUT','NETWORK','AGENT_DEADLINE','STATUS_TIMEOUT','STATUS_LIMIT','STATUS_UNAVAILABLE','AGENT_PROBE_UNAVAILABLE'),
        'site_status':('MATCH','MISMATCH','UNKNOWN'),'api_key_status':('VALID','INVALID','UNKNOWN')}
    out={}
    for key,choices in fixed.items():
        if value.get(key) in choices:out[key]=value[key]
    if value.get('site') in SITES:out['site']=value['site']
    for key in ('source_bytes','source_inode','tailer_bytes','http_status','count'):
        if type(value.get(key))is int and 0<=value[key]<2**63:out[key]=value[key]
    for key in ('source_readable','source_registered','count_is_lower_bound'):
        if type(value.get(key))is bool:out[key]=value[key]
    for key in ('source_mtime_utc','first_utc','last_utc'):
        if isinstance(value.get(key),str) and fd.parse_time(value[key]):out[key]=fd.parse_time(value[key]).isoformat().replace('+00:00','Z')
    counters=value.get('counters',{})
    if isinstance(counters,dict):out['counters']={k:v for k,v in counters.items() if k in ('LogsProcessed','LogsSent','LogsDropped','BytesSent','BytesSentUncompressed','RetryQueueSize','Dropped','Retries','RetryCount','DroppedCount') and type(v)is int and 0<=v<2**63}
    flags=value.get('flags',{})
    if isinstance(flags,dict):
        out['flags']={k:v for k,v in flags.items() if (k in ('DD_LOGS_ENABLED','DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL','DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE','DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE') and v in ('TRUE','FALSE','UNKNOWN')) or (k in ('exclusion_present','inclusion_present','proxy_present') and type(v)is bool)}
    if type(value.get('agent_docker_socket_present'))is bool:out['agent_docker_socket_present']=value['agent_docker_socket_present']
    out.setdefault('status','UNKNOWN')
    return out

STATE_FORMAT='{"id":{{json .Id}},"status":{{json .State.Status}},"running":{{json .State.Running}},"started":{{json .State.StartedAt}},"finished":{{json .State.FinishedAt}},"exit":{{.State.ExitCode}},"oom":{{.State.OOMKilled}},"restarts":{{.RestartCount}},"image_id":{{json .Image}}}'

def state(runner,name):
    try:
        v=json.loads(runner.run(['docker','inspect',name,'--format',STATE_FORMAT],timeout=4,limit=4096))
        if not CID.fullmatch(v.get('id','')) or not IMAGE.fullmatch(v.get('image_id','')):raise ValueError()
        if v.get('status') not in ('running','exited','created','dead','restarting','paused','removing') or type(v.get('running'))is not bool:raise ValueError()
        for k in ('exit','restarts'):
            if type(v.get(k))is not int or v[k]<0:raise ValueError()
        if type(v.get('oom'))is not bool:raise ValueError()
        for k in ('started','finished'):
            if not isinstance(v.get(k),str) or fd.parse_time(v[k]) is None:raise ValueError()
        return {k:v[k] for k in ('id','status','running','started','finished','exit','oom','restarts','image_id')}
    except (fd.DiagnosticError,ValueError,KeyError,TypeError):
        try:
            names=runner.run(['docker','ps','--all','--filter','name=^/'+name+'$','--format','{{.Names}}'],timeout=2,limit=1024).strip()
            if not names:return {'status':'missing','running':None,'failure':'CONFIRMED_NAME_ABSENT'}
        except fd.DiagnosticError:pass
        return {'status':'unknown','running':None,'failure':'INSPECTION_UNAVAILABLE'}

class Canary:
    FORMAT='{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},"label":{{json (index .Config.Labels "bridge.watcher.owner")}},"mounts":{{json .Mounts}},"network":{{json .HostConfig.NetworkMode}}}'
    def __init__(self,runner,name):
        if not re.fullmatch(r'fw-canary-[0-9a-f]{24}',name):raise ProbeError('CANARY_NAME')
        self.runner,self.name,self.identity,self.image=runner,name,None,None
        self.created=None;self.attempted=False;self.cancelled=None
    def create(self,image,marker):
        if self.cancelled and self.cancelled():raise ProbeError('INTERRUPTED')
        if not IMAGE.fullmatch(image) or not re.fullmatch(r'fw-canary-marker-[0-9a-f]{24}',marker):raise ProbeError('CANARY_INPUT')
        try:
            actual=json.loads(self.runner.run(['docker','image','inspect',image,'--format','{"id":{{json .Id}},"volumes":{{json .Config.Volumes}}}'],timeout=4,limit=4096))
        except (ValueError,TypeError):raise ProbeError('IMAGE_NOT_LOCAL') from None
        if not isinstance(actual,dict) or actual.get('id')!=image:raise ProbeError('IMAGE_NOT_LOCAL')
        if actual.get('volumes') not in (None,{}):raise ProbeError('IMAGE_INHERITED_VOLUMES')
        self.image=image
        label=json.dumps([{'source':'federator-watcher','service':'bridge-federator-watcher','tags':['diagnostic:true']}],separators=(',',':'))
        args=['docker','create','--name',self.name,'--pull=never','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','32','--memory','128m','--log-driver','json-file',
            '--log-opt','max-size=20k','--log-opt','max-file=1','--label','bridge.watcher.owner='+self.name,
            '--label','com.datadoghq.ad.logs='+label,'--entrypoint','node',image,'-e',
            'process.stdout.write('+json.dumps(marker+' synthetic Docker collection canary\n')+');setTimeout(()=>process.exit(0),150000);']
        if self.cancelled and self.cancelled():raise ProbeError('INTERRUPTED')
        self.attempted=True
        cid=self.runner.run(args,timeout=5,limit=256).strip()
        if not CID.fullmatch(cid):raise ProbeError('CANARY_IDENTITY')
        self.identity=cid;self.created=time.monotonic()
        if self.cancelled and self.cancelled():raise ProbeError('INTERRUPTED')
        if self.verify(cid) is None:raise ProbeError('CANARY_UNSAFE')
        if self.cancelled and self.cancelled():raise ProbeError('INTERRUPTED')
        self.runner.run(['docker','start',cid],timeout=5,limit=256)
        return {'status':'CREATED','id':cid,'name':self.name,'marker':marker,'discovery_hold_seconds':120,'process_deadline_seconds':150}
    def verify(self,target):
        v=json.loads(self.runner.run(['docker','inspect',target,'--format',self.FORMAT],timeout=3,limit=4096))
        if not isinstance(v,dict) or not CID.fullmatch(v.get('id','')):return None
        if self.identity and v.get('id')!=self.identity:return None
        if v.get('name')!='/'+self.name or v.get('image')!=self.image or v.get('label')!=self.name or v.get('mounts')!=[] or v.get('network')!='none':return None
        return v['id']
    def cleanup(self):
        if self.identity is None and not self.attempted:return {'status':'SKIP','reason':'NO_OWNED_CANARY'}
        try:
            target=self.identity or self.name
            cid=self.verify(target)
            if cid is None:return {'status':'UNKNOWN','failure':'CANARY_IDENTITY_MISMATCH','name':self.name}
            self.runner.run(['docker','rm','--force',cid],timeout=3,limit=256)
            self.identity=None;self.attempted=False
            return {'status':'REMOVED','name':self.name}
        except (fd.DiagnosticError,ValueError,TypeError):return {'status':'UNKNOWN','failure':'CANARY_CLEANUP_UNAVAILABLE','name':self.name}

def fixed_command(runner,args,timeout=4,limit=65536):
    try:return runner.run(args,timeout=timeout,limit=limit),None
    except fd.DiagnosticError as exc:return None,exc.code if isinstance(exc,ProbeError) else 'UNAVAILABLE'

def events(runner,since,until,names):
    raw,error=fixed_command(runner,['docker','events','--since',since,'--until',until,'--filter','type=container','--format','{{json .}}'],limit=128*1024)
    if error:return {'status':'UNKNOWN','failure':error,'events':[]}
    rows=[]
    for line in raw.splitlines()[-500:]:
        try:
            v=json.loads(line);actor=v.get('Actor',{});action=v.get('Action',v.get('status'))
            name=actor.get('Attributes',{}).get('name');cid=actor.get('ID',v.get('id',''));stamp=v.get('time')
            if name in names and action in ('die','restart','oom','start','destroy') and CID.fullmatch(cid) and type(stamp)is int:
                rows.append({'utc':datetime.fromtimestamp(stamp,timezone.utc).isoformat().replace('+00:00','Z'),'container_id':cid,'role':names[name],'action':action})
        except (ValueError,TypeError,OverflowError,OSError):continue
    return {'status':'OBSERVED','events':rows[-100:],'partial':True,'scope':'bounded_daemon_events_not_retained_history'}

def kernel_evidence(runner,since,until):
    journal_since=fd.parse_time(since).strftime('%Y-%m-%d %H:%M:%S UTC')
    journal_until=fd.parse_time(until).strftime('%Y-%m-%d %H:%M:%S UTC')
    raw,error=fixed_command(runner,['journalctl','_TRANSPORT=kernel','--since',journal_since,'--until',journal_until,'-n','200','--no-pager','-o','short-iso-precise'],timeout=3,limit=65536)
    out={'status':'UNKNOWN' if error else 'OBSERVED','permission_or_retention_limited':True,'oom_markers':0}
    if error:out['failure']=error
    else:
        out['oom_markers']=len(re.findall(r'(?i)out of memory|oom-kill|killed process|memory cgroup out of memory',raw))
        out['io_error_markers']=len(re.findall(r'(?i)I/O error|EXT4-fs error|buffer I/O|blk_update_request',raw))
        out['blocked_task_markers']=len(re.findall(r'(?i)blocked for more than|hung task',raw))
        out['network_error_markers']=len(re.findall(r'(?i)NETDEV WATCHDOG|network.*(?:unreachable|timeout)',raw))
    pressure={}
    for kind in ('cpu','memory','io'):
        try:
            path=Path('/proc/pressure')/kind
            text=fd.read_public(path,path.parent,limit=1024)
            for line in text.splitlines():
                m=re.fullmatch(r'(some|full) avg10=([0-9.]+) avg60=([0-9.]+) avg300=([0-9.]+) total=([0-9]+)',line)
                if m:pressure[kind+'_'+m.group(1)+'_avg10']=float(m.group(2))
        except (OSError,fd.DiagnosticError):pass
    out['pressure']=pressure;out['pressure_status']='OBSERVED' if pressure else 'UNKNOWN'
    try:
        v=os.statvfs('/');out['host_disk_available_bytes']=v.f_bavail*v.f_frsize
    except OSError:pass
    try:
        raw=fd.read_public(Path('/proc/meminfo'),Path('/proc'),limit=65536)
        for key in ('MemTotal','MemAvailable','SwapFree'):
            m=re.search(r'(?m)^'+key+r':\s*([0-9]+) kB$',raw)
            if m:out[key+'_bytes']=int(m.group(1))*1024
    except (OSError,fd.DiagnosticError):pass
    return out

def source_layout(runner,source,agent):
    out={'status':'UNKNOWN','log_path_verified':False,'agent_readonly_source_mount':None,'agent_socket_mount':None}
    cid=source.get('id')
    if not cid:return out,None
    root,error=fixed_command(runner,['docker','info','--format','{{.DockerRootDir}}'],timeout=3,limit=1024)
    root=root.strip() if root else None
    if not root or not re.fullmatch(r'/[A-Za-z0-9_./-]{1,240}',root) or '..' in Path(root).parts:return out,None
    out['docker_storage_root']=root
    try:
        usage=os.statvfs(root);out['docker_disk_available_bytes']=usage.f_bavail*usage.f_frsize;out['docker_inodes_available']=usage.f_favail
    except OSError:out['storage_permission_limited']=True
    raw,error=fixed_command(runner,['docker','inspect',cid,'--format','{"log_path":{{json .LogPath}}}'],limit=2048)
    try:value=json.loads(raw) if raw else {}
    except ValueError:value={}
    expected=root.rstrip('/')+'/containers/'+cid+'/'+cid+'-json.log'
    if value.get('log_path')!=expected:return out,None
    out['log_path_verified']=True;out['status']='OBSERVED';out['source_log_path']=expected
    if not agent.get('id'):return out,None
    raw,error=fixed_command(runner,['docker','inspect',agent['id'],'--format','{"log_path":{{json .LogPath}},"mounts":{{json .Mounts}}}'],limit=16384)
    try:value=json.loads(raw) if raw else {};mounts=value.get('mounts',[])
    except (ValueError,TypeError):return out,None
    mapped=None
    for mount in mounts:
        if not isinstance(mount,dict):continue
        src,dest=mount.get('Source'),mount.get('Destination')
        if src=='/var/run/docker.sock' and dest=='/var/run/docker.sock':out['agent_socket_mount']=True
        if src==root.rstrip('/')+'/containers' and dest in ('/var/lib/docker/containers','/host/var/lib/docker/containers'):
            mapped=dest+'/'+cid+'/'+cid+'-json.log';out['agent_readonly_source_mount']=mount.get('RW') is False
        elif src==root and dest in ('/var/lib/docker','/host/var/lib/docker'):
            mapped=dest+'/containers/'+cid+'/'+cid+'-json.log';out['agent_readonly_source_mount']=mount.get('RW') is False
    if mapped:out['agent_mapped_log_path']=mapped
    return out,mapped

def inventory(runner,repo,source):
    out={'image_id':source['image_id'],'host_commit':None,'image':{}}
    raw,error=fixed_command(runner,['git','-C',str(Path(repo).expanduser()),'rev-parse','HEAD'],limit=128)
    if raw and re.fullmatch('[0-9a-f]{40}',raw.strip()):out['host_commit']=raw.strip()
    raw,error=fixed_command(runner,['docker','image','inspect',source['image_id'],'--format','{"digests":{{json .RepoDigests}},"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}},"created":{{json .Created}}}'],limit=16384)
    try:value=json.loads(raw) if raw else {}
    except ValueError:value={}
    if isinstance(value,dict):
        rev=value.get('revision')
        if isinstance(rev,str) and re.fullmatch('[0-9a-f]{7,40}',rev):out['image']['revision']=rev
        digests=value.get('digests')
        if isinstance(digests,list):out['image']['digests']=[x for x in digests[:8] if isinstance(x,str) and re.fullmatch('[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}',x)]
        created=fd.parse_time(value.get('created',''))
        if created:out['image']['created']=created.isoformat().replace('+00:00','Z')
    out['note']='Host HEAD, image revision label, immutable image ID and embedded source hashes are separate evidence.'
    return out

class Watcher:
    def __init__(self,args,runner,store):
        self.args,self.runner,self.store=args,runner,store
        self.started=fd.utc_now();self.start_mono=time.monotonic();self.previous_time=self.started
        self.stop=False;self.runner.cancelled=lambda:self.stop;self.nodes={};self.samples=deque(maxlen=60);self.deep=deque(maxlen=3)
        token=secrets.token_hex(12);self.canary=Canary(runner,'fw-canary-'+token);self.canary.cancelled=lambda:self.stop
        self.direct_marker='fw-direct-'+token;self.canary_marker='fw-canary-marker-'+token
        self.report={'version':VERSION,'operator':args.operator,'profile':args.profile,'started':self.started,
            'samples':[],'deep':[],'tests':{},'human_queries':{'direct':'service:bridge-federator-watcher "'+self.direct_marker+'"',
                'canary':'service:bridge-federator-watcher "'+self.canary_marker+'"'},
            'limits':{'retained_samples':60,'timeline_segments':2,'segment_bytes':8*1024*1024,'deep_samples':3},
            'claims':{'single_host_peer_timing':'CORRELATION_ONLY','aggregate_counters':'NOT_SOURCE_DELIVERY_PROOF'}}
        try:self.app_key=read_app_key(args.dd_app_key_file)
        except ProbeError as exc:self.app_key=None;self.report['read_key']={'status':'UNKNOWN','failure':exc.code}
        else:self.report['read_key']={'status':'AVAILABLE' if self.app_key else 'ABSENT'}
        self.sent_direct=False;self.created_canary=False;self.last_search=-float('inf');self.last_deep=-float('inf');self.last_fatal=None
        self.repo_error=None
        try:no_symlinks(args.repo)
        except ProbeError as exc:self.repo_error=exc.code
    def interrupted(self,*unused):self.stop=True
    def flush(self):
        self.report['samples']=list(self.samples);self.report['deep']=list(self.deep);self.store.write(self.report)
    def quick(self):
        now=fd.utc_now();snap={'utc':now,'source':state(self.runner,self.args.container),'agent':state(self.runner,self.args.agent),'collection':{'status':'UNKNOWN'}}
        source=snap['source'];agent=snap['agent'];snap['source_guard']='UNKNOWN'
        if source.get('id'):
            self.report['human_queries']['source']='container_id:'+source['id']
            if not self.repo_error:
                try:
                    node=self.nodes.get(source['id'])
                    if node is None:
                        node=fd.Container(self.args.repo,self.args.profile,self.args.container,self.runner);self.nodes[source['id']]=node
                        # Only a few epochs are retained; changing IDs stays explicit in snapshots.
                        if len(self.nodes)>4:self.nodes.pop(next(iter(self.nodes)))
                    guarded=node.inspect()
                    if guarded['id']!=source['id']:raise ProbeError('SOURCE_CHANGED_DURING_SNAPSHOT')
                    snap['source_guard']='PASS'
                    public=fd.public_settings(node.cfg,self.args.profile)
                    snap['public_config']={k:v for k,v in public.items() if k in ('minimum_peers','run_every_minutes','config_sha256','main_json','side_json')}
                    minimum=public['minimum_peers']
                except (fd.DiagnosticError,OSError,ValueError):snap['source_guard']='FAIL';minimum=1
            else:snap['source_guard']='FAIL';minimum=1
            raw,error=fixed_command(self.runner,['docker','inspect',source['id'],'--format','{{.HostConfig.LogConfig.Type}}'],limit=128)
            driver=raw.strip() if raw is not None else None
            snap['log_driver']=driver if driver in ('json-file','local','journald','none','syslog','fluentd','awslogs','gelf','splunk','gcplogs') else 'UNKNOWN'
            raw,error=fixed_command(self.runner,['docker','logs','--timestamps','--tail','500']+(['--since',self.previous_time] if self.samples else [])+['--until',now,source['id']],limit=1024*1024)
            if raw is not None:
                snap['markers']=markers(raw,fd.parse_time(source['started']));snap['log_context']=fd.log_summary(raw,source['started'],minimum)
                snap['log_window']={'status':'OBSERVED','partial':True,'since':self.previous_time if self.samples else source['started'],'until':now}
            else:snap['log_window']={'status':'UNKNOWN','failure':error,'partial':True}
            if source.get('running'):
                raw,error=fixed_command(self.runner,['docker','stats','--no-stream','--format','{{json .}}',source['id']],timeout=3,limit=8192)
                if raw:
                    try:
                        stats=json.loads(raw)
                        snap['docker_stats']={k:v for k,v in stats.items() if k in ('CPUPerc','MemUsage','MemPerc','NetIO','BlockIO','PIDs') and isinstance(v,str) and re.fullmatch(r'[0-9. %/A-Za-z]+',v)}
                    except (ValueError,TypeError):pass
        snap['source_layout'],mapped_log_path=source_layout(self.runner,source,agent)
        if agent.get('id') and agent.get('running'):
            raw,error=fixed_command(self.runner,['docker','stats','--no-stream','--format','{{json .}}',agent['id']],timeout=3,limit=8192)
            if raw:
                try:
                    stats=json.loads(raw)
                    snap['agent_docker_stats']={k:v for k,v in stats.items() if k in ('CPUPerc','MemUsage','MemPerc','NetIO','BlockIO','PIDs') and isinstance(v,str) and re.fullmatch(r'[0-9. %/A-Za-z]+',v)}
                except (ValueError,TypeError):pass
            snap['collection']=agent_call(self.runner,agent['id'],{'op':'snapshot','cid':source.get('id',''),'source_path':mapped_log_path})
            raw,error=fixed_command(self.runner,['docker','logs','--timestamps','--tail','200','--since',self.previous_time,'--until',now,agent['id']],limit=256*1024)
            if raw is not None:
                # Only known codes/classes are retained, never raw error lines.
                snap['agent_markers']=[{'class':name,'count':len(re.findall(pattern,raw))} for name,pattern in (
                    ('AUTH_REJECT',r'\b(?:401|403)\b'),('RATE_LIMIT',r'\b429\b'),('DNS_ERROR',r'ENOTFOUND|EAI_AGAIN|no such host'),
                    ('TLS_ERROR',r'(?i)certificate|TLS handshake'),('TIMEOUT',r'(?i)timed? ?out|timeout'),('RETRY',r'(?i)retry|backoff')) if re.search(pattern,raw)]
        elif agent.get('running') is False:snap['collection']={'status':'UNKNOWN','failure':'AGENT_STOPPED'}
        snap['events']=events(self.runner,self.previous_time,now,{self.args.container:'source',self.args.agent:'agent'})
        snap['kernel']=kernel_evidence(self.runner,self.previous_time,now)
        # Reinspect at the end: an initial running state cannot hide a crash during this sample.
        for kind,name in (('source',self.args.container),('agent',self.args.agent)):
            end=state(self.runner,name)
            snap[kind+'_end']=end
            if end.get('id')==snap[kind].get('id') and end.get('running') is False:snap[kind]=end
            elif end.get('id') and (end.get('id')!=snap[kind].get('id') or end.get('started')!=snap[kind].get('started')):snap[kind+'_changed_during_sample']=True
        mtime=fd.parse_time(snap['collection'].get('source_mtime_utc',''))
        if mtime:snap['collection']['source_file_age_seconds']=(fd.parse_time(now)-mtime).total_seconds()
        snap['assessment']=assess(snap)
        if self.samples:snap['delta']=compare(self.samples[-1],snap)
        if self.samples:
            before=fd.parse_time(self.samples[-1]['utc']);after=fd.parse_time(now)
            snap['actual_sample_interval_seconds']=(after-before).total_seconds()
        self.previous_time=now
        return snap
    def tests(self,snap):
        if self.stop:return
        agent=snap.get('agent',{});collection=snap.get('collection',{});source=snap.get('source',{})
        site=collection.get('site') if collection.get('site_status')=='MATCH' else None
        if agent.get('running') and site and not snap.get('agent_changed_during_sample'):
            if not self.sent_direct:
                self.sent_direct=True  # A timeout must never cause a second synthetic submission.
                self.report['tests']['direct']=agent_call(self.runner,agent['id'],{'op':'direct','site':site,'marker':self.direct_marker,'operator':self.args.operator})
                self.report['tests']['direct']['marker']=self.direct_marker
                if self.stop:return
            if self.app_key and time.monotonic()-self.last_search>=300:
                self.last_search=time.monotonic()
                identifiers=[('direct',self.direct_marker),('canary',self.canary_marker),('source',source.get('id',''))]
                for kind,identifier in identifiers:
                    if self.stop:return
                    if kind=='source' and (not CID.fullmatch(identifier) or snap.get('source_changed_during_sample') or snap.get('source_end',{}).get('id')!=identifier):continue
                    self.report['tests']['search_'+kind]=agent_call(self.runner,agent['id'],{'op':'search','site':site,'app_key':self.app_key,'kind':kind,'identifier':identifier,'since':epoch_since(self.started,source.get('started',self.started)) if kind=='source' else self.started})
            elif not self.app_key:self.report['tests']['search']={'status':'UNKNOWN','failure':'READ_KEY_ABSENT_OR_INVALID'}
        else:self.report['tests'].setdefault('direct',{'status':'UNKNOWN','failure':'AGENT_OR_SITE_UNVERIFIED'})
        if self.stop:return
        if not self.created_canary and snap.get('source_guard')=='PASS' and source.get('image_id') and not snap.get('source_changed_during_sample'):
            self.created_canary=True
            try:self.report['tests']['canary']=self.canary.create(source['image_id'],self.canary_marker)
            except fd.DiagnosticError:self.report['tests']['canary']={'status':'UNKNOWN','failure':'CANARY_UNAVAILABLE','name':self.canary.name}
        if self.canary.identity and time.monotonic()-self.canary.created>=120:
            self.report['canary_cleanup']=self.canary.cleanup()
    def deep_check(self,snap):
        # New fatal markers must not bypass the Etherscan diagnostic request budget.
        if time.monotonic()-self.last_deep<60:return
        if snap.get('source_guard')!='PASS' or snap.get('source_changed_during_sample'):
            self.deep.append({'utc':fd.utc_now(),'status':'UNKNOWN','failure':'SOURCE_PROFILE_UNVERIFIED'});return
        source=snap['source'];node=self.nodes.get(source['id'])
        entries=self.report.setdefault('inventory',{})
        if source['id'] not in entries:
            entries[source['id']]=inventory(self.runner,self.args.repo,source)
            if len(entries)>4:entries.pop(next(iter(entries)))
        if not source.get('running'):
            self.deep.append({'utc':fd.utc_now(),'status':'FAIL','failure':'SOURCE_STOPPED','id':source['id']});return
        before=time.monotonic();self.last_deep=before
        try:result=fd.runtime_probe(node,self.args.profile,False,self.runner,timeout=50)
        except (fd.DiagnosticError,OSError,ValueError,TypeError):result={'checks':[{'name':'runtime','status':'WARN','failure':'SOURCE_CHANGED_OR_UNAVAILABLE'}]}
        # The bound is explicit and keeps long dependency output out of every quick sample.
        if len(json.dumps(result).encode())>256*1024:result={'checks':[{'name':'runtime','status':'WARN','failure':'REPORT_LIMIT'}]}
        self.deep.append({'utc':fd.utc_now(),'id':source['id'],'evidence':result})
    def historical(self):
        if not self.args.incident_since:return
        since,until=self.args.incident_since,self.args.incident_until
        out={'since':since,'until':until,'partial':True,'claim':'MISSING_RECORDS_CANNOT_PROVE_CAUSE','containers':{}}
        for role,name in (('source',self.args.container),('agent',self.args.agent)):
            snap=state(self.runner,name)
            if not snap.get('id'):out['containers'][role]={'status':'UNKNOWN','failure':'CURRENT_CONTAINER_UNAVAILABLE'};continue
            raw,error=fixed_command(self.runner,['docker','logs','--timestamps','--since',since,'--until',until,'--tail','1000',snap['id']],timeout=8,limit=1024*1024)
            out['containers'][role]={'status':'UNKNOWN' if error else 'OBSERVED','id':snap['id'],'partial':True,'current_container_only':True,'markers':markers(raw or '')}
            if error:out['containers'][role]['failure']=error
        out['events']=events(self.runner,since,until,{self.args.container:'source',self.args.agent:'agent'})
        out['kernel']=kernel_evidence(self.runner,since,until);out['captured_utc']=fd.utc_now();self.report['historical']=out;self.store.append({'type':'historical','operator':self.args.operator,'evidence':out})
    def run(self):
        next_sample=self.start_mono;end=self.start_mono+self.args.duration if self.args.duration else None
        try:
            self.runner.deadline=time.monotonic()+30;self.historical();self.flush()
            while not self.stop and (end is None or time.monotonic()<end):
                self.runner.deadline=min(time.monotonic()+40,end) if end else time.monotonic()+40
                snap=self.quick();self.samples.append(snap);print(snap['utc']+' sample '+snap['assessment']['status']+'; source '+snap['source'].get('status','unknown')+'; Agent '+snap['agent'].get('status','unknown'),flush=True);self.store.append({'type':'sample','operator':self.args.operator,'evidence':snap});self.flush()
                if self.stop:break
                self.runner.deadline=min(time.monotonic()+60,end) if end else time.monotonic()+60
                self.tests(snap);self.flush()
                if self.stop:break
                fatal=max((v['utc'] for v in snap.get('markers',[]) if v['class'] in ('AUTH_STREAM_NULL','PROCESS_FATAL')),default=None)
                if time.monotonic()-self.last_deep>=self.args.deep_every or (fatal and fatal!=self.last_fatal):
                    self.runner.deadline=min(time.monotonic()+50,end) if end else time.monotonic()+50
                    self.deep_check(snap);self.last_fatal=fatal;self.flush()
                next_sample+=self.args.interval
                while next_sample<=time.monotonic():next_sample+=self.args.interval
                wait=min(next_sample-time.monotonic(),end-time.monotonic()) if end else next_sample-time.monotonic()
                until=time.monotonic()+max(0,wait)
                while not self.stop and time.monotonic()<until:time.sleep(min(.25,until-time.monotonic()))
        finally:
            self.runner.deadline=None;self.runner.cancelled=None
            self.report['finished']=fd.utc_now();self.report['interrupted']=self.stop
            cleanup=self.canary.cleanup()
            if cleanup['status']!='SKIP' or 'canary_cleanup' not in self.report:self.report['canary_cleanup']=cleanup
            self.app_key=None;self.flush()
        return self.report

def analyze(args,store):
    timelines=[]
    classes=('AUTH_STREAM_NULL','GAS_ERROR','DNS_ERROR','SIGNATURE_ERROR','PROCESS_FATAL','MISSING_KEY')
    def add(item,operator,observation,source_id,scope,window=None):
        if not isinstance(item,dict) or item.get('class') not in classes:return
        instant=fd.parse_time(item.get('utc',''))
        if instant is None:return
        observed=fd.parse_time(observation or '')
        timelines.append({'utc':instant.isoformat().replace('+00:00','Z'),
            'observation_utc':observed.isoformat().replace('+00:00','Z') if observed else None,
            'operator':operator,'source_id':source_id if isinstance(source_id,str) and CID.fullmatch(source_id) else None,
            'class':item['class'],'scope':scope})
        if window is not None:
            for key in ('since','until'):
                value=fd.parse_time(window.get(key,''))
                timelines[-1]['window_'+key]=value.isoformat().replace('+00:00','Z') if value else None
        if len(timelines)>10000:raise ProbeError('ANALYZE_LIMIT')
    for folder in args.analyze:
        root=no_symlinks(folder)
        for name in ('timeline.previous.jsonl','timeline.jsonl'):
            path=root/name
            if not path.exists():continue
            no_symlinks(path)
            if path.stat().st_size>8*1024*1024:raise ProbeError('ANALYZE_LIMIT')
            for line in fd.read_public(path,root,limit=8*1024*1024).splitlines():
                try:row=json.loads(line)
                except ValueError:raise ProbeError('ANALYZE_SHAPE') from None
                evidence=row.get('evidence',{}) if isinstance(row,dict) else {}
                operator=row.get('operator') if isinstance(row,dict) else None
                if operator not in OPERATORS or not isinstance(evidence,dict):continue
                if row.get('type')=='historical':
                    for role,container in evidence.get('containers',{}).items():
                        if role not in ('source','agent') or not isinstance(container,dict):continue
                        for item in container.get('markers',[]):add(item,operator,evidence.get('captured_utc'),container.get('id'),'historical_'+role,evidence)
                else:
                    source=evidence.get('source',{})
                    for item in evidence.get('markers',[]):add(item,operator,evidence.get('utc'),source.get('id') if isinstance(source,dict) else None,'source')
    timelines.sort(key=lambda x:fd.parse_time(x['utc']))
    report={'version':VERSION,'started':fd.utc_now(),'finished':fd.utc_now(),'samples':[],
        'merged_timeline':timelines,'interpretation':'Cross-node timing is correlation; this report does not prove which node caused a remote crash.'}
    store.write(report);return report

def main(argv=None):
    args=arguments(argv)
    root=args.output_dir or str(Path.home()/'.local/state/bridge-federator-watcher'/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4)))
    try:store=Store(root)
    except (ProbeError,OSError):
        print('Cannot create private output directory; no probes ran.',file=sys.stderr);return 1
    watcher=None
    previous={}
    try:
        if args.analyze:analyze(args,store)
        else:
            watcher=Watcher(args,Runner(),store)
            for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,watcher.interrupted)
            print('Watcher started UTC '+watcher.started+'; duration '+('continuous until Ctrl-C' if args.duration==0 else str(args.duration)+' seconds')+'; private evidence: '+str(store.root),flush=True)
            watcher.run()
        print('Private watcher evidence: '+str(store.root))
        return 130 if watcher and watcher.stop else 0
    except (fd.DiagnosticError,OSError,ValueError,TypeError):
        print('Watcher incomplete; partial private evidence: '+str(store.root),file=sys.stderr)
        return 1
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)

if __name__=='__main__':sys.exit(main())
