import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_dd_agent_legacy import LegacyDocker,m
import test_datadog_upgrade as upgrade_tests


class RegistryDiagnosticsTests(unittest.TestCase):
    def test_stopped_invalid_registry_reports_format_without_claiming_live_race(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        for raw in (b'',b'{"Version":2,"Registry":',b'{"Version":2,"Registry":{}}\0\0'):
            with self.subTest(size=len(raw)),tempfile.TemporaryDirectory() as tmp:
                d=LegacyDocker();d.files['/opt/datadog-agent/run/registry.json']=raw
                output=Path(tmp).resolve()/'inspect'
                with patch.object(u.time,'sleep'),self.assertRaises(m.RepairError) as error:u.inspect(d,output)
                self.assertIn('Stopped Agent',str(error.exception))
                report=json.loads((output/'registry-diagnostic.json').read_text())
                self.assertFalse(report['agent_running']);self.assertEqual(len(report['samples']),1)
                self.assertEqual(report['samples'][0]['bytes'],len(raw))
                self.assertEqual((output/'registry.private.json').read_bytes(),raw)
                self.assertEqual(d.writes,0);self.assertEqual(d.starts,0)

    def test_running_invalid_samples_are_bounded_and_private_contents_are_omitted(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        with tempfile.TemporaryDirectory() as tmp:
            d=LegacyDocker();d.agent['state'].update(Running=True,Status='running')
            d.files['/opt/datadog-agent/run/registry.json']=b'{"PRIVATE_URL_WITH_CREDENTIALS":'
            output=Path(tmp).resolve()/'inspect'
            with patch.object(u.time,'sleep'),self.assertRaises(m.RepairError):u.inspect(d,output)
            report=(output/'registry-diagnostic.json').read_text()
            self.assertNotIn('PRIVATE_',report)
            self.assertEqual(len(json.loads(report)['samples']),3)
            self.assertTrue(d.source['state']['Running']);self.assertEqual(d.writes,0)

    def test_padding_is_classified_without_normalizing_or_resetting_it(self):
        u=upgrade_tests.UpgradeDatadogTests.load(self)
        raw=b'{"Version":2,"Registry":{}}\0\0'
        info=u.registry_sample_metadata(raw)
        self.assertFalse(info['valid_json']);self.assertEqual(info['zero_bytes'],2)
        self.assertTrue(info['valid_after_padding_removal'])
        for broken in (b'',b'\0'*32,b'{"Version":2',b'{}PRIVATE_TRAILING_DATA'):
            self.assertFalse(u.registry_sample_metadata(broken)['valid_after_padding_removal'])
