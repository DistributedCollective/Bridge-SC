#!/usr/bin/env python3
"""Three isolated federators and guarded local Ethereum/Rootstock forks."""
import argparse, json, os, re, secrets, selectors, shutil, signal, socket, subprocess, sys, tempfile, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

class LabError(Exception): pass
READ={'eth_chainId','net_version','web3_clientVersion','eth_blockNumber','eth_getBlockByNumber','eth_getBlockByHash','eth_getCode','eth_getStorageAt','eth_getBalance','eth_getTransactionCount','eth_getProof','eth_getTransactionReceipt','eth_getTransactionByHash','eth_getLogs','eth_call','eth_gasPrice','eth_feeHistory','eth_estimateGas'}
def assert_read(method):
    if method not in READ: raise LabError('Upstream write/unknown method rejected')
def assert_owned(url,allowed):
    if url not in allowed or not re.fullmatch(r'http://(?:127\.0\.0\.1:[1-9][0-9]{3,4}|bf-[0-9a-f]{12}-(?:eth|rsk):8545)',url):raise LabError('Foreign or unowned write endpoint rejected')
def validate_inputs(data):
    events=data.get('events') if isinstance(data,dict) else None
    if not isinstance(events,list) or not 1<=len(events)<=50:raise LabError('Invalid event manifest')
    seen=set()
    for e in events:
        if not isinstance(e,dict) or type(e.get('chain')) is not int or e.get('chain') not in (1,30) or not re.fullmatch(r'0x[0-9a-fA-F]{64}',e.get('tx','')):raise LabError('Invalid source event identity')
        key=(e['chain'],e['tx'].lower())
        if key in seen:raise LabError('Duplicate source event')
        seen.add(key)
    return events
def should_read_upstream(method,params,pin,known):
    if method in ('eth_getTransactionReceipt','eth_getTransactionByHash'):
        return bool(params) and isinstance(params[0],str) and params[0].lower() in known
    if method=='eth_getLogs' and params and isinstance(params[0],dict):
        end=params[0].get('toBlock','latest')
        return isinstance(end,str) and end.startswith('0x') and int(end,16)<=pin
    return False

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*unused):return None
OPENER=build_opener(ProxyHandler({}),NoRedirect())
def rpc(url,method,params,timeout=12):
    req=Request(url,data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0 bridge-fork-lab'})
    with OPENER.open(req,timeout=timeout) as res:body=res.read(4*1024*1024+1)
    if len(body)>4*1024*1024:raise LabError('RPC response size limit')
    obj=json.loads(body)
    if not isinstance(obj,dict) or obj.get('error') or 'result' not in obj:raise LabError('RPC unavailable: '+str(obj.get('error',{}).get('code','shape')))
    return obj['result']
def utc():return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

class Gateway:
    def __init__(self,upstreams,events=(),listen='127.0.0.1',port=0):
        self.transactions={c:{e['tx'].lower() for e in events if e['chain']==c} for c in (1,30)}
        self.upstreams=upstreams;self.forks={};self.pins={};self.owned=set();self.min_gas=None;self.fail_signing=False;self.errors=[]
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*unused):pass
            def do_POST(self):
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=1024*1024:raise LabError('Input size limit')
                    obj=json.loads(self.rfile.read(length));batch=obj if isinstance(obj,list) else [obj]
                    if len(batch)>100:raise LabError('Batch limit')
                    route=self.path.split('/')
                    if len(route)!=3 or route[1] not in ('upstream','local') or route[2] not in ('1','30'):raise LabError('Unknown route')
                    chain=int(route[2]);kind=route[1];out=[]
                    for item in batch:
                        method=item.get('method');params=item.get('params',[])
                        try:
                            if kind=='upstream':
                                assert_read(method);result=rpc(outer.upstreams[chain],method,params)
                            else:
                                endpoint=outer.forks.get(chain);assert_owned(endpoint,outer.owned)
                                if outer.fail_signing and method=='eth_getLogs':raise LabError('Injected source RPC failure')
                                # Historical source identities remain canonical public data. No writes use upstream.
                                historical=should_read_upstream(method,params,outer.pins[chain],outer.transactions[chain])
                                if historical:
                                    assert_read(method);result=rpc(outer.upstreams[chain],method,params)
                                else:result=rpc(endpoint,method,params)
                                if chain==30 and method in ('eth_getBlockByNumber','eth_getBlockByHash') and isinstance(result,dict):result['minimumGasPrice']=outer.min_gas
                            out.append({'jsonrpc':'2.0','id':item.get('id'),'result':result})
                        except Exception as exc:
                            detail={'utc':utc(),'chain':chain,'route':kind,'method':method,'failure':type(exc).__name__+': '+str(exc)[:180]}
                            if method=='eth_getLogs' and params and isinstance(params[0],dict):detail['range']={k:params[0].get(k) for k in ('fromBlock','toBlock','address','topics')}
                            outer.errors.append(detail);outer.errors=outer.errors[-100:];print('RPC_FAIL '+json.dumps(detail),flush=True)
                            out.append({'jsonrpc':'2.0','id':item.get('id'),'error':{'code':-32091,'message':'Bounded lab RPC failure; details withheld'}})
                    body=json.dumps(out if isinstance(obj,list) else out[0]).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                except Exception:self.send_response(400);self.end_headers()
        self.server=ThreadingHTTPServer((listen,port),Handler);self.server.daemon_threads=True
        self.port=self.server.server_address[1];self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def url(self,chain,kind='local'):return 'http://127.0.0.1:'+str(self.port)+'/'+kind+'/'+str(chain)
    def close(self):self.server.shutdown();self.server.server_close()

