import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import federator_dependencies as fd

NODE = os.environ.get('FEDERATOR_TEST_NODE') or shutil.which('node')


class FakeDocker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.running = True
        self.calls = []
        self.overlays = []
        self.identity = '1' * 64
        self.payload = {'versions': {'node': 'v14.21.3'}, 'checks': [
            {'name': 'main.rpc', 'status': 'PASS', 'chain_id': 30, 'net_version': 30},
            {'name': 'side.rpc', 'status': 'FAIL', 'failure': 'DNS'}]}

    def run(self, args, timeout=10, input_text=None, limit=1048576):
        self.calls.append((args, timeout, input_text))
        if args[:2] == ['docker', 'inspect']:
            if args[2] == 'datadog-agent':
                raise fd.DiagnosticError('unavailable')
            return json.dumps({'id': self.identity, 'running': self.running,
                'status': 'running' if self.running else 'exited', 'started': '2026-01-01T00:00:00Z',
                'finished': '2026-01-01T00:00:00Z', 'exit': 1 if not self.running else 0,
                'oom': False, 'restarts': 2, 'image_id': 'sha256:' + '2' * 64,
                'mounts': [{'Source': str(self.cfg), 'Destination': '/app/federator/config'},
                           {'Source': str(self.cfg / 'db'), 'Destination': '/app/federator/db'}] + self.overlays})
        if args[:3] == ['docker', 'image', 'inspect']:
            return json.dumps({'digests': ['repo@sha256:' + '3' * 64],
                'revision': 'abc1234', 'created': '2026-01-01T00:00:00Z'})
        if args[:2] == ['docker', 'logs']:
            return '2026-01-01T00:00:01Z TypeError: RSKKeyedAuth privateKey=' + '9' * 64
        if args[:2] == ['docker', 'stats']:
            return json.dumps({'CPUPerc': '1.2%', 'MemUsage': '2MiB / 1GiB', 'PIDs': '4'})
        if args[:2] in (['docker', 'exec'], ['docker', 'run']):
            return json.dumps(self.payload)
        if args[0] == 'git':
            return 'a' * 40
        raise AssertionError(args)


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.cfg = self.repo / 'federator-env/mainnet-BSC-RSK'
        (self.cfg / 'db').mkdir(parents=True)
        (self.cfg / 'config.js').write_text("module.exports={mainchain:require('./rskmainnet.json'),"
            "sidechain:require('./bmainnet.json'),minimumPeerAmount:2,runEvery:2,"
            "federatorAddress:'0x" + '4' * 40 + "', privateKey:require('/must-not-read')};")
        (self.cfg / 'federator.key').write_text('MUST-NOT-READ')
        self.docker = FakeDocker(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, flags):
        output = io.StringIO()
        with patch('federator_dependencies.Runner', return_value=self.docker), contextlib.redirect_stdout(output):
            result = fd.main(['--profile', 'bsc-rsk', '--repo', str(self.repo)] + flags)
        return result, output.getvalue()

    def test_failed_endpoint_preserves_other_evidence_and_private_report(self):
        dest = self.repo / 'evidence.json'
        result, output = self.cli(['--output', str(dest), '--samples', '2'])
        report = json.loads(dest.read_text())
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(result, 0)
        self.assertEqual(report['runtime_samples'][0]['checks'][0]['chain_id'], 30)
        self.assertEqual(report['runtime_samples'][0]['checks'][1]['failure'], 'DNS')
        self.assertEqual(report['host_commit'], 'a' * 40)
        self.assertEqual(report['image']['revision'], 'abc1234')
        self.assertNotIn('9' * 32, dest.read_text() + output)
        self.assertNotIn('MUST-NOT-READ', dest.read_text() + output)
        self.assertEqual(report['p2p_active_connect'], 'SKIP')

    def test_versions_only_running_has_no_network_payload_or_key_mount(self):
        self.docker.payload = {'versions': {'node': 'v14.21.3'}, 'checks': []}
        _, _ = self.cli(['--versions-only'])
        execution = [args for args, _, _ in self.docker.calls if args[:2] == ['docker', 'exec']]
        self.assertEqual(len(execution), 1)
        self.assertIn(self.docker.identity, execution[0])
        self.assertIn('--versions-only', execution[0])
        self.assertFalse(any(args[:2] == ['docker', 'logs'] for args, _, _ in self.docker.calls))

    def test_stopped_versions_use_offline_pinned_image_without_mounts(self):
        self.docker.running = False
        self.docker.payload = {'versions': {'node': 'v14.21.3'}, 'checks': []}
        result, _ = self.cli(['--versions-only'])
        args = next(args for args, _, _ in self.docker.calls if args[:2] == ['docker', 'run'])
        self.assertIn('--read-only', args)
        self.assertIn('--network', args)
        self.assertEqual(args[args.index('--network') + 1], 'none')
        self.assertEqual(args[args.index('--log-driver') + 1], 'none')
        self.assertIn('sha256:' + '2' * 64, args)
        self.assertNotIn('-v', args)
        self.assertNotIn('--mount', args)
        self.assertNotEqual(result, 0)  # versions do not make an exited federator healthy

    def test_stopped_full_diagnosis_never_execs_or_restarts(self):
        self.docker.running = False
        result, _ = self.cli([])
        self.assertNotEqual(result, 0)
        self.assertFalse(any(args[:2] in (['docker', 'exec'], ['docker', 'run'], ['docker', 'start'])
                             for args, _, _ in self.docker.calls))

    def test_wrong_mount_profile_overlay_and_container_replacement_fail_closed(self):
        self.docker.overlays = [{'Source': '/other/key', 'Destination': '/app/federator/config/federator.key'}]
        with self.assertRaises(fd.DiagnosticError):
            self.cli([])
        self.assertFalse(any(args[:2] == ['docker', 'exec'] for args, _, _ in self.docker.calls))

    def test_output_refuses_existing_and_symlink_files(self):
        dest = self.repo / 'report.json'
        dest.write_text('preserve')
        link = self.repo / 'link.json'
        link.symlink_to(dest)
        for path in (dest, link):
            with self.subTest(path=path), self.assertRaises(fd.DiagnosticError):
                self.cli(['--output', str(path)])
        self.assertEqual(dest.read_text(), 'preserve')
        self.assertFalse(self.docker.calls)

    def test_watch_and_samples_bounds_are_rejected_before_docker(self):
        for flags in (['--watch', '601'], ['--watch', '-1'], ['--samples', '4'], ['--samples', '0'],
                      ['--versions-only', '--watch', '10']):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.cli(flags)
        self.assertFalse(self.docker.calls)

    def test_subprocess_timeout_and_errors_never_echo_secret_output(self):
        secret = 'opaque-api-key'
        with patch('federator_dependencies.subprocess.run', side_effect=subprocess.TimeoutExpired('docker', 1, output=secret)):
            with self.assertRaises(fd.DiagnosticError) as err:
                fd.Runner().run(['docker', 'exec', 'node'], timeout=1)
        self.assertNotIn(secret, str(err.exception))

    def test_static_config_does_not_execute_private_key_require(self):
        public = fd.public_settings(self.cfg, 'bsc-rsk')
        self.assertEqual(public['main_json'], 'rskmainnet.json')
        self.assertEqual(public['side_json'], 'bmainnet.json')
        self.assertEqual(public['minimum_peers'], 2)
        self.assertNotIn('privateKey', public)

    def test_fresh_log_summary_retains_fatal_marker_without_raw_text(self):
        now = fd.parse_time('2026-01-01T00:00:05Z')
        logs = ('2026-01-01T00:00:02Z [2025-12-31T00:00:00] TypeError: RSKKeyedAuth https://user:key@host\n'
                '2026-01-01T00:00:03Z Not leader (3 other peers, node N, leader L)\n')
        report = fd.log_summary(logs, '2026-01-01T00:00:00Z', 2, now)
        self.assertEqual(report['fatal_counts']['auth_type_error'], 1)
        self.assertEqual(report['fresh_other_peers'], 3)
        self.assertGreater(report['app_clock_skew_seconds'], 80000)
        self.assertNotIn('https://', json.dumps(report))


