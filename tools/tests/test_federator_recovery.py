import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import federator_recovery as fr


def event(block=120, index=1):
    return fr.Event(block, '0x' + '33' * 32, '0x' + '44' * 32, index,
                    '0x' + '11' * 20, '0x' + '22' * 20, 1000, 'ETH',
                    18, 1, b'\xaa\xbb')


def checked(block, done=True, eligible=True, index=1):
    return fr.CheckedEvent(event(block, index), done, done, 3 if done else 0, eligible)


def sample_log(bridge):
    raw = ''.join(f'{x:064x}' for x in [1000, 160, 224, 18, 1])
    raw += f'{3:064x}' + '455448' + '00' * 29
    raw += f'{2:064x}' + 'aabb' + '00' * 30
    return {'address': bridge, 'topics': [fr.CROSS_TOPIC, '0x' + '00' * 12 + '11' * 20,
                                         '0x' + '00' * 12 + '22' * 20],
            'data': '0x' + raw, 'blockNumber': '0x78', 'blockHash': '0x' + '33' * 32,
            'transactionHash': '0x' + '44' * 32, 'logIndex': '0x1', 'removed': False}


class ChainDouble:
    def __init__(self, chain, bridge, done=True, mismatch=False, bad_receipt=False):
        self.chain, self.bridge, self.done = chain, bridge, done
        self.mismatch, self.bad_receipt = mismatch, bad_receipt

    def call(self, method, params):
        if method == 'eth_chainId':
            return hex(self.chain)
        if method == 'eth_blockNumber':
            return '0x12c'
        if method == 'eth_getBlockByNumber':
            return {'number': params[0], 'hash': '0x' + '33' * 32, 'timestamp': '0x1'}
        if method == 'eth_getTransactionReceipt':
            return {'status': '0x1', 'blockNumber': '0x78',
                    'blockHash': '0x' + ('88' if self.bad_receipt else '33') * 32,
                    'transactionHash': params[0], 'logs': [sample_log(self.bridge)]}
        if method == 'eth_getLogs':
            query = params[0]
            return [sample_log(self.bridge)] if int(query['fromBlock'], 16) <= 120 <= int(query['toBlock'], 16) else []
        if method == 'eth_call':
            sig = params[0]['data'][:10]
            if sig == fr.SELECTORS['federation']:
                return '0x' + '00' * 12 + '77' * 20
            if sig == fr.SELECTORS['required']:
                return '0x' + f'{3:064x}'
            if sig == fr.SELECTORS['members']:
                return '0x' + f'{32:064x}' + f'{3:064x}' + ''.join('00' * 12 + x * 20 for x in ['11', '22', '33'])
            if sig == fr.SELECTORS['bridge_id']:
                return '0x' + '55' * 32
            if sig == fr.SELECTORS['fed_id']:
                return '0x' + '66' * 32
            if sig == fr.SELECTORS['bridge_done']:
                return '0x' + f'{int(self.done):064x}'
            if sig == fr.SELECTORS['fed_done']:
                return '0x' + f'{int(not self.done if self.mismatch else self.done):064x}'
            if sig == fr.SELECTORS['votes']:
                return '0x' + f'{3 if self.done else 0:064x}'
        raise AssertionError((method, params))


class ChainTests(unittest.TestCase):
    def test_audit_event_limit_retains_observed_unverified_blockers(self):
        direction = self.direction()
        events = [event(100 + i) for i in range(201)]
        with patch('federator_recovery.scan_cross', return_value=events):
            with self.assertRaises(fr.IncompleteAudit) as err:
                direction.audit(100, 300, 3)
        self.assertEqual(err.exception.unverified, events)
        blockers = [fr.CheckedEvent(item, False, False, 0, False)
                    for item in err.exception.unverified]
        with self.assertRaises(fr.RecoveryError):
            fr.validate_replay(140, None, blockers, 'ALL BEFORE 56:140 PROCESSED', 56)

    def test_late_audit_error_retains_earlier_verified_pending_blocker(self):
        direction = self.direction()
        events = [event(120), event(150)]
        direction.receipt_events = lambda _: events
        def check(item):
            if item.block == 150:
                raise fr.RecoveryError('late destination query failed')
            return checked(120, False)
        direction.check = check
        with patch('federator_recovery.scan_cross', return_value=events):
            with self.assertRaises(fr.IncompleteAudit) as err:
                direction.audit(100, 200, 2)
        self.assertEqual(err.exception.known[0].event.block, 120)
        with self.assertRaises(fr.RecoveryError):
            fr.validate_replay(140, None, err.exception.known,
                               'ALL BEFORE 56:140 PROCESSED', 56)

    def direction(self, mismatch=False, bad_receipt=False):
        source = {'host': 'https://source.invalid', 'bridge': '0x' + '55' * 20,
                  'federation': '0x' + '77' * 20, 'fromBlock': 1}
        dest = {'host': 'https://destination.invalid', 'bridge': '0x' + '66' * 20,
                'federation': '0x' + '77' * 20, 'fromBlock': 1}
        table = {'56': {'default': 100, 'minConfirmation': 10,
                         'ETH': [{'amount': 0, 'confirmations': 10}]}}
        factory = lambda url: (ChainDouble(56, source['bridge'], bad_receipt=bad_receipt)
                               if 'source' in url else ChainDouble(30, dest['bridge'], mismatch=mismatch))
        return fr.Direction('BSC→Rootstock', 56, 30, source, dest, table, factory)

    def test_complete_audit_checks_receipt_and_both_destination_contracts(self):
        direction = self.direction()
        audit = direction.audit(100, 200, 2)
        self.assertEqual(audit.latest_completed, 120)
        self.assertEqual(audit.safe_frontier, 200)
        self.assertEqual(audit.events[0].votes, 3)
        self.assertEqual(audit.events[0].federation_id, '0x' + '66' * 32)

    def test_receipt_reorg_prevents_audit_frontier(self):
        with self.assertRaises(fr.RecoveryError):
            self.direction(bad_receipt=True).audit(100, 200, 2)

    def test_disagreeing_bridge_and_federation_states_do_not_claim_completion(self):
        with self.assertRaises(fr.RecoveryError):
            self.direction(mismatch=True).check(event())


