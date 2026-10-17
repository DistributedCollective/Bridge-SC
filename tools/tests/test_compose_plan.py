import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent


class ComposePlanTests(unittest.TestCase):
    def module(self):
        path = TOOLS / 'federator_compose_plan.py'
        self.assertTrue(path.is_file(), 'Agent-independent Compose preparation is missing')
        spec = importlib.util.spec_from_file_location('federator_compose_plan', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_only_application_and_its_referenced_resources_remain(self):
        m = self.module()
        model = {
            'name': 'bridge-sc',
            'services': {
                'federation': {'image': 'repair', 'environment': {'LITERAL': '$$KEEP'},
                    'networks': {'default': None}, 'volumes': [{'type': 'bind', 'source': '/cfg', 'target': '/app'}]},
                'datadog': {'environment': {'DD_API_KEY': '${DATADOG_API_KEY}', 'DD_TAGS': 'FED_ID:${FED_ID}'}}
            },
            'networks': {'default': {'name': 'bridge-sc_default'}, 'agent-only': {}},
            'volumes': {'agent-private': {'external': True}},
            'secrets': {'agent-key': {'file': '/private/agent-key'}}}
        selected = m.federation_only(model)
        self.assertEqual(selected['services'], {'federation': model['services']['federation']})
        self.assertEqual(selected['networks'], {'default': {'name': 'bridge-sc_default'}})
        self.assertNotIn('volumes', selected)
        self.assertNotIn('secrets', selected)
        self.assertNotIn('DATADOG_API_KEY', json.dumps(selected))
        self.assertNotIn('FED_ID', json.dumps(selected))
        self.assertEqual(selected['services']['federation']['environment']['LITERAL'], '$$KEEP')

    def test_app_dependency_is_not_silently_dropped(self):
        m = self.module()
        for field in ('depends_on', 'links', 'volumes_from'):
            with self.subTest(field=field), self.assertRaises(m.PlanError):
                m.federation_only({'services': {'federation': {field: ['datadog']}}})

    def test_generated_base_removes_only_the_obsolete_version_field(self):
        m = self.module()
        raw = 'version: "3"\nservices:\n  federation:\n    environment:\n      version: application-setting\n'
        self.assertEqual(m.without_version(raw), 'services:\n  federation:\n    environment:\n      version: application-setting\n')

    def test_cli_never_overwrites_destination_or_leaks_input_on_failure(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'keep.json';path.write_text('existing')
            process = subprocess.run([sys.executable, str(TOOLS/'federator_compose_plan.py'), '--model', str(path)],
                input=json.dumps({'services': {'federation': {}, 'datadog': {'private': 'DUMMY_SECRET'}}}),
                text=True, capture_output=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(path.read_text(), 'existing')
            self.assertNotIn('DUMMY_SECRET', process.stdout + process.stderr)

    def test_actual_compose_does_not_interpolate_agent_and_preserves_app_values(self):
        m = self.module()
        available = subprocess.run(['docker', 'compose', 'version'], capture_output=True).returncode == 0
        if not available:
            self.skipTest('Compose plugin unavailable; pure selection tests still apply')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root/'base.yml'
            base.write_text(m.without_version((REPO/'docker-compose-prod.yml').read_text()))
            override = root/'override.json'
            override.write_text(json.dumps({'services': {'federation': {
                'image': 'sovryn/fed-tokenbridge:fixture',
                'environment': {'APP_VALUE': '${APP_INPUT}', 'APP_LITERAL': '$$KEEP'}}}}))
            env = {k:v for k,v in os.environ.items() if k not in ('DATADOG_API_KEY','FED_ID','KEEP')}
            env.update(FED_ENV='mainnet-ETH-RSK', APP_INPUT='resolved')
            args = ['docker','compose','--project-directory',str(root),'--project-name','bridge-sc']
            first = subprocess.run(args+['-f',str(base),'-f',str(override),'config','--no-interpolate','--format','json'],
                env=env,text=True,capture_output=True)
            self.assertEqual(first.returncode,0,first.stderr)
            selected = root/'application.json'
            selected.write_text(json.dumps(m.federation_only(json.loads(first.stdout))))
            second = subprocess.run(args+['-f',str(selected),'config','--format','json'],env=env,text=True,capture_output=True)
            self.assertEqual(second.returncode,0,second.stderr)
            model = json.loads(second.stdout)
            self.assertEqual(list(model['services']), ['federation'])
            self.assertEqual(model['services']['federation']['environment'],
                             {'APP_VALUE':'resolved','APP_LITERAL':'$$KEEP'})
            # Compose serializes literal dollars escaped for re-reading its output.
            selected.write_text(second.stdout)
            third = subprocess.run(args+['-f',str(selected),'config','--format','json'],
                env=env,text=True,capture_output=True)
            self.assertEqual(third.returncode,0,third.stderr)
            self.assertEqual(json.loads(third.stdout)['services']['federation']['environment'],
                             {'APP_VALUE':'resolved','APP_LITERAL':'$$KEEP'})
            for warning in ('DATADOG_API_KEY','FED_ID','obsolete'):
                self.assertNotIn(warning, first.stderr + second.stderr)


if __name__ == '__main__':
    unittest.main()
