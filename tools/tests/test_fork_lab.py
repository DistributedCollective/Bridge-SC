import importlib.util
from pathlib import Path
import unittest

class ForkBoundaryTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'fork_lab.py'
        self.assertTrue(path.exists(),'fork harness absent')
        spec=importlib.util.spec_from_file_location('fork_lab',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    def test_upstream_rejects_all_write_and_impersonation_methods(self):
        m=self.module()
        for method in ('eth_sendRawTransaction','eth_sendTransaction','anvil_setBalance','anvil_setStorageAt','anvil_impersonateAccount','evm_mine'):
            with self.subTest(method=method),self.assertRaises(m.LabError):m.assert_read(method)
        for method in ('eth_chainId','eth_getBlockByNumber','eth_getStorageAt','eth_getTransactionReceipt','eth_getLogs'):m.assert_read(method)
    def test_local_write_boundary_rejects_foreign_or_unowned_endpoint(self):
        m=self.module()
        allowed={'http://127.0.0.1:19401'}
        for url in ('https://public-node.rsk.co','http://localhost:19401','http://127.0.0.1:8545','http://192.168.1.1:19401','http://127.0.0.1:19401/redirect'):
            with self.subTest(url=url),self.assertRaises(m.LabError):m.assert_owned(url,allowed)
        m.assert_owned('http://127.0.0.1:19401',allowed)
    def test_local_receipts_do_not_fall_through_to_mainnet(self):
        m=self.module();known={'0x'+'a'*64}
        self.assertTrue(m.should_read_upstream('eth_getTransactionReceipt',['0x'+'a'*64],100,known))
        self.assertFalse(m.should_read_upstream('eth_getTransactionReceipt',['0x'+'b'*64],100,known))
        self.assertFalse(m.should_read_upstream('eth_sendRawTransaction',['0xdead'],100,known))

    def test_manifest_rejects_wrong_or_duplicate_chain_and_bad_receipts(self):
        m=self.module()
        for manifest in ({}, {'events':[{'chain':1,'tx':'bad'}]}, {'events':[{'chain':56,'tx':'0x'+'a'*64}]}, {'events':[{'chain':1,'tx':'0x'+'a'*64},{'chain':1,'tx':'0x'+'a'*64}]}):
            with self.assertRaises(m.LabError):m.validate_inputs(manifest)
        self.assertEqual(len(m.validate_inputs({'events':[{'chain':1,'tx':'0x'+'a'*64},{'chain':30,'tx':'0x'+'b'*64}]})),2)


class DockerEvidenceTests(unittest.TestCase):
    def module(self):
        return ForkBoundaryTests().module()

    def test_docker_logs_retain_the_fatal_stderr(self):
        from unittest.mock import patch
        import subprocess
        m=self.module();lab=object.__new__(m.DockerLab)
        result=subprocess.CompletedProcess([],0,stdout='ordinary log\n',stderr='TypeError: null binding\n')
        with patch.object(m.subprocess,'run',return_value=result):
            self.assertIn('TypeError',lab.docker(['logs','owned-worker']))
            self.assertNotIn('TypeError',lab.docker(['inspect','owned-worker']))

    def test_cleanup_refuses_a_foreign_container(self):
        from unittest.mock import Mock
        m=self.module();lab=object.__new__(m.DockerLab);lab.token='a'*12;lab.report={}
        lab.docker=Mock(return_value='{"id":"'+('b'*64)+'","owner":"other-session"}')
        lab.remove('foreign')
        self.assertEqual(lab.docker.call_count,1)
        self.assertIn('Cleanup ownership mismatch',lab.report['cleanupErrors'][0])

    def test_gateway_never_forwards_a_write_to_upstream(self):
        from unittest.mock import patch
        m=self.module();gateway=m.Gateway({1:'https://mainnet.invalid',30:'https://mainnet.invalid'})
        try:
            with patch.object(m,'rpc',side_effect=AssertionError('mainnet request attempted')) as call:
                # Use the original RPC client to exercise the real HTTP routing guard.
                import json,urllib.request
                request=urllib.request.Request(gateway.url(1,'upstream'),data=json.dumps({'jsonrpc':'2.0','id':1,'method':'eth_sendRawTransaction','params':['0xdead']}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request) as response:result=json.load(response)
                self.assertEqual(result['error']['code'],-32091)
                call.assert_not_called()
        finally:gateway.close()

    def test_manifest_accepts_twenty_events_but_not_boolean_chain_ids(self):
        m=self.module()
        events=[{'chain':1,'tx':'0x'+format(i,'064x')} for i in range(20)]
        self.assertEqual(len(m.validate_inputs({'events':events})),20)
        with self.assertRaises(m.LabError):m.validate_inputs({'events':[{'chain':True,'tx':'0x'+'a'*64}]})

class BuildPrivacyTests(unittest.TestCase):
    def test_build_context_excludes_operator_secrets_and_database(self):
        import tempfile,subprocess
        spec=importlib.util.spec_from_file_location('build_fork_lab',Path(__file__).resolve().parents[1]/'build_fork_lab.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory)/'repo';context=Path(directory)/'context';repo.mkdir();context.mkdir()
            source='sovryn-token-bridge/federator/src/lib/module.js'
            for name in (source,'sovryn-token-bridge/abis/Federation.json','federator-env/mainnet-ETH-RSK/federator.key','federator-env/mainnet-ETH-RSK/db/lastBlock.txt','tools/fork-lab/Dockerfile','tools/fork-lab/package.json','tools/fork-lab/package-lock.json','tools/fork_lab.py','tools/fork_lab_worker.cjs'):
                target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('private-test-marker' if '/federator-env/' in '/'+name else 'public-fixture')
            tracked=(source+'\0sovryn-token-bridge/abis/Federation.json\0').encode()
            with patch.object(m.subprocess,'check_output',side_effect=[tracked,b'old-public-source']):m.populate(repo,context)
            contents=''.join(p.read_text() for p in context.rglob('*') if p.is_file())
            self.assertNotIn('private-test-marker',contents)
            self.assertTrue((context/'app/federator/src/lib/module.js').is_file())
            self.assertFalse((context/'federator-env').exists())

if __name__=='__main__':unittest.main()