@unittest.skipUnless(NODE, 'Node needed to test embedded probes')
class EmbeddedNodeTests(unittest.TestCase):
    def run_js(self, case):
        proc = subprocess.run([NODE, '-'], input=fd.NODE_CORE + '\n' + case, text=True,
                              capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr[:500])
        return json.loads(proc.stdout)

    def test_rpc_requires_well_formed_chain_and_net_version(self):
        out = self.run_js("console.log(JSON.stringify([validQuantity('0x1'),validQuantity('0xwat'),validNetwork('1x'),validNetwork('1')]));")
        self.assertEqual(out, ['1', None, None, '1'])

    def test_history_empty_and_oversized_logs_cannot_claim_completeness(self):
        out = self.run_js("console.log(JSON.stringify([summarizeLogs([],true),summarizeLogs(Array(501).fill({blockNumber:'0x1'}),true)]));")
        self.assertEqual(out[0]['status'], 'WARN')
        self.assertEqual(out[1]['status'], 'WARN')
        self.assertTrue(out[1]['truncated'])

    def test_versions_hash_the_average_source_used_by_repair_overlays(self):
        case="file=p=>p.endsWith('/GasPriceAvg.js')?'average-source-v1':'{}';console.log(JSON.stringify(versions().source_sha256));"
        out=self.run_js(case)
        self.assertEqual(out['src/lib/GasPriceAvg.js'],'a8a0bcaf6c329048f9dc5d6cd61ba2141526b3a13b8ff8130901f2da54087b3b')

    def test_versions_read_the_actual_service_scheduler_path(self):
        case="const reads=[];file=p=>{reads.push(p);return '{}'};versions();console.log(JSON.stringify(reads));"
        out=self.run_js(case)
        self.assertIn('/app/federator/src/services/Scheduler.js',out)
        self.assertNotIn('/app/federator/src/lib/Scheduler.js',out)

    def test_eth_fee_readiness_rejects_missing_zero_and_stale_base_fee(self):
        case="console.log(JSON.stringify([feeReadiness({timestamp:'0x64'},100),feeReadiness({timestamp:'0x64',baseFeePerGas:'0x0'},100),feeReadiness({timestamp:'0x64',baseFeePerGas:'0x1'},300),feeReadiness({timestamp:'0x64',baseFeePerGas:'0x1'},100)]));"
        out=self.run_js(case)
        self.assertEqual([x['status'] for x in out],['FAIL','FAIL','FAIL','PASS'])
        self.assertEqual(out[2]['age_seconds'],200)  # Fresh enough for general head check, stale for the fee builder.

    def test_general_head_pass_does_not_hide_failed_eth_fee_readiness(self):
        case="""Date.now=()=>300000;const checks=[];
          rpc=async(u,m,p)=>({result:m==='eth_chainId'?'0x1':m==='net_version'?'1':m==='eth_getBlockByNumber'?{number:'0x64',timestamp:'0x64',baseFeePerGas:'0x1'}:m==='eth_getLogs'?[]:m==='eth_syncing'?false:'0x1'});
          chainChecks('side',{host:'https://rpc.invalid',bridge:'0x'+'1'.repeat(40),federation:'0x'+'2'.repeat(40),fromBlock:5},1,null,2,v=>checks.push(v)).then(()=>console.log(JSON.stringify(checks)));"""
        out=self.run_js(case)
        self.assertEqual(next(x for x in out if x['name']=='side.head')['status'],'PASS')
        self.assertEqual(next(x for x in out if x['name']=='side.fee_readiness')['status'],'FAIL')

    def test_fee_readiness_keeps_the_builder_subsecond_age_boundary(self):
        out=self.run_js("Date.now=()=>220500;console.log(JSON.stringify(feeReadiness({timestamp:'0x64',baseFeePerGas:'0x1'})));" )
        self.assertEqual(out['status'],'FAIL')
        self.assertEqual(out['age_seconds'],120.5)

    def test_private_config_is_never_required_by_runtime_static_parser(self):
        case = """const reads=[];fs.readFileSync=(p)=>{reads.push(p);return Buffer.from(p.endsWith('config.js') ?
          \"module.exports={mainchain:require('./rskmainnet.json'),sidechain:require('./bmainnet.json'),privateKey:require('/secret.key'),minimumPeerAmount:2,federatorAddress:'unset'}\" : '{}');};
          fs.lstatSync=()=>({isFile:()=>true,isSymbolicLink:()=>false,size:100});
          const c=readPublic('bsc-rsk');console.log(JSON.stringify({reads,main:c.main_json,side:c.side_json}));"""
        out = self.run_js(case)
        self.assertEqual(out['main'], 'rskmainnet.json')
        self.assertNotIn('/secret.key', out['reads'])

    def test_rpc_error_does_not_emit_provider_message_or_url(self):
        out = self.run_js("request=async()=>({body:{error:{code:-32000,message:'opaque-private-secret'}}});rpc('https://user:key@rpc.invalid','eth_chainId',[]).then(x=>console.log(JSON.stringify(x)));")
        self.assertEqual(out['failure'], 'RPC')
        self.assertEqual(out['rpc_code'], -32000)
        self.assertNotIn('opaque-private-secret', json.dumps(out))

    def test_oracle_invalid_decimal_and_deprecated_response_are_summary_only(self):
        out = self.run_js("console.log(JSON.stringify([oracleSummary({status:'1',result:{SafeGasPrice:'0.123'}}),oracleSummary({status:'1',result:{SafeGasPrice:'NaN'}}),oracleSummary({status:'0',result:'V1 endpoint deprecated opaque-secret'})]));")
        self.assertEqual(out[0]['safe_gwei'], '0.123')
        self.assertEqual(out[1]['status'], 'FAIL')
        self.assertTrue(out[2]['deprecated'])
        self.assertNotIn('opaque-secret', json.dumps(out))