class ProtocolTests(unittest.TestCase):
    def test_fresh_scan_does_not_refresh_stale_peer_or_role_evidence(self):
        text = ('2026-10-07T20:00:00Z This node is a leader -- handling iteration. '
                '(2 other peers, node NODE, leader NODE)\n'
                '2026-10-07T22:00:00Z [INFO] SIDE-FEDERATOR - Progress saved, newFromBlock: 150\n')
        role = fr.fresh_role(text, '2026-10-07T19:00:00Z')
        self.assertFalse(fr.role_ready(role, 2, 2,
                                      datetime(2026, 10, 7, 22, 0, tzinfo=timezone.utc)))

    def test_stale_or_future_peer_message_does_not_prove_current_readiness(self):
        role = {'peers': 2, 'role': 'follower', 'activity': '2026-10-07T21:00:00Z',
                'peer_time': '2026-10-07T21:00:00Z', 'role_time': '2026-10-07T21:00:00Z'}
        self.assertFalse(fr.role_ready(role, 2, 2,
                                      datetime(2026, 10, 7, 22, 0, tzinfo=timezone.utc)))
        role['activity'] = '2026-10-07T22:00:00Z'
        role['peer_time'] = role['role_time'] = role['activity']
        self.assertTrue(fr.role_ready(role, 2, 2,
                                     datetime(2026, 10, 7, 22, 1, tzinfo=timezone.utc)))
        self.assertFalse(fr.role_ready(role, 2, 2,
                                      datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc)))

    def test_timezone_free_timestamp_is_not_interpreted_using_host_timezone(self):
        self.assertIsNone(fr.parse_time('2026-10-07T21:00:00'))

    def test_log_redaction_hides_both_prefixed_and_plain_key_shapes(self):
        secret = 'a' * 64
        redacted = fr.redact_logs('private=' + secret + ' private=0x' + secret)
        self.assertNotIn(secret, redacted)

    def test_fresh_role_ignores_old_pre_reboot_leader_messages(self):
        text = ('2026-10-07T08:00:00Z Not leader, just chilling. (2 other peers, node OLD, leader LEADER)\n'
                '2026-10-07T21:18:55Z Joined federators network | Node id: NEW | Port: 30303\n'
                '2026-10-07T21:18:56Z A new node is available: PEER | 1 total peer(s) | Leader: PEER\n')
        role = fr.fresh_role(text, '2026-10-07T21:13:00Z')
        self.assertEqual(role['peers'], 1)
        self.assertEqual(role['node'], 'NEW')
        self.assertNotEqual(role['role'], 'follower')

    def test_failed_rpc_message_does_not_expose_credential_bearing_url(self):
        url = 'https://user:SUPERSECRET@example.invalid/api?apikey=SUPERSECRET'
        with patch('federator_recovery.urllib.request.urlopen',
                   side_effect=fr.urllib.error.URLError(url)):
            with self.assertRaises(fr.RecoveryError) as err:
                fr.RPC(url).call('eth_blockNumber', [])
        self.assertNotIn('SUPERSECRET', str(err.exception))

    def test_direction_refuses_wrong_chain_before_audit(self):
        class WrongChain:
            def __init__(self, url):
                pass
            def call(self, method, params):
                return '0x1'
        config = {'host': 'https://example.invalid', 'bridge': '0x' + '11' * 20,
                  'federation': '0x' + '22' * 20, 'fromBlock': 1}
        with self.assertRaises(fr.RecoveryError):
            fr.Direction('BSC→RSK', 56, 30, config, config, {}, rpc_factory=WrongChain)

    def test_dynamic_abi_offsets_and_lengths_match_hand_encoded_vector(self):
        want = ('0x01020304' + f'{7:064x}' + f'{96:064x}' + f'{160:064x}'
                + f'{3:064x}' + '455448' + '00' * 29
                + f'{2:064x}' + '1122' + '00' * 30)
        self.assertEqual(fr.abi_call('0x01020304', ['uint256', 'string', 'bytes'],
                                     [7, 'ETH', b'\x11\x22']), want)

    def test_decode_cross_preserves_dynamic_userdata_and_log_index(self):
        words = [1000, 160, 224, 18, 1]
        raw = ''.join(f'{x:064x}' for x in words)
        raw += f'{3:064x}' + '455448' + '00' * 29
        raw += f'{2:064x}' + 'aabb' + '00' * 30
        log = {'address': '0x' + '55' * 20,
               'topics': [fr.CROSS_TOPIC, '0x' + '00' * 12 + '11' * 20,
                          '0x' + '00' * 12 + '22' * 20],
               'data': '0x' + raw, 'blockNumber': '0x78',
               'blockHash': '0x' + '33' * 32, 'transactionHash': '0x' + '44' * 32,
               'logIndex': '0x1', 'removed': False}
        self.assertEqual(fr.decode_cross(log, log['address']), event())
        log['data'] = '0x' + f'{1000:064x}' + f'{1:064x}' + raw[128:]
        with self.assertRaises(fr.RecoveryError):
            fr.decode_cross(log, log['address'])

    def test_static_config_read_does_not_execute_private_key_require(self):
        text = '''module.exports = {
          mainchain: require('./rskmainnet.json'), sidechain: require('./bmainnet.json'),
          privateKey: require('/must-not-be-read'), minimumPeerAmount: 2, runEvery: 2,
          confirmationTable: {"56": {"default": 100, "minConfirmation": 10,
              "ETH": [{"amount": 0, "confirmations": 10},
                      {"amount": 1000000000000000000, "confirmations": 20},],},},
        };'''
        config = fr.parse_public_config(text)
        self.assertEqual(config['side_json'], 'bmainnet.json')
        self.assertEqual(fr.confirmations_for(config['table'], 56, 'ETH', 10**18), 20)
        self.assertEqual(fr.confirmations_for(config['table'], 56, 'UNKNOWN', 0), 100)
        with self.assertRaises(fr.RecoveryError):
            fr.parse_public_config(text.replace('100,', 'Math.random(),'))

    def test_later_completed_event_cannot_hide_older_pending_event(self):
        audit = fr.Audit(100, 200, 220, [checked(110, False), checked(150)])
        self.assertEqual(audit.latest_completed, 150)
        self.assertEqual(audit.first_blocked, 110)
        self.assertEqual(audit.safe_frontier, 109)
        self.assertEqual(fr.suggest_replay(audit, []), 110)
        with self.assertRaises(fr.RecoveryError):
            fr.validate_replay(150, None, audit.events, 'ALL BEFORE 56:150 PROCESSED', 56)

    def test_same_block_success_and_pending_replays_whole_block(self):
        audit = fr.Audit(100, 200, 220, [checked(150, True, index=1),
                                      checked(150, False, index=2)])
        self.assertEqual(audit.safe_frontier, 149)
        self.assertEqual(fr.validate_replay(150, None, audit.events,
                                           'ALL BEFORE 56:150 PROCESSED', 56), 149)

    def test_missing_or_forward_cursor_requires_specific_completeness_statement(self):
        for old in [None, 5]:
            with self.assertRaises(fr.RecoveryError):
                fr.validate_replay(100, old, [], 'yes', 56)
            self.assertEqual(fr.validate_replay(100, old, [],
                                               'ALL BEFORE 56:100 PROCESSED', 56), 99)
        self.assertEqual(fr.validate_replay(100, 120, [], '', 56), 99)

    def test_unconfirmed_event_blocks_forward_frontier(self):
        audit = fr.Audit(100, 200, 220, [checked(130, True), checked(150, True, False)])
        self.assertEqual(audit.latest_completed, 130)
        self.assertEqual(audit.safe_frontier, 149)

    def test_partial_rpc_scan_does_not_return_frontier(self):
        class BadRpc:
            def call(self, method, params):
                if int(params[0]['fromBlock'], 16) == 100:
                    return []
                raise fr.RecoveryError('RPC unavailable')
        with self.assertRaises(fr.RecoveryError):
            fr.scan_cross(BadRpc(), '0x' + '55' * 20, 100, 250, 10)

    def test_scan_page_budget_rejects_large_historical_replay(self):
        with self.assertRaises(fr.RecoveryError):
            fr.scan_cross(None, '0x' + '55' * 20, 1, 1000000, 10)


