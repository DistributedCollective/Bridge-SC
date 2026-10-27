import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepare_federator_overlay as context


class ContextPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.repo=Path(self.tmp.name)/'operator-checkout'
        self.repo.mkdir()
        self.output=Path(self.tmp.name)/'safe-context'
        self.private=['federator-env/mainnet-ETH-RSK/federator.key',
            'federator-env/mainnet-ETH-RSK/db/lastBlock.txt','API.env',
            'sovryn-token-bridge/federator/config/etherscan.key',
            'sovryn-token-bridge/federator/config/federator.key','.git/private-fixture']
        for name in self.private:
            p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('FAKE_PRIVATE_DO_NOT_READ_OR_COPY')
        self.expected=[
            'sovryn-token-bridge/federator/src/lib/GasPriceAvg.js',
            'sovryn-token-bridge/federator/src/lib/GasPriceFetcher.js',
            'sovryn-token-bridge/federator/src/lib/GasServices.js',
            'sovryn-token-bridge/federator/src/lib/TransactionSender.js',
            'sovryn-token-bridge/federator/src/vendors/RSKKeyedAuth.js',
            'sovryn-token-bridge/Dockerfile.repair-overlay',
            'sovryn-token-bridge/Dockerfile.repair-overlay.dockerignore',
        ]
        self.reads=[]

    def tearDown(self):
        self.tmp.cleanup()

    def git(self,args,**kwargs):
        if args[-2:]==['-t','a'*40]:
            return type('Result',(),{'returncode':0,'stdout':b'commit\n','stderr':b''})()
        blob=args[-1]
        self.reads.append(blob.split(':',1)[1])
        self.assertIn(self.reads[-1],self.expected)
        return type('Result',(),{'returncode':0,'stdout':b'PUBLIC_REVIEWED_SOURCE\n','stderr':b''})()

    def test_sanitized_context_has_exact_public_inputs_and_no_private_files(self):
        with patch('prepare_federator_overlay.subprocess.run',side_effect=self.git):
            context.prepare(self.repo,'a'*40,self.output)
        emitted=sorted(str(p.relative_to(self.output)) for p in self.output.rglob('*') if p.is_file())
        self.assertEqual(emitted,sorted(self.expected))
        self.assertEqual(len(context.SOURCE_INPUTS),5)
        self.assertEqual(sorted(self.reads),sorted(self.expected))
        self.assertEqual(self.output.stat().st_mode & 0o777,0o700)
        for name in context.INPUTS:
            self.assertEqual((self.output/name).stat().st_mode & 0o777,0o600)
        for name in self.private:
            self.assertFalse((self.output/name).exists())
            self.assertEqual((self.repo/name).read_text(),'FAKE_PRIVATE_DO_NOT_READ_OR_COPY')

    def test_mutable_or_injected_revision_rejected_before_git(self):
        for rev in ['HEAD','main','a'*7,'a'*40+';command']:
            with self.subTest(rev=rev),patch('prepare_federator_overlay.subprocess.run',side_effect=AssertionError('must not read')):
                with self.assertRaises(context.ContextError):context.prepare(self.repo,rev,self.output)
        self.assertFalse(self.output.exists())

    def test_existing_directory_or_symlink_is_never_overwritten(self):
        self.output.mkdir();marker=self.output/'keep';marker.write_text('preserve')
        link=Path(self.tmp.name)/'link';link.symlink_to(self.output,target_is_directory=True)
        for path in [self.output,link]:
            with self.subTest(path=path),patch('prepare_federator_overlay.subprocess.run',side_effect=AssertionError('must not read')):
                with self.assertRaises(context.ContextError):context.prepare(self.repo,'a'*40,path)
        self.assertEqual(marker.read_text(),'preserve')

    def test_failed_git_read_exposes_no_raw_stderr(self):
        result=type('Result',(),{'returncode':1,'stdout':b'','stderr':b'FAKE_PRIVATE_ERROR'})()
        with patch('prepare_federator_overlay.subprocess.run',return_value=result):
            with self.assertRaises(context.ContextError) as error:context.prepare(self.repo,'a'*40,self.output)
        self.assertNotIn('FAKE_PRIVATE_ERROR',str(error.exception))


if __name__=='__main__':unittest.main()