class AdditionalEvidenceTests(unittest.TestCase):
    def test_waiting_peer_message_and_multiline_auth_fault_are_classified(self):
        log=('2026-01-01T00:00:01Z TypeError: The list[0] argument must be a Buffer. Received null\n'
             '2026-01-01T00:00:02Z at TCPPeer.peer.localPublicSecurity (/app/federator/src/vendors/RSKKeyedAuth.js:10)\n'
             '2026-01-01T00:00:03Z Waiting for enough peers (now 1. node N, leader L)\n')
        out=fd.log_summary(log,'2026-01-01T00:00:00Z',2,fd.parse_time('2026-01-01T00:00:04Z'))
        self.assertEqual(out['fatal_counts']['auth_type_error'],1)
        self.assertEqual(out['fresh_other_peers'],1)
        self.assertEqual(out['role'],'waiting')
        self.assertFalse(out['peer_gate_met'])

    @unittest.skipUnless(NODE, 'Node needed to test embedded probes')
    def test_node_deadline_preserves_already_collected_checks(self):
        setup="""const originalTimeout=setTimeout;setTimeout=(f,m)=>originalTimeout(f,m===45000?20:m);
          mainProbe=async(p,v,out)=>{out.checks.push({name:'main.rpc',status:'PASS'});return new Promise(()=>{});};"""
        result=subprocess.run([NODE,'-'],input=fd.NODE_CORE+'\n'+setup+'\n'+fd.NODE_ENTRY,
                              text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr[:100])
        out=json.loads(result.stdout)
        self.assertEqual(out['checks'][0],{'name':'main.rpc','status':'PASS'})
        self.assertEqual(out['checks'][-1]['failure'],'WALL_DEADLINE')

    @unittest.skipUnless(NODE, 'Node needed to test embedded probes')
    def test_owner_gate_comparison_and_saved_history_windows(self):
        case="""
        const cfg={host:'https://rpc.invalid',bridge:'0x'+'1'.repeat(40),federation:'0x'+'2'.repeat(40),multiSig:'0x'+'3'.repeat(40),fromBlock:5};
        const calls=[],checks=[];
        rpc=async(url,m,p)=>{calls.push([m,p]);if(m==='eth_chainId')return {result:'0x1e'};
          if(m==='net_version')return {result:'30'};if(m==='eth_getBlockByNumber')return {result:{number:'0x64',timestamp:'0x1'}};
          if(m==='eth_getLogs')return {result:[]};if(m==='eth_syncing')return {result:false};
          if(m==='eth_getCode')return {result:'0x1234'};if(m==='eth_call'){
            const d=p[0].data;if(d===SELECT.federation)return {result:'0x'+'0'.repeat(24)+'2'.repeat(40)};
            if(d===SELECT.required)return {result:'0x'+'0'.repeat(63)+'2'};
            if(d===SELECT.members)return {result:'0x'+'0'.repeat(62)+'20'+'0'.repeat(63)+'3'+['4','5','6'].map(x=>'0'.repeat(24)+x.repeat(40)).join('')};
            return {result:'0x'+'0'.repeat(24)+'3'.repeat(40)};
          }return {result:'0x1'};};
        chainChecks('main',cfg,30,null,2,v=>checks.push(v),'90').then(()=>console.log(JSON.stringify({calls,checks})));
        """
        out=EmbeddedNodeTests.run_js(self,case)
        gate=next(x for x in out['checks'] if x['name']=='main.members_and_gate')
        self.assertEqual(gate['members'], ['0x'+c*40 for c in ['4','5','6']])
        self.assertEqual(gate['status'],'WARN')  # 2 configured other peers over-requires a 2-of-3 federation.
        owners=[x for x in out['checks'] if '.owner.' in x['name']]
        self.assertEqual(len(owners),2)
        self.assertTrue(all(x['matches_multisig'] for x in owners))
        windows=[p[0] for m,p in out['calls'] if m=='eth_getLogs']
        self.assertIn('0x5a',[x['fromBlock'] for x in windows])