class FakeRunner:
    def __init__(self, cfg):
        self.cfg = cfg
        self.running = False
        self.stop_fails = False
        self.changed_mount = False
        self.started = False
        self.on_stop = None
        self.logs_text = ''
        self.logs_error = None
        self.commands = []
        self.identity = '1' * 64
        self.on_start = None

    def run(self, args, timeout=15):
        self.commands.append((list(args), timeout))
        if args[:2] == ['docker', 'inspect']:
            source = str(self.cfg) if not self.changed_mount else str(self.cfg.parent / 'wrong')
            return json.dumps({'id': self.identity, 'status': 'running' if self.running else 'exited',
                              'running': self.running, 'exit': 0, 'oom': False,
                              'started': '2026-10-07T21:00:00Z',
                              'finished': '2026-10-07T08:00:00Z', 'restart': '',
                              'image': 'sovryn/fed-tokenbridge:10.28', 'image_id': 'sha256:test',
                              'user': 'node', 'mounts': [
                                  {'Source': source, 'Destination': '/app/federator/config'},
                                  {'Source': str(self.cfg / 'db'), 'Destination': '/app/federator/db'}]})
        if args[:2] == ['docker', 'logs']:
            if self.logs_error:
                raise self.logs_error
            return self.logs_text
        if args[:2] == ['docker', 'stop']:
            if self.stop_fails:
                raise fr.RecoveryError('stop failed')
            if self.on_stop:
                self.on_stop()
            self.running = False
            return 'bridge-sc_federation_1'
        if args[:2] == ['docker', 'start']:
            self.started = True
            self.running = True
            if self.on_start:
                self.on_start()
            return 'bridge-sc_federation_1'
        raise AssertionError(args)