class Worker:
    def __init__(self,node,script,app,config,log,mode='worker'):
        self.log=open(log,'wb');self.process=subprocess.Popen([node,str(script),mode,str(app),str(config)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,start_new_session=True)
        self.buffer=b'';self.selector=selectors.DefaultSelector();os.set_blocking(self.process.stdout.fileno(),False);self.selector.register(self.process.stdout,selectors.EVENT_READ);self.bytes=0
    def receive(self,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                if line.startswith(b'LAB:'):return json.loads(line[4:])
                self.bytes+=len(line)
                if self.bytes>4*1024*1024:raise LabError('Worker log size limit')
                self.log.write(line+b'\n');self.log.flush()
            for key,_ in self.selector.select(.2):
                chunk=os.read(key.fileobj.fileno(),8192)
                if not chunk:raise LabError('Worker exited before response')
                self.buffer+=chunk
                if len(self.buffer)>1024*1024:raise LabError('Worker line limit')
        raise LabError('Worker response timeout')
    def command(self,data,timeout=60):
        self.process.stdin.write((json.dumps(data)+'\n').encode());self.process.stdin.flush();return self.receive(timeout)
    def close(self):
        try:os.killpg(self.process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait()
        self.selector.close();self.log.close()

class Lab:
    def __init__(self,args):
        self.args=args;self.repo=Path(args.repo).resolve();self.root=Path(tempfile.mkdtemp(prefix='bridge-fork-lab-',dir='/private/tmp' if Path('/private/tmp').is_dir() else None));self.root.chmod(0o700)
        self.processes=[];self.workers=[];self.gateway=None;self.report={'startedUtc':utc(),'runId':self.root.name,'scope':'Owned local forks/test keys only; upstream methods read-only','results':[],'limitations':['Rootstock state uses Anvil Ethereum EVM; no Rootstock consensus equivalence','Focused real-module worker entry point; production five-minute startup wait excluded']}
    def save(self):
        target=self.root/'report.json';target.write_text(json.dumps(self.report,indent=2)+'\n');target.chmod(0o600)
class DockerWorker(Worker):
    def __init__(self,lab,name,config,db,mode='worker',old_vendor=None):
        self.lab=lab;self.name=name;self.log=open(lab.root/(name+'.log'),'wb');self.buffer=b'';self.bytes=0
        command=['docker','--host','unix:///var/run/docker.sock','run','-i','--name',name,'--label','bridge.lab.owner='+lab.token,'--network',lab.private_net,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,nodev,size=32m','--mount','type=bind,source='+str(config)+',target=/fixture/config.json,readonly']
        if db:command+=['--mount','type=bind,source='+str(db)+',target=/lab/db-'+str(json.loads(config.read_text()).get('index',0))]
        if old_vendor:command+=['--mount','type=bind,source='+str(old_vendor)+',target=/opt/lab/app/federator/src/vendors/RSKKeyedAuth.js,readonly']
        command += [lab.image,'node','/opt/lab/worker.cjs',mode,'/opt/lab/app','/fixture/config.json']
        lab.names.append(name);self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,start_new_session=True);self.selector=selectors.DefaultSelector();os.set_blocking(self.process.stdout.fileno(),False);self.selector.register(self.process.stdout,selectors.EVENT_READ)
    def close(self):
        self.lab.remove(self.name)
        # Container deletion ends the owned workload. Let its Docker client exit;
        # do not signal a process group after the client may already have exited.
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.selector.close();self.log.close()

class DockerLab(Lab):
    def __init__(self,args):
        super().__init__(args);self.token=secrets.token_hex(6);self.prefix='bf-'+self.token;self.private_net=self.prefix+'-private';self.egress_net=self.prefix+'-read-egress';self.names=[];self.networks=[];self.image=args.docker_image
        self.report['isolation']='Three Docker worker environments; private network; upstream read-only relay; per-worker disposable key/database'
    def docker(self,args,timeout=60):
        p=subprocess.run(['docker','--host','unix:///var/run/docker.sock']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
        if p.returncode:raise LabError('Docker '+args[0]+' failed: '+p.stderr[-200:])
        return (p.stdout+p.stderr if args[0]=='logs' else p.stdout).strip()
    def remove(self,name):
        try:
            v=json.loads(self.docker(['inspect',name,'--format','{"id":{{json .Id}},"owner":{{json (index .Config.Labels "bridge.lab.owner")}}}'],timeout=5))
            if v.get('owner')!=self.token or not re.fullmatch('[0-9a-f]{64}',v.get('id','')):raise LabError('Cleanup ownership mismatch')
            self.docker(['rm','--force',v['id']],timeout=8)
            self.report.setdefault('removedContainers',[]).append(name)
        except LabError as exc:
            if 'no such' not in str(exc).lower():self.report.setdefault('cleanupErrors',[]).append(str(exc))
    def control_rpc(self,chain,method,params):
        target=self.prefix+('-eth' if chain==1 else '-rsk')
        code="import sys,json;sys.path.insert(0,'/opt/lab');from fork_lab import rpc,assert_owned;p=json.load(sys.stdin);u='http://'+p['target']+':8545';assert_owned(u,{u});print(json.dumps(rpc(u,p['method'],p['params'],timeout=3)))"
        payload=json.dumps({'target':target,'method':method,'params':params})
        proc=subprocess.run(['docker','--host','unix:///var/run/docker.sock','exec','-i',self.relay,'python3','-c',code],input=payload,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=7)
        if proc.returncode:raise OSError('Owned fork not ready')
        return json.loads(proc.stdout)
    def boot(self):
        self.report['image']=json.loads(self.docker(['image','inspect',self.image,'--format','{"id":{{json .Id}},"architecture":{{json .Architecture}},"build":{{json (index .Config.Labels "bridge.lab.build")}}}']))
        if self.report['image'].get('build')!='three-federator-reproduction':raise LabError('Reviewed local lab image required')
        for name,internal in ((self.private_net,True),(self.egress_net,False)):
            self.docker(['network','create','--label','bridge.lab.owner='+self.token]+(['--internal'] if internal else [])+[name]);self.networks.append(name)
        pins={1:self.args.eth_block,30:self.args.rsk_block};headers={};upstreams={1:self.args.eth_upstream,30:self.args.rsk_upstream}
        for chain,block in pins.items():
            headers[chain]=rpc(upstreams[chain],'eth_getBlockByNumber',[hex(block),False])
            if not isinstance(headers[chain],dict) or int(headers[chain]['number'],16)!=block:raise LabError('Canonical fork pin unavailable')
        relay=self.prefix+'-gateway';targets={1:'http://'+self.prefix+'-eth:8545',30:'http://'+self.prefix+'-rsk:8545'}
        cfg=self.root/'relay.json';cfg.write_text(json.dumps({'upstreams':upstreams,'events':self.events,'pins':pins,'forks':targets,'minGas':headers[30]['minimumGasPrice']}));cfg.chmod(0o600)
        code="import sys,json,time;sys.path.insert(0,'/opt/lab');from fork_lab import Gateway;c=json.load(open('/fixture/relay.json'));g=Gateway({int(k):v for k,v in c['upstreams'].items()},c['events'],listen='0.0.0.0',port=8547);g.forks={int(k):v for k,v in c['forks'].items()};g.pins={int(k):v for k,v in c['pins'].items()};g.owned=set(g.forks.values());g.min_gas=c['minGas'];print('Read-only upstream relay ready',flush=True);time.sleep(3600)"
        self.names.append(relay);self.docker(['run','-d','--name',relay,'--label','bridge.lab.owner='+self.token,'--network',self.egress_net,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--user',str(os.getuid())+':'+str(os.getgid()),'--mount','type=bind,source='+str(cfg)+',target=/fixture/relay.json,readonly',self.image,'python3','-u','-c',code]);self.docker(['network','connect','--alias',relay,self.private_net,relay])
        self.relay=relay;self.rpc_urls={};self.host_rpc={}
        for chain,block in pins.items():
            name=self.prefix+('-eth' if chain==1 else '-rsk');port=free_port();self.names.append(name)
            self.docker(['run','-d','--name',name,'--label','bridge.lab.owner='+self.token,'--network',self.private_net,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','-e','HOME=/tmp','-e','XDG_CACHE_HOME=/tmp/.cache','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,nodev,size=128m',self.image,'anvil','--quiet','--host','0.0.0.0','--port','8545','--accounts','0','--chain-id',str(chain),'--fork-url','http://'+relay+':8547/upstream/'+str(chain),'--fork-block-number',str(block),'--timeout','15000','--retries','0','--cache-path','/tmp/cache','--hardfork','berlin' if chain==30 else 'cancun'])
            endpoint='http://127.0.0.1:'+str(port);self.host_rpc[chain]=endpoint;self.rpc_urls[chain]='http://'+relay+':8547/local/'+str(chain)
            end=time.monotonic()+60
            while time.monotonic()<end:
                try:
                    version=self.control_rpc(chain,'web3_clientVersion',[]);pin=self.control_rpc(chain,'eth_getBlockByNumber',[hex(block),False])
                    if 'anvil' not in version.lower() or int(self.control_rpc(chain,'eth_chainId',[]),16)!=chain or pin['hash'].lower()!=headers[chain]['hash'].lower():
                        self.report['pinMismatch']={'chain':chain,'block':block,'expectedHash':headers[chain]['hash'],'observedHash':pin.get('hash'),'client':version};raise LabError('Docker fork identity mismatch')
                    break
                except OSError:time.sleep(.2)
            else:raise LabError('Docker fork readiness deadline')
            self.control_rpc(chain,'evm_setNextBlockTimestamp',[int(time.time())]);self.control_rpc(chain,'evm_mine',[])
            self.report.setdefault('forks',{})[str(chain)]={'block':block,'hash':headers[chain]['hash'],'client':version,'container':name,'rootstockMinimumGasPrice':headers[30]['minimumGasPrice'] if chain==30 else None}
            print('Docker fork ready: chain '+str(chain),flush=True);self.save()
    def run(self):
        try:
            self.events=validate_inputs(json.loads(Path(self.args.inputs).read_text()));self.boot()
            fixture={'runId':self.token,'rpc':self.rpc_urls,'events':self.events,'keys':[secrets.token_hex(32) for _ in range(3)],'root':'/lab','ports':[30303]*3,'ips':[self.prefix+'-f'+str(i) for i in range(3)]}
            config=self.root/'fixture.json';config.write_text(json.dumps(fixture));config.chmod(0o600)
            utility=DockerWorker(self,self.prefix+'-setup',config,None,mode='setup')
            try:prepared=utility.receive(600)
            finally:utility.close()
            self.report['setup']=prepared
            if not prepared.get('ok'):raise LabError('Docker fixture setup failed')
            fixture.update(prepared['fixture']);self.fixture=fixture;self.worker_configs=[]
            for i in range(3):
                public={k:v for k,v in fixture.items() if k!='keys'};public.update(index=i,privateKey=fixture['keys'][i]);path=self.root/('worker-'+str(i)+'.json');path.write_text(json.dumps(public));path.chmod(0o600);self.worker_configs.append(path)
                db=self.root/('db-'+str(i));db.mkdir(mode=0o700)
                worker=DockerWorker(self,fixture['ips'][i],path,db);self.workers.append(worker);self.report['results'].append(worker.receive(60))
            end=time.monotonic()+45
            while time.monotonic()<end:
                states=[w.command({'op':'state'}) for w in self.workers]
                if all(s.get('peers')==2 for s in states):break
                time.sleep(1)
            else:raise LabError('Docker three-peer admission incomplete')
            self.report['peerAdmission']=states;self.save();leader=next(i for i,s in enumerate(states) if s['leader'])
            # Compare the native unready-channel behavior in the old/repaired application.
            old_vendor=self.root/'RSKKeyedAuth.baseline.js';old_vendor.write_bytes(subprocess.check_output(['git','-C',str(self.repo),'show','c5a6f607481277a69dd86364976b078501e10c4e:sovryn-token-bridge/federator/src/vendors/RSKKeyedAuth.js']));old_vendor.chmod(0o644)
            slot=2;self.workers[slot].close();baseline=DockerWorker(self,fixture['ips'][slot],self.worker_configs[slot],self.root/('db-'+str(slot)),old_vendor=old_vendor);self.workers[slot]=baseline
            ready=baseline.receive(60)
            try:
                unexpected=baseline.command({'op':'connection-reset'},timeout=15)
                self.report['baselineConnectionReset']={'processExited':False,'unexpected':unexpected}
                raise LabError('Old connection reset did not reproduce the process failure')
            except LabError as exc:
                metadata=json.loads(self.docker(['inspect',fixture['ips'][slot],'--format','{"running":{{.State.Running}},"exit":{{.State.ExitCode}}}']))
                log=self.docker(['logs','--tail','60',fixture['ips'][slot]])
                self.report['baselineConnectionReset']={'state':metadata,'typeError':('TypeError' in log),'nullBinding':('null' in log),'log':log[-6000:]}
                if metadata['running'] or metadata['exit']!=1 or 'TypeError' not in log:raise
            baseline.close();repaired=DockerWorker(self,fixture['ips'][slot],self.worker_configs[slot],self.root/('db-'+str(slot)));self.workers[slot]=repaired;repaired.receive(60)
            self.report['repairedConnectionReset']=repaired.command({'op':'connection-reset'},timeout=15)
            if not self.report['repairedConnectionReset'].get('connectionReset',{}).get('processSurvived'):raise LabError('Repaired connection reset failed')
            self.report['gasProbe']=repaired.command({'op':'gas-probe'},timeout=15)
            self.control_rpc(1,'anvil_setNextBlockBaseFeePerGas',[hex(5000000000)]);self.control_rpc(1,'evm_setNextBlockTimestamp',[int(time.time())]);self.control_rpc(1,'evm_mine',[])
            self.report['feeProbe']=repaired.command({'op':'fee-probe'},timeout=20)
            if not self.report['feeProbe'].get('fee',{}).get('oldBelowBaseFee') or not self.report['feeProbe']['fee']['repairedCoversBaseFee']:raise LabError('ETH fee comparison did not prove recovery')
            def admitted():
                deadline=time.monotonic()+40
                while time.monotonic()<deadline:
                    states=[w.command({'op':'state'}) for w in self.workers]
                    if all(s.get('peers')==2 for s in states):return states
                    time.sleep(.5)
                raise LabError('Peer recovery deadline')
            states=admitted();leader=next(i for i,s in enumerate(states) if s['leader']);follower=next(i for i in range(3) if i!=leader)
            target=self.events[0];initial=next(c for c in fixture['cases'] if c['tx']==target['tx'])
            if not initial['before']['bridge']:
                self.workers[follower].command({'op':'delay-signatures','ms':20000});requested=self.workers[follower].command({'op':'state'})['requested']
                self.workers[leader].process.stdin.write((json.dumps({'op':'process','event':target})+'\n').encode());self.workers[leader].process.stdin.flush()
                for _ in range(180):
                    if self.workers[follower].command({'op':'state'})['requested']>requested:break
                    time.sleep(.25)
                else:raise LabError('No actual signature request observed before peer loss')
                self.workers[follower].command({'op':'leave'});failed=self.workers[leader].receive(30)
                self.report['peerLossDuringSignature']=failed
                if failed.get('processedAfter') or failed.get('outcome')!='failed':raise LabError('Missing peer unexpectedly completed the transfer')
                self.report['processSurvivalDuringPeerLoss']=[json.loads(self.docker(['inspect',name,'--format','{"running":{{.State.Running}},"exit":{{.State.ExitCode}}}'])) for name in fixture['ips']]
                if not all(v['running'] for v in self.report['processSurvivalDuringPeerLoss']):raise LabError('Peer loss killed a healthy worker')
                self.workers[follower].command({'op':'delay-signatures','ms':0});self.workers[follower].command({'op':'join'});states=admitted();leader=next(i for i,s in enumerate(states) if s['leader'])
            self.save()
            for event in self.events:
                # Automining forks do not advance while the other chain processes.
                # Model a fresh ETH head without weakening the application's freshness check.
                latest=self.control_rpc(1,'eth_getBlockByNumber',['latest',False])
                self.control_rpc(1,'evm_setNextBlockTimestamp',[max(int(time.time()),int(latest['timestamp'],16)+1)])
                if event['chain']==30:self.control_rpc(1,'anvil_setNextBlockBaseFeePerGas',[hex(5000000000)])
                self.control_rpc(1,'evm_mine',[])
                print('Docker replay: source '+str(event['chain'])+' '+event['tx'][:12],flush=True)
                result=self.workers[leader].command({'op':'process','event':event},timeout=120);self.report['results'].append(result);self.save();print('Replay outcome: '+str(result.get('outcome')),flush=True)
                if result.get('outcome') not in ('executed','already-processed') or not result.get('processedAfter'):raise LabError('Transfer processing failed; inspect recorded error')
                if result['outcome']=='executed':
                    expected=next(c['amount'] for c in fixture['cases'] if c['tx']==event['tx'])
                    proof=result.get('executionProof',[])
                    if result.get('votes')!='3' or result.get('balanceDelta')!=expected or len(proof)!=1 or not proof[0].get('status') or proof[0]['transactionId'].lower()!=result['federationId'].lower():raise LabError('Missing receipt, three votes or full receiver token credit (18-decimal fixtures required)')
            self.report['finalStates']=[w.command({'op':'state'}) for w in self.workers];self.report['status']='complete'
        except Exception as exc:self.report['status']='incomplete';self.report['failure']=type(exc).__name__+': '+str(exc)[:250];print(self.report['failure'],flush=True)
        finally:
            for w in self.workers:
                try:
                    self.report.setdefault('workerLogs',{})[w.name]=self.docker(['logs','--tail','80',w.name],timeout=5)[-12000:]
                    self.report.setdefault('workerExit',{})[w.name]=json.loads(self.docker(['inspect',w.name,'--format','{"running":{{.State.Running}},"exit":{{.State.ExitCode}},"oom":{{.State.OOMKilled}}}'],timeout=5))
                except Exception:pass
                try:w.close()
                except Exception as exc:self.report.setdefault('cleanupErrors',[]).append(type(exc).__name__)
            if hasattr(self,'relay'):
                try:self.report['relayLog']=self.docker(['logs','--tail','30',self.relay],timeout=5)[-4000:]
                except Exception:pass
            for name in reversed(self.names):
                try:
                    self.report.setdefault('containerLogs',{})[name]=self.docker(['logs','--tail','80',name],timeout=5)[-12000:]
                    self.report.setdefault('containerExit',{})[name]=json.loads(self.docker(['inspect',name,'--format','{"status":{{json .State.Status}},"exit":{{.State.ExitCode}},"oom":{{.State.OOMKilled}}}'],timeout=5))
                except Exception:pass
                self.remove(name)
            for name in reversed(self.networks):
                try:
                    v=json.loads(self.docker(['network','inspect',name,'--format','{{json .Labels}}']))
                    if v.get('bridge.lab.owner')!=self.token:raise LabError('Network cleanup owner mismatch')
                    self.docker(['network','rm',name],timeout=5)
                except Exception as exc:self.report.setdefault('cleanupErrors',[]).append(type(exc).__name__)
            for name in ('fixture.json','relay.json','worker-0.json','worker-1.json','worker-2.json'):
                (self.root/name).unlink(missing_ok=True)
            for i in range(3):
                db=self.root/('db-'+str(i))
                if db.is_dir():shutil.rmtree(db)
            self.report['finishedUtc']=utc();self.report['cleanup']='Owned Docker containers/networks, disposable keys and databases removed; bounded proof retained';self.save();print('Private Docker lab report: '+str(self.root/'report.json'),flush=True)
        return 0 if self.report['status']=='complete' else 2

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',required=True);p.add_argument('--repo',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--eth-upstream',default='https://eth.sovryn.app/mainnet');p.add_argument('--rsk-upstream',default='https://mainnet-dev.sovryn.app/rpc');p.add_argument('--eth-block',type=int,default=26156820);p.add_argument('--rsk-block',type=int,default=9310975);p.add_argument('--docker-image',default='bridge-fork-lab:local');args=p.parse_args();return DockerLab(args).run()
if __name__=='__main__':sys.exit(main())