@unittest.skipUnless(NODE, 'Node needed to test embedded probes')
class ReadBoundaryTests(unittest.TestCase):
    run_js = EmbeddedNodeTests.run_js
    def test_signature_request_read_preserves_userdata_and_only_calls_read_methods(self):
        case="""
        const calls=[],encoded=[],checks=[];const originalRequire=require;
        class Interface {
          parseLog(){return {name:'Cross',args:{_tokenAddress:'0x'+'1'.repeat(40),_to:'0x'+'2'.repeat(40),_amount:'123',_symbol:'ETH',_decimals:18,_granularity:'1',_userData:'0xaabb'}};}
          encodeFunctionData(name,args){encoded.push({name,args});return '0x01020304';}
        }
        require=p=>p==='ethers'?{ethers:{utils:{Interface}}}:originalRequire(p);require.resolve=p=>p;
        file=p=>'[]';
        rpc=async(u,m,p)=>{calls.push({method:m,params:p});return m==='eth_call'?{result:'0x'+'3'.repeat(64)}:{result:{hash:'0x'+'5'.repeat(64),transactionHash:'0x'+'5'.repeat(64)}};};
        const chains={side:{host:'https://source.invalid',bridge:'0x'+'4'.repeat(40)},main:{host:'https://dest.invalid',federation:'0x'+'6'.repeat(40)}};
        const e={address:chains.side.bridge,transactionHash:'0x'+'5'.repeat(64),blockHash:'0x'+'7'.repeat(64),logIndex:'0x1'};
        signatureReadBoundary(chains,e,v=>checks.push(v)).then(()=>console.log(JSON.stringify({calls,checks,encoded})));
        """
        out=self.run_js(case)
        self.assertEqual(out['encoded'][0]['name'],'getTransactionIdU')
        self.assertEqual(out['encoded'][0]['args'][-1],'0xaabb')
        self.assertEqual([x['method'] for x in out['calls']],['eth_call','eth_getTransactionByHash','eth_getTransactionReceipt'])
        self.assertEqual(out['checks'][0]['status'],'PASS')

    def test_equal_member_counts_with_different_addresses_warn(self):
        case="console.log(JSON.stringify(membershipSummary([{name:'main.members_and_gate',members:['0x'+'1'.repeat(40)]},{name:'side.members_and_gate',members:['0x'+'2'.repeat(40)]}])));"
        out=self.run_js(case)
        self.assertEqual(out['status'],'WARN')
        self.assertFalse(out['same_members'])

    def test_provider_failure_fields_do_not_taint_rpc_or_oracle_reports(self):
        case="""const {EventEmitter}=require('events');let payload={};
          https.request=(u,o,cb)=>{const req=new EventEmitter();req.write=()=>{};req.destroy=()=>{};
            req.end=()=>{const res=new EventEmitter();res.statusCode=200;res.destroy=()=>{};cb(res);res.emit('data',Buffer.from(JSON.stringify(payload)));res.emit('end');};return req;};
          readPublic=()=>({main_json:'rskmainnet.json',side_json:'mainnet.json',minimum_peers:2,signer:null});
          resources=()=>({checkpoints:{}});versions=()=>({gas_strategy:'v2_present'});chainChecks=async()=>{};
          file=p=>p.endsWith('rskmainnet.json')?JSON.stringify({bridge:PROFILE['eth-rsk'].rsk}):p.endsWith('mainnet.json')?JSON.stringify({bridge:PROFILE['eth-rsk'].bridge}):p.endsWith('peers.config.js')?'module.exports={"peers":[]}':p.endsWith('etherscan.key')?'FAKE_READ_API_KEY':'{}';
          (async()=>{const out=[];for(const bad of ['OPAQUE_API_CREDENTIAL',{privateKey:'OPAQUE_NESTED_CREDENTIAL'}]){
            payload={failure:bad};const rpcResult=await rpc('https://rpc.invalid','eth_chainId',[]);
            const report=await mainProbe('eth-rsk',false);out.push({rpc:rpcResult,oracle:report.checks.filter(x=>x.name.startsWith('etherscan.'))});}
            console.log(JSON.stringify(out));})();"""
        out=self.run_js(case)
        serialized=json.dumps(out)
        self.assertNotIn('OPAQUE_',serialized)
        self.assertNotIn('FAKE_READ_API_KEY',serialized)
        for item in out:
            self.assertEqual(item['rpc']['failure'],'RPC_SHAPE')
            self.assertTrue(all(x['failure']=='JSON_SHAPE' for x in item['oracle']))

    def test_fixed_transport_failures_remain_classified_without_extra_payload(self):
        case="""request=async()=>({failure:'DNS',unexpected:'OPAQUE_TRANSPORT_EXTRA'});
          rpc('https://rpc.invalid','eth_chainId',[]).then(x=>console.log(JSON.stringify(x)));"""
        out=self.run_js(case)
        self.assertEqual(out['failure'],'DNS')
        self.assertNotIn('OPAQUE_',json.dumps(out))

    def test_wallet_scalar_shaped_read_credential_causes_no_oracle_request(self):
        case="""let requests=0,key='';request=async()=>{requests++;return {body:{status:'1',result:{SafeGasPrice:'1'}}};};
          readPublic=()=>({main_json:'rskmainnet.json',side_json:'mainnet.json',minimum_peers:2,signer:null});
          resources=()=>({checkpoints:{}});versions=()=>({gas_strategy:'v2_present'});chainChecks=async()=>{};
          file=p=>p.endsWith('rskmainnet.json')?JSON.stringify({bridge:PROFILE['eth-rsk'].rsk}):p.endsWith('mainnet.json')?JSON.stringify({bridge:PROFILE['eth-rsk'].bridge}):p.endsWith('peers.config.js')?'module.exports={"peers":[]}':p.endsWith('etherscan.key')?key:'{}';
          (async()=>{const out=[];for(const candidate of ['1'.repeat(64),'0x'+'a'.repeat(64)]){key=candidate;requests=0;const report=await mainProbe('eth-rsk',false);out.push({requests,checks:report.checks.filter(x=>x.name.startsWith('etherscan.'))});}console.log(JSON.stringify(out));})();"""
        out=self.run_js(case)
        for item in out:
            self.assertEqual(item['requests'],0)
            self.assertTrue(any(x.get('failure')=='CREDENTIAL_SHAPE_REJECTED' for x in item['checks']))

    def test_http_null_json_fails_instead_of_stalling_until_wall_deadline(self):
        case="""
        const {EventEmitter}=require('events');
        https.request=(u,o,cb)=>{const req=new EventEmitter();req.end=()=>{const res=new EventEmitter();res.statusCode=200;res.destroy=()=>{};cb(res);res.emit('data',Buffer.from('null'));res.emit('end');};req.destroy=()=>{};return req;};
        Promise.race([request('https://rpc.invalid'),new Promise(r=>setTimeout(()=>r({failure:'STALL'}),100))]).then(x=>console.log(JSON.stringify(x)));
        """
        out=self.run_js(case)
        self.assertNotEqual(out['failure'],'STALL')
        self.assertEqual(out['failure'],'JSON_SHAPE')

    def test_http_failure_and_body_limit_never_expose_body(self):
        case="""
        const {EventEmitter}=require('events');let status=403;
        https.request=(u,o,cb)=>{const req=new EventEmitter();req.destroy=()=>{};req.end=()=>{const res=new EventEmitter();res.statusCode=status;res.destroy=()=>{};cb(res);res.emit('data',Buffer.alloc(MAX_BODY+1,120));res.emit('end');};return req;};
        (async()=>{const a=await request('https://user:key@rpc.invalid');status=200;const b=await request('https://rpc.invalid');console.log(JSON.stringify([a,b]));})();
        """
        out=self.run_js(case)
        self.assertEqual(out[0]['failure'],'HTTP')
        self.assertEqual(out[0]['http_status'],403)
        self.assertEqual(out[1]['failure'],'BODY_LIMIT')
        self.assertNotIn('user:key',json.dumps(out))