class RecoveryTests(unittest.TestCase):
    def test_stop_prompt_mount_change_is_rejected_before_docker_stop(self):
        self.runner.running = True
        def approve(_):
            self.runner.changed_mount = True
            return True
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {self.cursor: (100, 90)}, approve)
        self.assertTrue(self.runner.running)
        self.assertEqual(self.cursor.read_text(), '100\n')

    def test_key_removed_during_stop_prompt_does_not_strand_running_node(self):
        self.runner.running = True
        def approve(_):
            if (self.cfg / 'federator.key').exists():
                (self.cfg / 'federator.key').unlink()
            return True
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {self.cursor: (100, 90)}, approve)
        self.assertTrue(self.runner.running)

    def test_atomic_write_refuses_running_node(self):
        self.runner.running = True
        with self.assertRaises(fr.RecoveryError):
            fr.atomic_checkpoint(self.node, self.cursor, 100, 90)
        self.assertEqual(self.cursor.read_text(), '100\n')

    def test_parent_swap_during_install_never_writes_outside_reviewed_directory(self):
        outside = self.repo / 'outside-db'
        outside.mkdir()
        (outside / 'lastBlock.txt').write_text('777\n')
        directory = self.cursor.parent
        real_open = os.open
        swapped = []
        def open_file(path, *args, **kwargs):
            if '.checkpoint.' in str(path) and not swapped:
                directory.rename(directory.parent / 'side-fed-original')
                directory.symlink_to(outside, target_is_directory=True)
                swapped.append(True)
            return real_open(path, *args, **kwargs)
        with patch('federator_recovery.os.open', side_effect=open_file):
            try:
                fr.atomic_checkpoint(self.node, self.cursor, 100, 90)
            except fr.RecoveryError:
                pass
        self.assertEqual((outside / 'lastBlock.txt').read_text(), '777\n')
        self.assertTrue(swapped)
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'Bridge-SC'
        self.cfg = self.repo / 'federator-env' / 'mainnet-BSC-RSK'
        (self.cfg / 'db' / 'side-fed').mkdir(parents=True)
        self.cursor = self.cfg / 'db' / 'side-fed' / 'lastBlock.txt'
        self.cursor.write_text('100\n')
        (self.cfg / 'db' / 'lastBlock.txt').write_text('200\n')
        (self.cfg / 'db' / 'side-fed' / 'failingTxIds.txt').write_text('keep\n')
        self.secret = '9' * 64
        fr.install_key(self.cfg, self.secret, os.getuid())
        self.runner = FakeRunner(self.cfg)
        self.node = fr.Node(self.repo, 'bsc-rsk', 'bridge-sc_federation_1', self.runner,
                            expected_uid=os.getuid())

    def tearDown(self):
        self.tmp.cleanup()

    def test_stop_failure_preserves_cursor_and_prevents_start(self):
        self.runner.running = True
        self.runner.stop_fails = True
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: True)
        self.assertEqual(self.cursor.read_text(), '100\n')
        self.assertFalse(self.runner.started)

    def test_wrong_operator_uid_cannot_write_unreadable_checkpoint(self):
        with patch('federator_recovery.os.getuid', return_value=os.getuid() + 1):
            with self.assertRaises(fr.RecoveryError):
                fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: True)
        self.assertEqual(self.cursor.read_text(), '100\n')
        self.assertFalse(self.runner.started)

    def test_invalid_checkpoint_path_is_rejected_before_stopping(self):
        self.runner.running = True
        other = self.cfg / 'db' / 'numeric-not-a-cursor'
        other.write_text('100\n')
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {other: (100, 90)}, lambda _: True)
        self.assertTrue(self.runner.running)
        self.assertEqual(other.read_text(), '100\n')

    def test_docker_command_uses_local_socket_even_if_context_is_remote(self):
        result = type('Result', (), {'returncode': 0, 'stdout': '{}', 'stderr': ''})()
        with patch.dict(os.environ, {'DOCKER_HOST': 'ssh://remote.invalid'}):
            with patch('federator_recovery.subprocess.run', return_value=result) as execute:
                fr.Runner().run(['docker', 'inspect', 'bridge-sc_federation_1'])
        self.assertEqual(execute.call_args.args[0][:3],
                         ['docker', '--host', 'unix:///var/run/docker.sock'])

    def test_running_node_is_stopped_before_atomic_cursor_write_and_other_direction_untouched(self):
        self.runner.running = True
        self.runner.on_stop = lambda: self.assertEqual(self.cursor.read_text(), '100\n')
        backup = fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: True)
        self.assertEqual(self.cursor.read_text(), '90\n')
        self.assertEqual((self.cfg / 'db' / 'lastBlock.txt').read_text(), '200\n')
        self.assertEqual((self.cfg / 'db' / 'side-fed' / 'failingTxIds.txt').read_text(), 'keep\n')
        self.assertEqual((backup / 'db-before' / 'side-fed' / 'lastBlock.txt').read_text(), '100\n')
        self.assertTrue(self.runner.started)

    def test_declined_stop_preserves_state(self):
        self.runner.running = True
        fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: False)
        self.assertEqual(self.cursor.read_text(), '100\n')
        self.assertTrue(self.runner.running)
        self.assertFalse(self.runner.started)

    def test_mount_change_aborts_before_mutation(self):
        self.node.inspect()
        self.runner.changed_mount = True
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: True)
        self.assertEqual(self.cursor.read_text(), '100\n')

    def test_cursor_changed_during_stop_aborts_write(self):
        self.runner.running = True
        self.runner.on_stop = lambda: self.cursor.write_text('101\n')
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: True)
        self.assertEqual(self.cursor.read_text(), '101\n')
        self.assertFalse(self.runner.started)

    def test_cursor_symlink_is_rejected(self):
        outside = self.repo / 'outside.txt'
        outside.write_text('777\n')
        self.cursor.unlink()
        self.cursor.symlink_to(outside)
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {self.cursor: (100, 90)}, lambda _: True)
        self.assertEqual(outside.read_text(), '777\n')

    def test_second_cursor_write_failure_rolls_back_first(self):
        reverse = self.cfg / 'db' / 'lastBlock.txt'
        original = fr.atomic_checkpoint
        def write(node, path, old, new):
            if path == reverse and new == 180:
                raise fr.RecoveryError('second installation failed')
            return original(node, path, old, new)
        with patch('federator_recovery.atomic_checkpoint', side_effect=write):
            with self.assertRaises(fr.RecoveryError):
                fr.perform_recovery(self.node, {self.cursor: (100, 90), reverse: (200, 180)},
                                    lambda _: True)
        self.assertEqual(self.cursor.read_text(), '100\n')
        self.assertEqual(reverse.read_text(), '200\n')
        self.assertFalse(self.runner.started)

    def test_second_cursor_directory_sync_failure_rolls_back_both(self):
        reverse = self.cfg / 'db' / 'lastBlock.txt'
        original = os.fsync
        calls = []
        def fail_fourth(fd):
            calls.append(fd)
            if len(calls) == 4:
                raise OSError('directory sync failed after replacement')
            return original(fd)
        with patch('federator_recovery.os.fsync', side_effect=fail_fourth):
            with self.assertRaises(fr.RecoveryError):
                fr.perform_recovery(self.node, {self.cursor: (100, 90), reverse: (200, 180)},
                                    lambda _: True)
        self.assertEqual(self.cursor.read_text(), '100\n')
        self.assertEqual(reverse.read_text(), '200\n')
        self.assertFalse(self.runner.started)

    def test_new_cursor_directory_sync_failure_removes_installed_cursor(self):
        self.cursor.unlink()
        original = os.fsync
        calls = []
        def fail_second(fd):
            calls.append(fd)
            if len(calls) == 2:
                raise OSError('directory sync failed after installation')
            return original(fd)
        with patch('federator_recovery.os.fsync', side_effect=fail_second):
            with self.assertRaises(fr.RecoveryError):
                fr.perform_recovery(self.node, {self.cursor: (None, 90)}, lambda _: True)
        self.assertFalse(self.cursor.exists())
        self.assertFalse(self.runner.started)

    def test_secret_symlink_cannot_overwrite_other_file(self):
        key = self.cfg / 'federator.key'
        key.unlink()
        outside = self.repo / 'unrelated-secret'
        outside.write_text('preserve\n')
        key.symlink_to(outside)
        with self.assertRaises(fr.RecoveryError):
            fr.install_key(self.cfg, self.secret, os.getuid())
        self.assertEqual(outside.read_text(), 'preserve\n')

    def test_blank_confirmation_defaults_to_no(self):
        with patch('builtins.input', return_value=''):
            self.assertFalse(fr.ask_yes('Stop container?'))

    def test_default_cli_is_read_only_with_real_config_and_mocked_external_boundaries(self):
        profile = fr.PROFILES['bsc-rsk']
        cfg = '''module.exports={mainchain: require('./rskmainnet.json'),
          sidechain: require('./bmainnet.json'),minimumPeerAmount:2,runEvery:2,
          privateKey: require('/never-read-this'),confirmationTable:{
          "30":{"default":4,"minConfirmation":2},
          "56":{"default":100,"minConfirmation":10}}};'''
        (self.cfg / 'config.js').write_text(cfg)
        for name, chain, bridge in [('rskmainnet.json', 30, profile['rootstock_bridge']),
                                    ('bmainnet.json', 56, profile['external_bridge'])]:
            (self.cfg / name).write_text(json.dumps({'host': 'https://rpc' + str(chain) + '.invalid',
                        'bridge': bridge, 'federation': '0x' + '77' * 20, 'fromBlock': 1}))
        factory = lambda url: ChainDouble(30, profile['rootstock_bridge'], False) if 'rpc30' in url else ChainDouble(56, profile['external_bridge'], False)
        captured = io.StringIO()
        with patch('federator_recovery.Runner', return_value=self.runner), patch('federator_recovery.RPC', side_effect=factory):
            with contextlib.redirect_stdout(captured):
                result = fr.main(['--bridge', 'bsc-rsk', '--repo', str(self.repo), '--no-scan',
                                  '--tx', '0x' + '44' * 32])
        self.assertEqual(result, 0)
        self.assertFalse(self.runner.started)
        self.assertEqual(self.cursor.read_text(), '100\n')
        self.assertNotIn(self.secret, captured.getvalue())
        self.assertIn('pending', captured.getvalue())

    def test_watch_does_not_count_same_old_poll_twice(self):
        self.runner.running = True
        role = {'peers': 2, 'role': 'follower', 'activity': '2026-10-07T21:00:00Z'}
        with patch('federator_recovery.fresh_role', return_value=role), patch('federator_recovery.role_ready', return_value=True):
            with patch('federator_recovery.time.monotonic', side_effect=[0, 0.1, 1.1]), patch('federator_recovery.time.sleep'):
                with contextlib.redirect_stdout(io.StringIO()):
                    ready = fr.watch(self.node, {'minimumPeerAmount': 2, 'runEvery': 2}, [], {}, 1)
        self.assertFalse(ready)

    def test_key_is_private_and_existing_key_cannot_be_overwritten(self):
        key = self.cfg / 'federator.key'
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        with self.assertRaises(fr.RecoveryError):
            fr.install_key(self.cfg, 'a' * 64, os.getuid())
        self.assertEqual(key.read_text().strip(), self.secret)

    def test_bad_secret_never_appears_in_error_or_stdout(self):
        (self.cfg / 'federator.key').unlink()
        bad = 'SENSITIVE-NOT-A-KEY'
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), self.assertRaises(fr.RecoveryError) as err:
            fr.install_key(self.cfg, bad, os.getuid())
        self.assertNotIn(bad, str(err.exception) + captured.getvalue())
        self.assertFalse((self.cfg / 'federator.key').exists())

    def test_missing_key_does_not_start_container(self):
        (self.cfg / 'federator.key').unlink()
        with self.assertRaises(fr.RecoveryError):
            fr.perform_recovery(self.node, {}, lambda _: True)
        self.assertFalse(self.runner.started)

    def test_subprocess_failure_does_not_disclose_stdout_secret(self):
        result = type('Result', (), {'returncode': 1, 'stdout': self.secret,
                                     'stderr': self.secret})()
        with patch('federator_recovery.subprocess.run', return_value=result):
            with self.assertRaises(fr.RecoveryError) as err:
                fr.Runner().run(['aws', 'secretsmanager', 'get-secret-value'])
        self.assertNotIn(self.secret, str(err.exception))


