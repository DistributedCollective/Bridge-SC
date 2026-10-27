import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'dd_agent_recovery.py'


class RegistryCutoverTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'Agent-only recovery tool is not implemented')
        spec = importlib.util.spec_from_file_location('dd_agent_recovery_under_test', MODULE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.cid = 'a' * 64
        self.path = '/var/lib/docker/containers/' + self.cid + '/' + self.cid + '-json.log'
        self.key = 'file:' + self.path
        self.registry = {'Version': 2, 'Registry': {
            self.key: {'Offset': '12', 'LastUpdated': '2025-11-25T16:23:24Z', 'TailingMode': 'beginning', 'IngestionTimestamp': 5},
            'file:/other.log': {'Offset': '100', 'LastUpdated': '2026-10-16T00:00:00Z'},
            'docker:' + self.cid: {'Offset': '2025-11-25T16:23:24Z'}}}

    def test_only_selected_file_offset_changes_and_input_is_unchanged(self):
        before = copy.deepcopy(self.registry)
        result = self.m.cutover_registry(self.registry, self.path, 145, '2026-10-16T01:00:00Z')
        self.assertEqual(self.registry, before)
        self.assertEqual(result['Registry'][self.key]['Offset'], '145')
        self.assertEqual(result['Registry'][self.key]['TailingMode'], 'beginning')
        self.assertEqual(result['Registry']['file:/other.log'], before['Registry']['file:/other.log'])
        self.assertEqual(result['Registry']['docker:' + self.cid], before['Registry']['docker:' + self.cid])

    def test_unknown_or_missing_registry_source_is_refused(self):
        for reg in ([], {'Version': 1, 'Registry': {}}, {'Version': 2, 'Registry': {}}, {'Version': True, 'Registry': self.registry['Registry']}):
            with self.assertRaises(self.m.RepairError):
                self.m.cutover_registry(reg, self.path, 145, '2026-10-16T01:00:00Z')

    def test_invalid_or_decreasing_offsets_are_refused(self):
        for offset in ('2025-11-25T00:00:00Z', '-1', '123junk'):
            reg = copy.deepcopy(self.registry); reg['Registry'][self.key]['Offset'] = offset
            with self.assertRaises(self.m.RepairError):
                self.m.cutover_registry(reg, self.path, 145, '2026-10-16T01:00:00Z')
        for target in (11, -1, True):
            with self.assertRaises(self.m.RepairError):
                self.m.cutover_registry(self.registry, self.path, target, '2026-10-16T01:00:00Z')

    def test_default_empty_mode_is_preserved_with_current_offset(self):
        reg = copy.deepcopy(self.registry)
        reg['Registry'][self.key]['TailingMode'] = ''
        before = copy.deepcopy(reg)
        result = self.m.cutover_registry(reg, self.path, 145, '2026-10-16T08:55:00Z')
        self.assertEqual(result['Registry'][self.key]['TailingMode'], '')
        self.assertEqual(result['Registry'][self.key]['Offset'], '145')
        self.assertEqual(reg, before)
        for mode in ('forceBeginning', 'forceEnd', 'unknown', None, 0):
            reg['Registry'][self.key]['TailingMode'] = mode
            with self.assertRaises(self.m.RepairError):
                self.m.cutover_registry(reg, self.path, 145, '2026-10-16T08:55:00Z')

    def test_configuration_preserves_credentials_and_other_settings(self):
        cfg = {'api_key': 'private-fixture-do-not-print', 'hostname': 'existing', 'logs_config': {'container_collect_all': True}}
        before = copy.deepcopy(cfg)
        result = self.m.persistent_config(cfg, {})
        self.assertEqual(cfg, before)
        self.assertEqual(result['api_key'], before['api_key'])
        self.assertEqual(result['hostname'], 'existing')
        self.assertEqual(result['logs_config']['run_path'], self.m.PERSISTENT_PATH)
        self.assertTrue(result['logs_config']['container_collect_all'])

    def test_environment_or_socket_mode_conflict_is_refused(self):
        for env in ({'DD_CONF_PATH': '/different'}, {'DD_CONFD_PATH': '/different'}, {'DD_CONFIG_FILE': '/different.yaml'}, {'DD_LOGS_CONFIG_RUN_PATH': '/different'}, {'DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE': 'false'}):
            with self.assertRaises(self.m.RepairError):
                self.m.persistent_config({}, env)
        with self.assertRaises(self.m.RepairError):
            self.m.persistent_config({'logs_config': {'docker_container_use_file': False}}, {})
        with self.assertRaises(self.m.RepairError):
            self.m.persistent_config({'confd_path': '/different'}, {})

    def test_complete_byte_boundary_preserves_partial_record_for_later_read(self):
        first = (json.dumps({'log': 'public fixture ü\n', 'time': '2026-10-16T01:00:00.123456789Z'}) + '\n').encode()
        partial = b'{"log":"not-complete'
        result = self.m.tail_boundary(first + partial, 0)
        self.assertEqual(result['offset'], len(first))
        self.assertEqual(result['last_record_utc'], '2026-10-16T01:00:00.123456789Z')
        self.assertNotIn('public fixture', json.dumps(result))
        with self.assertRaises(self.m.RepairError):
            self.m.tail_boundary(partial, 0)

    def fixtures(self):
        agent = {'id': 'b'*64, 'image': 'sha256:'+'c'*64, 'user': '', 'env': [],
                 'state': {'Running': False, 'Paused': False, 'Status': 'exited', 'StartedAt': '2026-10-16T00:00:00Z'},
                 'mounts': [{'Type': 'volume', 'Destination': '/var/log/datadog', 'Name': 'agent_log_volume', 'RW': True},
                            {'Type': 'bind', 'Source': '/var/lib/docker/containers', 'Destination': '/var/lib/docker/containers', 'RW': False}]}
        base = '/home/ubuntu/Bridge-SC/federator-env/mainnet-ETH-RSK'
        source = {'id': self.cid, 'image': 'sha256:'+'d'*64, 'state': {'Running': True, 'StartedAt': '2026-10-16T00:00:00Z'},
                  'log_config': {'Type': 'json-file'}, 'log_path': self.path,
                  'mounts': [{'Destination': '/app/federator/config', 'Source': base}, {'Destination': '/app/federator/db', 'Source': base+'/db'}]}
        return agent, source

    def test_scope_requires_stopped_agent_running_eth_and_existing_volume(self):
        agent, source = self.fixtures()
        self.assertEqual(self.m.scope(agent, source), (self.path, 'agent_log_volume'))
        for kind in ('running_agent', 'paused_agent', 'stopped_source', 'bsc_source', 'missing_volume'):
            a, c = copy.deepcopy(agent), copy.deepcopy(source)
            if kind == 'running_agent': a['state']['Running'] = True
            if kind == 'paused_agent': a['state']['Paused'] = True
            if kind == 'stopped_source': c['state']['Running'] = False
            if kind == 'bsc_source': c['mounts'][0]['Source'] = '/home/ubuntu/Bridge-SC/federator-env/mainnet-BSC-RSK'
            if kind == 'missing_volume': a['mounts'] = a['mounts'][1:]
            with self.assertRaises(self.m.RepairError): self.m.scope(a, c)

    def test_changed_process_or_environment_refuses_apply(self):
        agent, source = self.fixtures()
        new = copy.deepcopy(source); new['state']['StartedAt'] = '2026-10-16T00:01:00Z'
        with self.assertRaises(self.m.RepairError): self.m.ensure_same(agent, source, agent, new)
        new_agent = copy.deepcopy(agent); new_agent['env_fingerprint'] = 'changed'
        with self.assertRaises(self.m.RepairError): self.m.ensure_same(agent, source, new_agent, source)

    def test_mount_order_does_not_change_identity_or_layout(self):
        agent, source = self.fixtures()
        new_agent, new_source = copy.deepcopy(agent), copy.deepcopy(source)
        new_agent['mounts'].reverse(); new_source['mounts'].reverse()
        self.m.ensure_same(agent, source, new_agent, new_source)

    def test_real_mount_changes_still_refuse_apply(self):
        agent, source = self.fixtures()
        for role in ('agent', 'source'):
            for key, value in (('Source', '/different'), ('Destination', '/different'), ('RW', False), ('Type', 'tmpfs')):
                new_agent, new_source = copy.deepcopy(agent), copy.deepcopy(source)
                changed = new_agent if role == 'agent' else new_source
                changed['mounts'][0][key] = value
                with self.assertRaises(self.m.RepairError):
                    self.m.ensure_same(agent, source, new_agent, new_source)

    def test_agent_environment_backup_does_not_copy_api_key(self):
        payload = {'env': ['DD_API_KEY=private-fixture-not-for-report', 'DD_LOGS_CONFIG_RUN_PATH=/opt/datadog-agent/run']}
        class Double(self.m.Docker):
            def call(self, args, **kwargs): return json.dumps(payload).encode()
        inspected = Double().inspect('datadog-agent', agent=True)
        self.assertTrue(inspected['api_key_present'])
        self.assertNotIn('private-fixture-not-for-report', json.dumps(inspected))
        self.assertEqual(inspected['env'], ['DD_LOGS_CONFIG_RUN_PATH=/opt/datadog-agent/run'])

    def test_volume_metadata_reader_gets_only_explicit_read_search_capability(self):
        class Double(self.m.Docker):
            def __init__(self): self.calls = []
            def call(self, args, **kwargs):
                self.calls.append(args)
                return None if args[0] == 'inspect' else b'{}'
        d = Double()
        d.helper('fixture-image', 'pass', [('fixture-volume', '/agent-logs', 'volume')], user='0:0', read_search=True)
        command = d.calls[0]
        self.assertIn('--read-only', command)
        self.assertEqual(command[command.index('--network') + 1], 'none')
        self.assertEqual(command[command.index('--cap-drop') + 1], 'ALL')
        self.assertEqual(command[command.index('--cap-add') + 1], 'DAC_READ_SEARCH')
        d = Double(); d.helper('fixture-image', 'pass', [])
        self.assertNotIn('--cap-add', d.calls[0])

    def test_legacy_socket_cursor_requires_confirmed_file_precedence(self):
        with self.assertRaises(self.m.RepairError):
            self.m.ensure_file_collection(self.registry, self.cid, {}, {})
        self.m.ensure_file_collection(self.registry, self.cid, {'logs_config': {'docker_container_force_use_file': True}}, {})
        with self.assertRaises(self.m.RepairError):
            self.m.ensure_file_collection(self.registry, self.cid,
                {'logs_config': {'docker_container_force_use_file': True}},
                {'DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE': 'false'})


    def test_shadow_mounts_are_refused_before_any_write(self):
        agent, source = self.fixtures()
        for path in (self.m.PERSISTENT_PATH, self.m.PERSISTENT_PATH + '/registry.json', str(Path(self.path).parent)):
            new = copy.deepcopy(agent)
            new['mounts'].append({'Type': 'bind', 'Source': source['mounts'][0]['Source'], 'Destination': path, 'RW': True})
            with self.assertRaises(self.m.RepairError): self.m.scope(new, source)

    def test_custom_entrypoint_and_changed_agent_epoch_are_refused(self):
        agent, source = self.fixtures()
        new = copy.deepcopy(agent); new['entrypoint'] = ['/custom-launcher']
        with self.assertRaises(self.m.RepairError): self.m.scope(new, source)
        new = copy.deepcopy(agent); new['state']['StartedAt'] = '2026-10-16T00:01:00Z'
        with self.assertRaises(self.m.RepairError): self.m.ensure_same(agent, source, new, source)

    def test_parent_components_and_source_bind_output_are_refused(self):
        with self.assertRaises(self.m.RepairError): self.m.safe_path('/tmp/federator-env/../federator-env/repair')
        agent, source = self.fixtures()
        with self.assertRaises(self.m.RepairError):
            self.m.ensure_output_outside_source(Path(source['mounts'][1]['Source']) / 'repair', source)

    def test_forced_start_modes_are_refused(self):
        reg = copy.deepcopy(self.registry); reg['Registry'][self.key]['TailingMode'] = 'forceBeginning'
        with self.assertRaises(self.m.RepairError): self.m.cutover_registry(reg, self.path, 145, '2026-10-16T01:00:00Z')
        for value in ({'logs': [{'start_position': 'forceBeginning'}]}, {'nested': [{'start_position': 'forceEnd'}]}):
            with self.assertRaises(self.m.RepairError): self.m.ensure_registry_start_modes(value)
        self.m.ensure_registry_start_modes({'logs': [{'start_position': 'beginning'}]})
        self.m.ensure_registry_start_modes({'logs': [{'start_position': 'end'}]})

    def config_archive(self, link=None):
        import io, tarfile
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w') as archive:
            row = tarfile.TarInfo('datadog.yaml')
            if link:
                row.type = tarfile.SYMTYPE; row.linkname = link
            else:
                payload = b'logs_enabled: true\n'; row.size = len(payload)
            archive.addfile(row, None if link else io.BytesIO(payload))
        return data.getvalue()

    def test_standard_agent_config_alias_resolves_to_verified_target(self):
        for link in ('/etc/datadog-agent/datadog-docker.yaml', 'datadog-docker.yaml'):
            data = self.config_archive(link)
            class Double(self.m.Docker):
                def call(self, args, **kwargs): return data
            agent, source = self.fixtures()
            self.assertEqual(self.m.config_path(Double(), agent), '/etc/datadog-agent/datadog-docker.yaml')
        data = self.config_archive()
        self.assertEqual(self.m.config_path(Double(), agent), self.m.AGENT_CONFIG)

    def test_custom_config_alias_or_mounted_target_is_refused(self):
        agent, source = self.fixtures()
        for link in ('/app/federator/config/config.js', '../config.yaml'):
            data = self.config_archive(link)
            class Double(self.m.Docker):
                def call(self, args, **kwargs): return data
            with self.assertRaises(self.m.RepairError): self.m.config_path(Double(), agent)
        agent['mounts'].append({'Type': 'bind', 'Destination': '/etc/datadog-agent/datadog-docker.yaml', 'Source': source['mounts'][0]['Source'], 'RW': True})
        with self.assertRaises(self.m.RepairError): self.m.scope(agent, source)


if __name__ == '__main__':
    unittest.main()