class FinalStateTests(unittest.TestCase):
    setUp=DiagnosticTests.setUp
    tearDown=DiagnosticTests.tearDown
    cli=DiagnosticTests.cli
    def test_versions_do_not_require_public_config_file(self):
        (self.cfg/'config.js').unlink()
        self.docker.payload={'versions':{'node':'v14'},'checks':[]}
        result,out=self.cli(['--versions-only'])
        self.assertIn('v14',out)

    def test_running_to_exited_during_probe_is_fail_with_final_state(self):
        original=self.docker.run
        def execute(args,**kw):
            result=original(args,**kw)
            if args[:2]==['docker','exec']:
                self.docker.running=False
            return result
        self.docker.run=execute
        dest=self.repo/'crash.json'
        result,_=self.cli(['--samples','1','--output',str(dest)])
        report=json.loads(dest.read_text())
        self.assertEqual(report['status'],'FAIL')
        self.assertFalse(report['container_end']['running'])
        self.assertEqual(report['container_end']['exit'],1)

    def test_mid_diagnosis_guard_failure_retains_runtime_evidence(self):
        original=self.docker.run
        def execute(args,**kw):
            result=original(args,**kw)
            if args[:2]==['docker','exec']:
                self.docker.identity='8'*64
            return result
        self.docker.run=execute
        dest=self.repo/'changed.json'
        with self.assertRaises(fd.DiagnosticError):
            self.cli(['--samples','1','--output',str(dest)])
        report=json.loads(dest.read_text())
        self.assertEqual(report['runtime_samples'][0]['checks'][0]['chain_id'],30)
        self.assertEqual(report['status'],'FAIL')

    def test_runner_clamps_timeout_and_rejects_exhausted_budget(self):
        result=type('Response',(),{'stdout':'{}','stderr':'','returncode':0})()
        runner=fd.Runner();runner.deadline=12
        with patch('federator_dependencies.time.monotonic',return_value=10),patch('federator_dependencies.subprocess.run',return_value=result) as execute:
            runner.run(['docker','inspect','x'],timeout=10)
            self.assertEqual(execute.call_args.kwargs['timeout'],2)
        with patch('federator_dependencies.time.monotonic',return_value=12),patch('federator_dependencies.subprocess.run',side_effect=AssertionError('must not start command')):
            with self.assertRaises(fd.DiagnosticError):runner.run(['docker','inspect','x'])


