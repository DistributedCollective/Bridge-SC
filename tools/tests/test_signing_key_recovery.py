from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import federator_signing_key as m
except ImportError:m=None


class SigningKeyRecoveryTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(m,'automatic key recovery is not implemented')

    def node(self,root):
        class Node:
            cfg=root;expected_uid=__import__('os').getuid()
            def inspect(self):return {'running':False}
            def key_ready(self):
                if not (self.cfg/'federator.key').is_file():raise RuntimeError('not installed')
        return Node()

    def test_existing_original_file_never_queries_aws_or_prompts_for_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            node=self.node(Path(tmp));(node.cfg/'federator.key').write_text('a'*64);(node.cfg/'federator.key').chmod(0o600)
            with patch.object(m.r,'restore_original_key',side_effect=AssertionError('AWS must not be queried')):
                value=m.restore(node,request_key=lambda:(_ for _ in ()).throw(AssertionError('must not prompt')))
            self.assertEqual(value,'existing')

    def test_aws_discovery_failure_falls_back_to_hidden_manual_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            node=self.node(Path(tmp));requests=[]
            with patch.object(m.r,'restore_original_key',side_effect=m.r.RecoveryError('access denied')):
                value=m.restore(node,request_key=lambda:requests.append(True) or 'b'*64)
            self.assertEqual(value,'manual');self.assertEqual(requests,[True])
            self.assertEqual((node.cfg/'federator.key').stat().st_mode&0o777,0o600)

    def test_discovered_instance_secret_is_used_without_asking_operator_for_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            node=self.node(Path(tmp))
            def recover(n,confirm):
                self.assertTrue(confirm('Restore ORIGINAL instance secret fixture/name?'))
                m.r.install_key(n.cfg,'c'*64,n.expected_uid);return True
            with patch.object(m.r,'restore_original_key',side_effect=recover):
                value=m.restore(node,request_key=lambda:(_ for _ in ()).throw(AssertionError('must not prompt')))
            self.assertEqual(value,'aws')

if __name__=='__main__':unittest.main()