class LocalRecoveryTests(unittest.TestCase):
    setUp = RecoveryTests.setUp
    tearDown = RecoveryTests.tearDown
    def public_config(self):
        profile = fr.PROFILES['bsc-rsk']
        (self.cfg / 'config.js').write_text("""module.exports={
          mainchain: require('./rskmainnet.json'), sidechain: require('./bmainnet.json'),
          minimumPeerAmount:2,runEvery:2,privateKey:require('/never-read'),
          confirmationTable:{"30":{"default":4,"minConfirmation":2},
          "56":{"default":100,"minConfirmation":10}}};""")
        for name, bridge, fallback in [('rskmainnet.json', profile['rootstock_bridge'], 11),
                                        ('bmainnet.json', profile['external_bridge'], 22)]:
            (self.cfg / name).write_text(json.dumps({'host': 'https://credential.invalid/secret',
                'bridge': bridge, 'federation': '0x' + '77' * 20, 'fromBlock': fallback}))

    def cli(self, flags):
        self.public_config()
        with patch('federator_recovery.Runner', return_value=self.runner), \
             patch('federator_recovery.RPC', side_effect=AssertionError('RPC must remain unused')), \
             patch('federator_recovery.sys.stdin.isatty', return_value=True), \
             patch('federator_recovery.os.getuid', return_value=1000), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            # The fixture has the host's UID; the CLI production default remains 1000.
            self.node.expected_uid = 1000
            with patch('federator_recovery.Node', return_value=self.node):
                result = fr.main(['--bridge', 'bsc-rsk', '--repo', str(self.repo)] + flags)
        return result, out.getvalue()

    def test_local_diagnosis_skips_rpc_and_preserves_all_files(self):
        before = {str(p): p.read_bytes() for p in (self.cfg / 'db').rglob('*') if p.is_file()}
        result, out = self.cli(['--local-only'])
        self.assertEqual(result, 0)
        self.assertIn('fallback=22', out)
        self.assertIn('saved cursor=100', out)
        self.assertEqual(before, {str(p): p.read_bytes() for p in (self.cfg / 'db').rglob('*') if p.is_file()})
        self.assertFalse(self.runner.started)

    def test_local_diagnosis_handles_absent_follower_directory(self):
        self.cursor.unlink()
        (self.cursor.parent / 'failingTxIds.txt').unlink()
        self.cursor.parent.rmdir()
        result, out = self.cli(['--local-only'])
        self.assertEqual(result, 0)
        self.assertIn('saved cursor=None; fallback=22', out)
        self.assertIn('historical', out.lower())
        self.assertFalse(self.cursor.parent.exists())

    def test_restart_only_preserves_present_and_absent_checkpoints(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.runner.running = False
                self.runner.started = False
                if missing:
                    self.cursor.unlink()
                before = {str(p): p.read_bytes() for p in (self.cfg / 'db').rglob('*') if p.is_file()}
                with patch('federator_recovery.ask_yes', return_value=True), \
                     patch('federator_recovery.os.getuid', return_value=os.stat(self.cfg / 'db').st_uid):
                    fr.restart_only(self.node, lambda _: True)
                self.assertTrue(self.runner.started)
                self.assertEqual(before, {str(p): p.read_bytes() for p in (self.cfg / 'db').rglob('*') if p.is_file()})
                self.assertEqual(self.cursor.exists(), not missing)

    def test_restart_only_running_node_has_no_prompts_or_writes(self):
        self.runner.running = True
        (self.cfg / 'federator.key').unlink()
        fr.restart_only(self.node, lambda _: self.fail('running node must not prompt'))
        self.assertTrue(self.runner.running)
        self.assertFalse(self.runner.started)
        self.assertFalse((self.cfg / 'federator.key').exists())

    def test_restart_only_restores_original_missing_key_before_start(self):
        (self.cfg / 'federator.key').unlink()
        def restore(node, confirm):
            self.assertFalse(self.runner.started)
            fr.install_key(node.cfg, self.secret, os.getuid())
            return True
        with patch('federator_recovery.restore_original_key', side_effect=restore):
            fr.restart_only(self.node, lambda _: True)
        self.assertTrue(self.runner.started)
        self.assertEqual(self.cursor.read_bytes(), b'100\n')

    def test_declined_or_failed_restore_never_starts(self):
        (self.cfg / 'federator.key').unlink()
        for behavior in (False, fr.RecoveryError('AWS unavailable')):
            with self.subTest(behavior=type(behavior).__name__):
                kwargs = {'side_effect': behavior} if isinstance(behavior, Exception) else {'return_value': behavior}
                with patch('federator_recovery.restore_original_key', **kwargs):
                    with self.assertRaises(fr.RecoveryError):
                        fr.restart_only(self.node, lambda _: True)
                self.assertFalse(self.runner.started)
                self.assertEqual(self.cursor.read_bytes(), b'100\n')
        with patch('federator_recovery.restore_original_key', side_effect=AssertionError('must not fetch')):
            with self.assertRaises(fr.RecoveryError):
                fr.restart_only(self.node, lambda _: False)
        self.assertFalse(self.runner.started)

    def test_restart_only_rechecks_identity_and_key_after_prompt(self):
        def approve(_):
            self.runner.changed_mount = True
            return True
        with self.assertRaises(fr.RecoveryError):
            fr.restart_only(self.node, approve)
        self.assertFalse(self.runner.started)
        self.runner.changed_mount = False
        def delete_key(_):
            (self.cfg / 'federator.key').unlink()
            return True
        with self.assertRaises(fr.RecoveryError):
            fr.restart_only(self.node, delete_key)
        self.assertFalse(self.runner.started)

    def test_restart_only_refuses_operator_uid_mismatch(self):
        with patch('federator_recovery.os.getuid', return_value=os.getuid() + 1):
            with self.assertRaises(fr.RecoveryError):
                fr.restart_only(self.node, lambda _: True)
        self.assertFalse(self.runner.started)

    def test_restart_only_cli_start_works_without_rpc_or_checkpoint_seed(self):
        self.cursor.unlink()
        # CLI UID check is patched; use matching fake node ownership.
        self.node.expected_uid = 1000
        with patch('federator_recovery.ask_yes', return_value=True), \
             patch('federator_recovery.Node.key_ready'):
            result, out = self.cli(['--recover', '--restart-only', '--watch-seconds', '0'])
        self.assertTrue(self.runner.started)
        self.assertFalse(self.cursor.exists())
        self.assertEqual(result, 3)  # Start alone does not prove participation.
        self.assertNotIn('transfers processed', out)

    def test_conflicting_modes_are_rejected_before_inspection(self):
        cases = [['--restart-only'], ['--recover', '--local-only'],
                 ['--local-only', '--tx', '0x' + '44' * 32],
                 ['--recover', '--restart-only', '--tx', '0x' + '44' * 32],
                 ['--recover', '--restart-only', '--completed-tx', '0x' + '44' * 32],
                 ['--recover', '--restart-only', '--rootstock-tx', '0x' + '44' * 32],
                 ['--recover', '--restart-only', '--rootstock-completed-tx', '0x' + '44' * 32],
                 ['--recover', '--restart-only', '--lookback', '20'],
                 ['--recover', '--restart-only', '--max-pages', '20'],
                 ['--recover', '--restart-only', '--no-scan']]
        for flags in cases:
            with self.subTest(flags=flags), \
                 patch('federator_recovery.Runner', side_effect=AssertionError('no inspection')), \
                 patch('federator_recovery.sys.stdin.isatty', return_value=True), \
                 patch('federator_recovery.os.getuid', return_value=1000):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
                    fr.main(['--bridge', 'bsc-rsk'] + flags)
                self.assertEqual(err.exception.code, 2)


class EvidenceTests(unittest.TestCase):
    setUp = RecoveryTests.setUp
    tearDown = RecoveryTests.tearDown
    public_config = LocalRecoveryTests.public_config
    cli = LocalRecoveryTests.cli
    # Separate real fixture; test only the new capture/report contracts.
    def test_report_is_private_and_retains_redacted_auth_stack_context(self):
        self.runner.logs_text = ("2026-10-09T12:00:00Z TypeError: RSKKeyedAuth handshake failed\n"
            "    at ataraxia/auth.js:10\n"
            "2026-10-09T12:00:01Z npm ERR! PRIVATE_KEY=" + self.secret + "\n"
            "2026-10-09T12:00:02Z rpc=https://user:password@rpc.invalid/key\n"
            "2026-10-09T12:00:03Z Authorization: Bearer opaque-credential\n"
            "2026-10-09T12:00:04Z AWS_SECRET_ACCESS_KEY=aws-opaque-secret\n")
        destination = self.repo / 'private-report.json'
        result, out = self.cli(['--local-only', '--report', str(destination),
            '--logs-since', '2026-10-09T12:00:00Z', '--logs-until', '2026-10-09T12:05:00Z'])
        self.assertEqual(result, 0)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        report = json.loads(destination.read_text())
        self.assertEqual(report['container']['status'], 'exited')
        self.assertTrue(report['key']['present'])
        self.assertEqual(report['key']['mode'], '600')
        self.assertEqual(report['cursors'][1]['saved'], 100)
        self.assertEqual(report['cursors'][1]['fallback'], 22)
        self.assertEqual(report['logs']['status'], 'captured')
        self.assertEqual(report['logs']['since'], '2026-10-09T12:00:00Z')
        self.assertEqual(report['logs']['until'], '2026-10-09T12:05:00Z')
        self.assertGreaterEqual(report['duration_seconds'], 0)
        self.assertIn('version', report)
        self.assertIn('TypeError', report['logs']['text'])
        self.assertIn('ataraxia/auth.js:10', report['logs']['text'])
        self.assertIn('npm ERR!', report['logs']['text'])
        for secret in (self.secret, 'opaque-credential', 'aws-opaque-secret', 'password@rpc', '/key'):
            self.assertNotIn(secret, destination.read_text() + out)
        self.assertEqual(report['node_participation'], 'unverified')
        self.assertEqual(report['transfer_completion'], 'not_checked')
        log_args, timeout = next((args, timeout) for args, timeout in self.runner.commands if args[:2] == ['docker', 'logs'])
        self.assertIn('--since', log_args)
        self.assertIn('--until', log_args)
        self.assertEqual(timeout, 15)

    def test_log_failure_is_explicit_unavailable_in_private_report(self):
        self.runner.logs_error = fr.RecoveryError('docker timed out https://auth:secret@rpc.invalid/key')
        report_file = self.repo / 'failed-capture.json'
        result, out = self.cli(['--local-only', '--report', str(report_file)])
        report = json.loads(report_file.read_text())
        self.assertEqual(result, 0)
        self.assertEqual(report['logs']['status'], 'unavailable')
        self.assertIn('timed out', report['logs']['failure'])
        self.assertNotIn('secret@', report_file.read_text() + out)
        self.assertEqual(report['node_participation'], 'unverified')

    def test_report_refuses_existing_or_symlink_target_before_docker(self):
        target = self.repo / 'existing-report.json'
        target.write_text('preserve')
        link = self.repo / 'linked-report.json'
        link.symlink_to(target)
        for path in (target, link):
            with self.subTest(path=path), patch('federator_recovery.Runner', side_effect=AssertionError('must not inspect')):
                with self.assertRaises(fr.RecoveryError):
                    fr.main(['--bridge', 'bsc-rsk', '--local-only', '--report', str(path)])
            self.assertEqual(target.read_text(), 'preserve')

    def test_report_records_recovery_failure_without_exception_secrets(self):
        self.public_config()
        report_file = self.repo / 'aborted.json'
        self.runner.changed_mount = True
        with self.assertRaises(fr.RecoveryError):
            self.cli(['--local-only', '--report', str(report_file)])
        report = json.loads(report_file.read_text())
        self.assertEqual(report['outcome'], 'failed')
        self.assertIn('mount', report['failure'])
        self.assertGreaterEqual(report['duration_seconds'], 0)
        self.assertFalse(self.runner.started)

    def test_log_bounds_require_offsets_order_and_finite_window(self):
        bounds = [[], ['--logs-since', '2026-10-09T12:00:00Z'],
            ['--logs-since', '2026-10-09T12:00:00', '--logs-until', '2026-10-09T12:05:00Z'],
            ['--logs-since', '2026-10-09T12:05:00Z', '--logs-until', '2026-10-09T12:00:00Z'],
            ['--logs-since', '2026-10-07T12:00:00Z', '--logs-until', '2026-10-09T12:00:00Z']]
        for flags in bounds[1:]:
            with self.subTest(flags=flags), patch('federator_recovery.Runner', side_effect=AssertionError('must not inspect')):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
                    fr.main(['--bridge', 'bsc-rsk', '--local-only'] + flags)
                self.assertEqual(err.exception.code, 2)
        result, _ = self.cli(['--local-only', '--logs-since', '2026-10-09T14:00:00+02:00',
                              '--logs-until', '2026-10-09T14:05:00+02:00'])
        self.assertEqual(result, 0)
        args = next(args for args, _ in self.runner.commands if args[:2] == ['docker', 'logs'])
        self.assertEqual(args[args.index('--since') + 1], '2026-10-09T12:00:00Z')
        self.assertEqual(args[args.index('--until') + 1], '2026-10-09T12:05:00Z')

    def test_log_redactor_hides_labeled_nonhex_credentials_and_other_url_schemes(self):
        raw = ('{"privateKey":"opaque-a", "password": "opaque-b", "token":"opaque-c"}\n'
               'AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP\n'
               'AWS_SECRET_ACCESS_KEY=opaque-d\n'
               'Authorization: Bearer opaque-e\n'
               'peer=wss://user:opaque-f@peer.invalid/a\n'
               'TypeError: RSKKeyedAuth\n    at ataraxia/auth.js:10')
        cleaned = fr.redact_logs(raw)
        for sensitive in ['opaque-' + ch for ch in 'abcdef'] + ['AKIAABCDEFGHIJKLMNOP']:
            self.assertNotIn(sensitive, cleaned)
        self.assertIn('TypeError: RSKKeyedAuth', cleaned)
        self.assertIn('ataraxia/auth.js:10', cleaned)

    def test_watch_requires_new_peer_role_polls_not_two_scan_lines(self):
        self.runner.running = True
        started = datetime.now(timezone.utc).isoformat()
        role_line = f'{started} Not leader -- skipping iteration. (2 other peers, node N, leader L)\n'
        calls = []
        def logs(*args, **kwargs):
            calls.append(True)
            stamp = datetime.now(timezone.utc).isoformat()
            return role_line + f'{stamp} MAIN-FEDERATOR - Progress saved, newFromBlock: {100 + len(calls)}'
        with patch.object(self.node, 'logs', side_effect=logs), \
             patch('federator_recovery.time.monotonic', side_effect=[0, 0.1, 1.1]), \
             patch('federator_recovery.time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(fr.watch(self.node, {'minimumPeerAmount': 2, 'runEvery': 2}, [], {}, 1))

    def test_local_watch_accepts_two_fresh_polls_but_does_not_claim_settlement(self):
        self.runner.running = True
        stamps = iter(['2026-10-09T12:00:00Z', '2026-10-09T12:00:01Z'])
        def logs(*args, **kwargs):
            return next(stamps) + ' Not leader -- skipping iteration. (2 other peers, node N, leader L)'
        class Clock:
            fromisoformat = staticmethod(datetime.fromisoformat)

            @classmethod
            def now(cls, tz):
                return datetime(2026, 10, 9, 12, 0, 2, tzinfo=timezone.utc)
        evidence = {}
        with patch.object(self.node, 'logs', side_effect=logs), \
             patch('federator_recovery.datetime', Clock), \
             patch('federator_recovery.time.monotonic', side_effect=[0, 0.1]), \
             patch('federator_recovery.time.sleep'), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(fr.watch(self.node, {'minimumPeerAmount': 2, 'runEvery': 2}, [], {}, 1, evidence))
        self.assertEqual(evidence['node_participation'], 'verified')
        self.assertEqual(evidence['transfer_completion'], 'not_checked')
        self.assertNotIn('transfers processed', out.getvalue())

    def test_local_watch_rejects_stale_failed_logs_and_exited_node(self):
        self.runner.running = True
        for error in (None, fr.RecoveryError('docker unavailable')):
            self.runner.logs_error = error
            self.runner.logs_text = '2020-01-01T00:00:00Z Not leader (2 other peers, node N, leader L)'
            with patch('federator_recovery.time.monotonic', side_effect=[0, 1]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(fr.watch(self.node, {'minimumPeerAmount': 2, 'runEvery': 2}, [], {}, 0))
        self.runner.running = False
        with self.assertRaises(fr.RecoveryError):
            fr.watch(self.node, {'minimumPeerAmount': 2, 'runEvery': 2}, [], {}, 0)

    def test_restart_only_detects_container_replacement_during_start_prompt(self):
        def approve(_):
            self.runner.identity = '2' * 64
            return True
        with self.assertRaises(fr.RecoveryError):
            fr.restart_only(self.node, approve)
        self.assertFalse(self.runner.started)

    def test_restart_only_reports_immediate_crash(self):
        self.runner.on_start = lambda: setattr(self.runner, 'running', False)
        with self.assertRaises(fr.RecoveryError):
            fr.restart_only(self.node, lambda _: True)
        self.assertTrue(self.runner.started)
        self.assertFalse(self.runner.running)
        self.assertEqual(self.cursor.read_bytes(), b'100\n')


class AdditionalGuardTests(unittest.TestCase):
    setUp = RecoveryTests.setUp
    tearDown = RecoveryTests.tearDown
    public_config = LocalRecoveryTests.public_config
    cli = LocalRecoveryTests.cli

    def test_report_parent_symlink_is_refused_before_docker(self):
        directory = self.repo / 'real-report-directory'
        directory.mkdir()
        alias = self.repo / 'alias-report-directory'
        alias.symlink_to(directory, target_is_directory=True)
        with patch('federator_recovery.Runner', side_effect=AssertionError('must not inspect')):
            with self.assertRaises(fr.RecoveryError):
                fr.main(['--bridge', 'bsc-rsk', '--local-only', '--report', str(alias / 'report.json')])
        self.assertFalse((directory / 'report.json').exists())

    def test_restart_only_refuses_config_or_db_directory_replacement(self):
        for directory in (self.cfg / 'db', self.cfg):
            with self.subTest(directory=directory):
                self.node = fr.Node(self.repo, 'bsc-rsk', 'bridge-sc_federation_1', self.runner, expected_uid=os.getuid())
                self.node.inspect()
                original = directory.with_name(directory.name + '-original')
                def approve(_):
                    directory.rename(original)
                    directory.mkdir()
                    if directory == self.cfg:
                        (directory / 'db').mkdir()
                        fr.install_key(directory, self.secret, os.getuid())
                    return True
                try:
                    with self.assertRaises(fr.RecoveryError):
                        fr.restart_only(self.node, approve)
                    self.assertFalse(self.runner.started)
                finally:
                    import shutil
                    shutil.rmtree(directory)
                    original.rename(directory)

    def test_restart_only_continues_when_logs_unavailable_and_reports_final_key_state(self):
        self.runner.logs_error = fr.RecoveryError('docker logs unavailable')
        destination = self.repo / 'start.json'
        with patch('federator_recovery.ask_yes', return_value=True), \
             patch('federator_recovery.Node.key_ready'):
            result, _ = self.cli(['--recover', '--restart-only', '--watch-seconds', '0', '--report', str(destination)])
        self.assertEqual(result, 3)
        self.assertTrue(self.runner.started)
        report = json.loads(destination.read_text())
        self.assertEqual(report['container_after']['status'], 'running')
        self.assertTrue(report['key_after']['present'])
        self.assertEqual(report['watch_logs']['status'], 'unavailable')
        self.assertIn('unavailable', report['watch_logs']['failure'])
        self.assertEqual(self.cursor.read_bytes(), b'100\n')

    def test_report_normal_chain_diagnosis_contains_both_cursors_and_transfer_result(self):
        self.public_config()
        profile = fr.PROFILES['bsc-rsk']
        destination = self.repo / 'chain-diagnosis.json'
        # Give the fixture distinct public endpoints; RPC double alone supplies chain responses.
        for filename, chain in [('rskmainnet.json', 30), ('bmainnet.json', 56)]:
            path = self.cfg / filename
            cfg = json.loads(path.read_text())
            cfg['host'] = 'https://rpc' + str(chain) + '.invalid'
            path.write_text(json.dumps(cfg))
        factory = lambda url: ChainDouble(30, profile['rootstock_bridge'], False) if 'rpc30' in url else ChainDouble(56, profile['external_bridge'], False)
        with patch('federator_recovery.Runner', return_value=self.runner), \
             patch('federator_recovery.RPC', side_effect=factory), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fr.main(['--bridge', 'bsc-rsk', '--repo', str(self.repo), '--no-scan',
                '--report', str(destination), '--tx', '0x' + '44' * 32]), 0)
        report = json.loads(destination.read_text())
        self.assertEqual([item['saved'] for item in report['cursors']], [200, 100])
        self.assertEqual(report['transfer_completion'], 'pending')


class SecretRestorationTests(unittest.TestCase):
    setUp = RecoveryTests.setUp
    tearDown = RecoveryTests.tearDown

    def restore(self, name='federator-bsc-node', value=None, aws_failure=False, confirmation=True):
        if (self.cfg / 'federator.key').exists():
            (self.cfg / 'federator.key').unlink()
        value = self.secret if value is None else value
        class Metadata:
            def open(self, request, timeout):
                if request.get_method() == 'PUT':
                    return io.BytesIO(b'private-imds-token')
                return io.BytesIO(b'{"instanceId":"i-123abc", "region":"us-east-2"}')
        original_run = self.runner.run
        def run(args, timeout=15):
            if args[:3] == ['aws', 'ec2', 'describe-instances']:
                if aws_failure:
                    raise fr.RecoveryError('aws operation failed (exit 254)')
                return name
            if args[:3] == ['aws', 'secretsmanager', 'get-secret-value']:
                return json.dumps({'SecretString': value})
            return original_run(args, timeout)
        prompts = []
        def confirm(question):
            prompts.append(question)
            return confirmation
        with patch('federator_recovery.urllib.request.build_opener', return_value=Metadata()), \
             patch.object(self.runner, 'run', side_effect=run), contextlib.redirect_stdout(io.StringIO()) as output:
            result = fr.restore_original_key(self.node, confirm)
        return result, prompts, output.getvalue()

    def test_original_key_restore_checks_name_and_installs_private_valid_key(self):
        result, prompts, out = self.restore()
        self.assertTrue(result)
        self.assertIn('federator-bsc-node', prompts[0])
        self.assertIn('mainnet-BSC-RSK', prompts[0])
        self.assertNotIn(self.secret, out)
        self.assertEqual((self.cfg / 'federator.key').read_text().strip(), self.secret)
        self.assertEqual(stat.S_IMODE((self.cfg / 'federator.key').stat().st_mode), 0o600)

    def test_wrong_bridge_empty_invalid_or_aws_denied_secret_never_installs_key(self):
        cases = [{'name': 'federator-eth-node'}, {'value': ''}, {'value': '0' * 64},
                 {'value': 'f' * 64}, {'value': 'opaque-invalid-secret'}, {'aws_failure': True}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(fr.RecoveryError) as err:
                self.restore(**kwargs)
            self.assertFalse((self.cfg / 'federator.key').exists())
            self.assertNotIn('opaque-invalid-secret', str(err.exception))
            self.assertFalse(self.runner.started)

    def test_declined_original_secret_mapping_never_installs_key(self):
        result, _, _ = self.restore(confirmation=False)
        self.assertFalse(result)
        self.assertFalse((self.cfg / 'federator.key').exists())

    def test_ec2_name_cannot_inject_prompt_or_expose_a_url(self):
        for name in ['https://user:password@name.invalid/key', 'bad\x1b[31mname']:
            with self.subTest(name=name), self.assertRaises(fr.RecoveryError):
                self.restore(name=name)
        self.assertFalse((self.cfg / 'federator.key').exists())


class CompatibilityTests(unittest.TestCase):
    def test_docker_nanosecond_timestamps_are_normalized_for_python38(self):
        # Python3.8 accepts millisecond/microsecond ISO fractions; Docker emits nanoseconds.
        class LegacyDatetime:
            @staticmethod
            def fromisoformat(value):
                import re
                fraction = re.search(r'\.(\d+)', value)
                if fraction and len(fraction.group(1)) not in (3, 6):
                    raise ValueError('unsupported timestamp fraction')
                return datetime.fromisoformat(value)
        with patch('federator_recovery.datetime', LegacyDatetime):
            stamp = fr.parse_time('2026-01-01T12:00:00.123456789Z')
        self.assertEqual(stamp, datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc))

    def test_rpc_error_code_cannot_echo_arbitrary_provider_credentials(self):
        class Response(io.BytesIO):
            pass
        payload = json.dumps({'id': 1, 'error': {'code': 'provider-private-credential', 'message': 'private'}}).encode()
        with patch('federator_recovery.urllib.request.urlopen', return_value=Response(payload)):
            with self.assertRaises(fr.RecoveryError) as err:
                fr.RPC('https://rpc.invalid').call('eth_call', [])
        self.assertNotIn('provider-private-credential', str(err.exception))


if __name__ == '__main__':
    unittest.main()