@unittest.skipUnless(NODE, 'Node needed to test embedded probes')
class ProbeLifetimeTests(unittest.TestCase):
    def test_completed_probe_exits_even_with_pending_dns_handle(self):
        setup="""mainProbe=async(p,v,out)=>{setInterval(()=>{},1000);out.checks.push({name:'p2p.dns',status:'WARN',failure:'TIMEOUT'});return out;};"""
        try:
            result=subprocess.run([NODE,'-','bsc-rsk','--budget-ms','100'],
                input=fd.NODE_CORE+'\n'+setup+'\n'+fd.NODE_ENTRY,text=True,capture_output=True,timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('diagnostic remained alive after emitting evidence')
        self.assertEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)['checks'][0]['failure'],'TIMEOUT')

    def test_partial_deadline_uses_passed_budget_and_forces_probe_exit(self):
        setup="""mainProbe=async(p,v,out)=>{out.checks.push({name:'main.rpc',status:'PASS'});setInterval(()=>{},1000);return new Promise(()=>{});};"""
        try:
            result=subprocess.run([NODE,'-','bsc-rsk','--budget-ms','100'],
                input=fd.NODE_CORE+'\n'+setup+'\n'+fd.NODE_ENTRY,text=True,capture_output=True,timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('probe ignored the passed child deadline')
        out=json.loads(result.stdout)
        self.assertEqual(out['checks'][0]['name'],'main.rpc')
        self.assertEqual(out['checks'][-1]['failure'],'WALL_DEADLINE')


class UtilityLifetimeTests(unittest.TestCase):
    setUp=DiagnosticTests.setUp
    tearDown=DiagnosticTests.tearDown
    def test_remaining_budget_is_forwarded_and_only_named_offline_utility_is_removed(self):
        self.docker.running=False
        original=self.docker.run
        commands=[]
        def execute(args,**kw):
            commands.append(args)
            if args[:2]==['docker','run']:raise fd.DiagnosticError('timeout')
            if args[:2]==['docker','rm']:return ''
            return original(args,**kw)
        self.docker.run=execute;self.docker.deadline=15
        container=fd.Container(self.repo,'bsc-rsk','bridge-sc_federation_1',self.docker)
        with patch('federator_dependencies.time.monotonic',return_value=10):
            result=fd.runtime_probe(container,'bsc-rsk',True,self.docker,50)
        run=next(x for x in commands if x[:2]==['docker','run'])
        budget=int(run[run.index('--budget-ms')+1]);self.assertLessEqual(budget,4000)
        name=run[run.index('--name')+1]
        remove=next(x for x in commands if x[:2]==['docker','rm'])
        self.assertEqual(remove,['docker','rm','--force',name])
        self.assertTrue(name.startswith('federator-dependency-versions-'))
        self.assertNotIn('bridge-sc_federation_1',remove)
        self.assertEqual(result['offline_utility_cleanup'],'completed')


if __name__ == '__main__':
    unittest.main()
