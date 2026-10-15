#!/usr/bin/env python3
"""Inspect or interactively recover an existing Sovryn token-bridge federator.

Python standard library only. Default mode is read-only. No bridge votes,
signing, image pulls, resets, or broad Docker operations are implemented.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class RecoveryError(Exception):
    """Safe operator-facing failure; never include secret command output."""


class ChainChanged(RecoveryError):
    pass


class CheckpointInstalledError(RecoveryError):
    """Replacement occurred, but its subsequent durability/path check failed."""


class IncompleteAudit(RecoveryError):
    def __init__(self, message, known=None, unverified=None, chain_changed=False):
        super().__init__(message)
        self.known = list(known or [])
        self.unverified = list(unverified or [])
        self.chain_changed = chain_changed


VERSION = '1.0.1'
LOG_TAIL = 2000
LOG_TIMEOUT = 15
MAX_LOG_WINDOW = 24 * 60 * 60
MAX_LOG_CHARS = 1024 * 1024

CROSS_TOPIC = '0x33409cca56f705a7bbed38b7db57cf3a63317f3c1b9a747bbfb3d3ecffa84f6f'
SELECTORS = {
    'federation': '0xea217091', 'required': '0xdc8452cd', 'members': '0x9eab5253',
    'bridge_id': '0xe8340a99', 'fed_id': '0xf2f34d51',
    'bridge_done': '0xc1f0808a', 'fed_done': '0xa93585f0', 'votes': '0xa1fb4acb',
}
PROFILES = {
    'eth-rsk': {'env': 'mainnet-ETH-RSK', 'chain': 1, 'json': 'mainnet.json',
                'external_bridge': '0x33c0d33a0d4312562ad622f91d12b0ac47366ee1',
                'rootstock_bridge': '0x1ccad820b6d031b41c54f1f3da11c0d48b399581'},
    'bsc-rsk': {'env': 'mainnet-BSC-RSK', 'chain': 56, 'json': 'bmainnet.json',
                'external_bridge': '0xdfc7127593c8af1a17146893f10e08528f4c2aa7',
                'rootstock_bridge': '0x971b97c8cc82e7d27bc467c2dc3f219c6ee2e350'},
}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def integer(value, label='number'):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RecoveryError('Invalid ' + label)
    try:
        n = int(value, 16) if isinstance(value, str) and value.startswith('0x') else int(value)
    except (ValueError, TypeError):
        raise RecoveryError('Invalid ' + label) from None
    if n < 0 or n >= 2**256:
        raise RecoveryError('Invalid ' + label)
    return n


def hex_bytes(value, size=None):
    if not isinstance(value, str) or not re.fullmatch(r'0x(?:[0-9a-fA-F]{2})*', value):
        raise RecoveryError('Invalid public hex field')
    raw = bytes.fromhex(value[2:])
    if size is not None and len(raw) != size:
        raise RecoveryError('Incorrect public hex field size')
    return raw


def address(value):
    hex_bytes(value, 20)
    return value.lower()


def abi_call(selector, types, values):
    if len(types) != len(values):
        raise RecoveryError('ABI argument count mismatch')
    hex_bytes(selector, 4)
    head, tail = [], bytearray()
    for kind, value in zip(types, values):
        if kind in ('string', 'bytes'):
            raw = value.encode('utf-8') if kind == 'string' else bytes(value)
            head.append((32 * len(types) + len(tail)).to_bytes(32, 'big'))
            tail += len(raw).to_bytes(32, 'big') + raw + b'\0' * (-len(raw) % 32)
        elif kind == 'address':
            head.append(b'\0' * 12 + hex_bytes(value, 20))
        elif kind == 'bytes32':
            head.append(hex_bytes(value, 32))
        elif kind.startswith('uint'):
            n = integer(value)
            if n >= 2**int(kind[4:] or '256'):
                raise RecoveryError('ABI integer overflow')
            head.append(n.to_bytes(32, 'big'))
        else:
            raise RecoveryError('Unsupported ABI type')
    return selector + (b''.join(head) + tail).hex()


@dataclass(frozen=True)
class Event:
    block: int
    block_hash: str
    tx_hash: str
    log_index: int
    token: str
    receiver: str
    amount: int
    symbol: str
    decimals: int
    granularity: int
    user_data: bytes


def decode_cross(log, bridge):
    try:
        if log.get('removed', False):
            raise ChainChanged('Source Cross event was removed by a reorg')
        if address(log['address']) != address(bridge):
            raise RecoveryError('Cross log address mismatch')
        topics = log['topics']
        if len(topics) != 3 or topics[0].lower() != CROSS_TOPIC:
            raise RecoveryError('Unexpected Cross topics')
        raw = hex_bytes(log['data'])
        if len(raw) < 160 or len(raw) % 32 or len(raw) > 65536:
            raise RecoveryError('Malformed Cross data')
        def word(i):
            return int.from_bytes(raw[i * 32:(i + 1) * 32], 'big')
        def dynamic(offset):
            if offset < 160 or offset % 32 or offset + 32 > len(raw):
                raise RecoveryError('Malformed Cross offset')
            n = int.from_bytes(raw[offset:offset + 32], 'big')
            if offset + 32 + n > len(raw):
                raise RecoveryError('Truncated Cross field')
            return raw[offset + 32:offset + 32 + n]
        symbol = dynamic(word(1)).decode('utf-8')
        if not symbol or len(symbol) > 128 or word(3) >= 256 or not word(4):
            raise RecoveryError('Invalid Cross token fields')
        block, index = integer(log['blockNumber']), integer(log['logIndex'])
        if index >= 2**32:
            raise RecoveryError('Cross log index overflow')
        hex_bytes(log['blockHash'], 32)
        hex_bytes(log['transactionHash'], 32)
        indexed = [hex_bytes(x, 32) for x in topics[1:]]
        if any(x[:12] != b'\0' * 12 for x in indexed):
            raise RecoveryError('Malformed indexed address')
        return Event(block, log['blockHash'].lower(), log['transactionHash'].lower(), index,
                     '0x' + indexed[0][-20:].hex(), '0x' + indexed[1][-20:].hex(),
                     word(0), symbol, word(3), word(4), dynamic(word(2)))
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise RecoveryError('Malformed Cross log') from None


def strip_comments(text):
    # Preserve quoted strings; never evaluate JavaScript or private-file requires.
    return re.sub(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|//[^\n]*|/\*.*?\*/',
                  lambda m: m.group(1) or ' ', text, flags=re.S)


def parse_public_config(text):
    clean = strip_comments(text)
    refs = {}
    for field in ('mainchain', 'sidechain'):
        m = re.search(r'\b' + field + r'\s*:\s*require\([\'"]\./([\w.-]+\.json)[\'"]\)', clean)
        if not m:
            raise RecoveryError('Unsupported public chain configuration')
        refs['main_json' if field == 'mainchain' else 'side_json'] = m.group(1)
    table_start = re.search(r'\bconfirmationTable\s*:\s*\{', clean)
    if not table_start:
        raise RecoveryError('Literal confirmationTable is required')
    start = table_start.end() - 1
    depth, quoted, escaped, end = 0, False, False, None
    for i in range(start, len(clean)):
        ch = clean[i]
        if quoted:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise RecoveryError('Incomplete literal confirmationTable')
    literal = clean[start:end]
    # All supported table values are JSON literals; commas in strings are preserved.
    literal = re.sub(r'("(?:\\.|[^"\\])*")|,(\s*[}\]])',
                     lambda m: m.group(1) or m.group(2), literal)
    try:
        refs['table'] = json.loads(literal)
    except (ValueError, TypeError):
        raise RecoveryError('confirmationTable contains unsupported expressions') from None
    for field, default in [('minimumPeerAmount', None), ('runEvery', 2)]:
        match = re.search(r'\b' + field + r'\s*:\s*(\d+)\s*[,}]', clean)
        refs[field] = int(match.group(1)) if match else default
    if refs['minimumPeerAmount'] is None or refs['minimumPeerAmount'] < 1:
        raise RecoveryError('Public peer threshold is missing/invalid')
    return refs


def confirmations_for(table, chain_id, symbol, amount):
    try:
        chain = table[str(chain_id)]
        minimum = integer(chain['minConfirmation'])
        default = integer(chain['default'])
        if not minimum or default < minimum:
            raise RecoveryError('Invalid confirmation policy')
        rules = chain.get(symbol)
        if rules is None:
            return default
        value = minimum
        for rule in sorted(rules, key=lambda x: integer(x['amount'])):
            n = integer(rule['confirmations'])
            if n < minimum:
                raise RecoveryError('Invalid per-token confirmation policy')
            if integer(rule['amount']) <= amount:
                value = n
        return value
    except (KeyError, TypeError):
        raise RecoveryError('Unsupported confirmation policy') from None


@dataclass(frozen=True)
class CheckedEvent:
    event: Event
    bridge_processed: bool
    federation_processed: bool
    votes: int
    eligible: bool
    bridge_id: str = ''
    federation_id: str = ''


@dataclass
class Audit:
    start: int
    end: int
    source_head: int
    events: list

    @property
    def latest_completed(self):
        blocks = [x.event.block for x in self.events if x.eligible and x.bridge_processed]
        return max(blocks) if blocks else None

    @property
    def first_blocked(self):
        blocks = [x.event.block for x in self.events if not x.eligible or not x.bridge_processed]
        return min(blocks) if blocks else None

    @property
    def safe_frontier(self):
        blocked = self.first_blocked
        return blocked - 1 if blocked is not None else self.end


def suggest_replay(audit, targets):
    completed = [x.event.block for x in targets if x.eligible and x.bridge_processed]
    if audit and audit.latest_completed is not None:
        completed.append(audit.latest_completed)
    blocked = [x.event.block for x in targets if not x.eligible or not x.bridge_processed]
    if audit and audit.first_blocked is not None:
        blocked.append(audit.first_blocked)
    anchors = ([max(completed)] if completed else []) + ([min(blocked)] if blocked else [])
    return min(anchors) if anchors else None


def validate_replay(first_block, existing, known, completeness, source_chain):
    first_block = integer(first_block, 'first replay block')
    if not first_block:
        raise RecoveryError('Replay block must be positive')
    if any(x.event.block < first_block and (not x.bridge_processed or not x.eligible) for x in known):
        raise RecoveryError('Replay boundary would skip a known pending/unconfirmed event')
    saved = first_block - 1
    if existing is None or saved > existing:
        required = f'ALL BEFORE {source_chain}:{first_block} PROCESSED'
        if completeness.strip() != required:
            raise RecoveryError('Missing explicit older-deposit completeness statement')
    return saved


def scan_cross(rpc, bridge, start, end, max_pages, progress=None):
    if end < start:
        return []
    pages = (end - start + 100) // 100
    if pages > max_pages:
        raise RecoveryError(f'Audit needs {pages} pages, above the {max_pages}-page budget')
    logs, seen = [], set()
    for a in range(start, end + 1, 100):
        b = min(a + 99, end)
        try:
            result = rpc.call('eth_getLogs', [{'address': bridge, 'fromBlock': hex(a),
                                             'toBlock': hex(b), 'topics': [CROSS_TOPIC]}])
        except RecoveryError as exc:
            raise IncompleteAudit(str(exc), unverified=logs) from None
        try:
            if not isinstance(result, list):
                raise RecoveryError('Source scan did not return a complete log array')
            for raw in result:
                item = decode_cross(raw, bridge)
                identity = (item.tx_hash, item.log_index)
                if not a <= item.block <= b or identity in seen:
                    raise RecoveryError('Source scan returned out-of-range/duplicate logs')
                seen.add(identity)
                logs.append(item)
        except RecoveryError as exc:
            raise IncompleteAudit(str(exc), unverified=logs,
                                  chain_changed=isinstance(exc, ChainChanged)) from None
        if progress:
            progress(a, b)
    return sorted(logs, key=lambda x: (x.block, x.log_index))


class Runner:
    def run(self, args, timeout=15):
        combined_logs = args[:2] == ['docker', 'logs']
        if args[0] == 'docker':
            # Recovery and IMDS refer to this host, never a selected remote context.
            args = ['docker', '--host', 'unix:///var/run/docker.sock'] + args[1:]
        try:
            res = subprocess.run(args, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT if combined_logs else subprocess.PIPE,
                                 text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise RecoveryError(f'{args[0]} operation unavailable/timed out') from None
        if res.returncode:
            # stdout can contain a signing secret; never echo command output on failure.
            raise RecoveryError(f'{args[0]} operation failed (exit {res.returncode})')
        return res.stdout


def safe_path(path, root):
    path, root = Path(path).absolute(), Path(root).resolve()
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except ValueError:
        raise RecoveryError('Recovery path escapes the verified mount') from None
    for part in [path] + list(path.parents):
        try:
            part.resolve().relative_to(root)
        except ValueError:
            continue  # Host-wide aliases, e.g. macOS /var -> /private/var.
        if part.is_symlink():
            raise RecoveryError('Symlink in recovery path; no changes made')
        if part.resolve() == root:
            break
    return resolved


def read_checkpoint(path, root):
    path = safe_path(path, root)
    fd = open_directory(path.parent)
    try:
        result = read_regular_at(fd, path.name, 128, allow_missing=True)
        verify_directory(path.parent, fd)
        return parse_checkpoint(result[0]) if result else None
    finally:
        os.close(fd)


def parse_checkpoint(raw):
    try:
        text = raw.decode('ascii').strip()
    except UnicodeError:
        raise RecoveryError('Invalid checkpoint encoding') from None
    if not re.fullmatch(r'[0-9]{1,20}', text):
        raise RecoveryError('Checkpoint is not a valid saved block number')
    return int(text)


def open_directory(path):
    """Bind a canonical directory through an O_NOFOLLOW walk, without string races."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise RecoveryError('Directory path is not canonical')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open('/', flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError:
        os.close(fd)
        raise RecoveryError('Verified directory changed or cannot be opened safely') from None


def verify_directory(path, fd):
    current = open_directory(path)
    try:
        before, after = os.fstat(fd), os.fstat(current)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise RecoveryError('Verified directory identity changed; recovery aborted')
    finally:
        os.close(current)


def read_regular_at(directory_fd, name, limit, allow_missing=False):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    except FileNotFoundError:
        if allow_missing:
            return None
        raise RecoveryError('Required file is absent') from None
    except OSError:
        raise RecoveryError('File cannot be opened safely') from None
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode):
            raise RecoveryError('Recovery files must be regular files')
        raw = os.read(fd, limit + 1)
        if len(raw) > limit:
            raise RecoveryError('Recovery file exceeds its expected size')
        return raw, meta
    finally:
        os.close(fd)


def private_temp_at(directory_fd, prefix):
    for _ in range(10):
        name = prefix + secrets.token_hex(12)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory_fd)
            os.fchmod(fd, 0o600)
            return fd, name
        except FileExistsError:
            continue
    raise RecoveryError('Cannot create exclusive private temporary file')


def validate_key_text(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0x)?[0-9a-fA-F]{64}', value.strip()):
        raise RecoveryError('Existing secret has invalid private-key format')
    clean = value.strip()
    number = int(clean.removeprefix('0x') if hasattr(clean, 'removeprefix') else
                 (clean[2:] if clean.startswith('0x') else clean), 16)
    if not 0 < number < 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141:
        raise RecoveryError('Existing secret is not a valid signing scalar')
    return clean


def install_key(cfg, value, expected_uid):
    cfg = Path(cfg)
    key = safe_path(cfg / 'federator.key', cfg)
    clean = validate_key_text(value)
    if os.getuid() != expected_uid:
        raise RecoveryError('Operator UID does not match the expected container key owner')
    directory_fd = open_directory(key.parent)
    tmp = None
    try:
        if read_regular_at(directory_fd, key.name, 256, allow_missing=True) is not None:
            raise RecoveryError('Existing signing-key file will not be overwritten')
        fd, tmp = private_temp_at(directory_fd, '.federator.key.')
        with os.fdopen(fd, 'w') as f:
            f.write(clean + '\n')
            f.flush()
            os.fsync(f.fileno())
        # Exclusive install: a destination appearing meanwhile is not overwritten.
        verify_directory(key.parent, directory_fd)
        os.link(tmp, key.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                follow_symlinks=False)
        os.fsync(directory_fd)
    except OSError:
        raise RecoveryError('Private key installation failed; existing file preserved') from None
    finally:
        if tmp is not None:
            os.unlink(tmp, dir_fd=directory_fd)
        os.close(directory_fd)


class Node:
    FORMAT = ('{"id":{{json .Id}},"status":{{json .State.Status}},"running":{{json .State.Running}},'
              '"exit":{{.State.ExitCode}},"oom":{{.State.OOMKilled}},'
              '"started":{{json .State.StartedAt}},"finished":{{json .State.FinishedAt}},'
              '"restart":{{json .HostConfig.RestartPolicy.Name}},'
              '"image":{{json .Config.Image}},"image_id":{{json .Image}},'
              '"user":{{json .Config.User}},"mounts":{{json .Mounts}}}')

    def __init__(self, repo, profile, container, runner=None, expected_uid=1000):
        if profile not in PROFILES or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', container):
            raise RecoveryError('Invalid bridge profile/container name')
        self.repo = Path(repo).expanduser().resolve()
        self.profile = PROFILES[profile]
        self.cfg = self.repo / 'federator-env' / self.profile['env']
        self.container = container
        self.runner = runner or Runner()
        self.expected_uid = expected_uid
        self.image_id = None
        self.container_id = None
        self.mount_identity = {}

    def inspect(self):
        try:
            snap = json.loads(self.runner.run(['docker', 'inspect', self.container,
                                              '--format', self.FORMAT]))
            if not re.fullmatch(r'[0-9a-f]{64}', snap['id']):
                raise RecoveryError('Invalid container identity')
            if self.container_id is not None and self.container_id != snap['id']:
                raise RecoveryError('Container was replaced during recovery')
            protected = ('/app/federator/config', '/app/federator/db')
            mounts = {}
            for mount in snap['mounts']:
                destination = mount['Destination']
                # Docker reports canonical absolute paths; reject ambiguous/special overlays.
                if (not isinstance(destination, str) or not destination.startswith('/') or
                        destination.startswith('//') or str(PurePosixPath(destination)) != destination or
                        '..' in PurePosixPath(destination).parts):
                    raise RecoveryError('Noncanonical container mount destination; no changes made')
                if destination in mounts:
                    raise RecoveryError('Duplicate container mount destination; no changes made')
                if any(destination.startswith(root + '/') for root in protected):
                    raise RecoveryError('Container mount overrides protected config/database contents')
                mounts[destination] = Path(mount['Source']).resolve()
            safe_path(self.cfg, self.repo)
            safe_path(self.cfg / 'db', self.cfg)
            if (mounts.get('/app/federator/config') != self.cfg.resolve() or
                    mounts.get('/app/federator/db') != (self.cfg / 'db').resolve()):
                raise RecoveryError('Container config/db mounts do not match this bridge profile')
            for path in (self.cfg, self.cfg / 'db'):
                fd = open_directory(path)
                try:
                    info = os.fstat(fd)
                    identity = (info.st_dev, info.st_ino)
                    if path in self.mount_identity and self.mount_identity[path] != identity:
                        raise RecoveryError('Verified config/database directory was replaced during recovery')
                    self.mount_identity[path] = identity
                    verify_directory(path, fd)
                finally:
                    os.close(fd)
            if snap['status'] not in ('running', 'exited'):
                raise RecoveryError('Container is neither running nor exited')
            if snap['user'] not in ('node', '1000', '1000:1000'):
                raise RecoveryError('Unsupported container user; key ownership needs review')
            if not snap['image'].startswith('sovryn/fed-tokenbridge:'):
                raise RecoveryError('Unexpected federator image; no changes made')
            if self.image_id is not None and self.image_id != snap['image_id']:
                raise RecoveryError('Container image changed during recovery')
            self.image_id = snap['image_id']
            self.container_id = snap['id']
            return snap
        except (ValueError, KeyError, TypeError, OSError):
            raise RecoveryError('Restricted container inspection failed') from None

    def logs(self, count=LOG_TAIL, since=None, until=None):
        if since is None and until is None:
            end = datetime.now(timezone.utc)
            since, until = format_time(end - timedelta(minutes=15)), format_time(end)
        since, until = log_window(since, until)
        return self.runner.run(['docker', 'logs', '--timestamps', '--tail', str(count),
                                '--since', since, '--until', until,
                                self.container_id or self.container], timeout=LOG_TIMEOUT)

    def key_ready(self):
        path = safe_path(self.cfg / 'federator.key', self.cfg)
        directory_fd = open_directory(path.parent)
        try:
            raw, mode = read_regular_at(directory_fd, path.name, 256)
            if mode.st_uid != self.expected_uid or stat.S_IMODE(mode.st_mode) != 0o600:
                raise RecoveryError('Signing key must have expected UID and mode 600')
            try:
                validate_key_text(raw.decode('ascii'))
            except UnicodeError:
                raise RecoveryError('Signing-key format is invalid') from None
            verify_directory(path.parent, directory_fd)
        finally:
            os.close(directory_fd)


def redact_logs(text):
    """Best-effort sharing sanitizer; review every report before sharing it."""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'(?i)\b[a-z][a-z0-9+.-]*://[^\s<>\"\']+', '[URL redacted]', text)
    text = re.sub(r'(?i)(authorization[\"\']?\s*[:=]\s*)[^\r\n]+',
                  r'\1[credential redacted]', text)
    labels = (r'private[_-]?key|aws[_-]?access[_-]?key[_-]?id|aws[_-]?secret[_-]?access[_-]?key|'
              r'aws[_-]?session[_-]?token|password|passwd|secret|access[_-]?token|api[_-]?key|token')
    text = re.sub(r'(?i)(\b(?:' + labels + r')[\"\']?\s*[:=]\s*)'
                  r'(?:"[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s,;})]+)',
                  r'\1[credential redacted]', text)
    text = re.sub(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b', '[AWS credential redacted]', text)
    return re.sub(r'(?i)(?<![0-9a-z])(?:0x)?[0-9a-f]{64}(?![0-9a-z])',
                  '[64-hex value redacted]', text)


def sanitized(value):
    if isinstance(value, str):
        return redact_logs(value)
    if isinstance(value, dict):
        return {key: sanitized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized(item) for item in value]
    return value


def format_time(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def log_window(since, until):
    start, end = parse_time(since), parse_time(until)
    if start is None or end is None:
        raise RecoveryError('Log window requires two offset-aware instants (use Z for UTC)')
    if not 0 < (end - start).total_seconds() <= MAX_LOG_WINDOW:
        raise RecoveryError('Log window must be ordered and no longer than 24 hours')
    return format_time(start), format_time(end)


def capture_logs(node, since=None, until=None):
    if since is None and until is None:
        end = datetime.now(timezone.utc)
        since, until = format_time(end - timedelta(minutes=15)), format_time(end)
    since, until = log_window(since, until)
    started = time.perf_counter()
    capture = {'since': since, 'until': until, 'tail_limit': LOG_TAIL,
               'timeout_seconds': LOG_TIMEOUT}
    try:
        text = node.logs(since=since, until=until)
        # Redact complete tokens before a size cut can turn them into unrecognized fragments.
        cleaned = redact_logs(text)
        capture.update(status='captured', text=cleaned[:MAX_LOG_CHARS],
                       truncated=len(cleaned) > MAX_LOG_CHARS)
    except RecoveryError as exc:
        capture.update(status='unavailable', failure=redact_logs(str(exc)))
    capture['duration_seconds'] = round(time.perf_counter() - started, 3)
    return capture


def open_report(path):
    """Exclusive private report: never overwrite an existing file or a symlink."""
    path = Path(path).expanduser().absolute()
    path = safe_path(path, path.parent)
    parent = path.parent.resolve()
    directory_fd = open_directory(parent)
    fd = None
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        os.fchmod(fd, 0o600)
        verify_directory(parent, directory_fd)
        report = os.fdopen(fd, 'w')
        fd = None
        return report
    except OSError:
        raise RecoveryError('Report destination unavailable/already exists; no recovery attempted') from None
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory_fd)


def checkpoint_path(node, path):
    path = safe_path(path, node.cfg / 'db')
    if path not in (node.cfg / 'db' / 'lastBlock.txt',
                    node.cfg / 'db' / 'side-fed' / 'lastBlock.txt'):
        raise RecoveryError('Only the two verified source checkpoint paths can be changed')
    return path


def backup_db(node, destination):
    source = safe_path(node.cfg / 'db', node.cfg)
    source_fd = open_directory(source)
    def copy_dir(fd, target):
        target.mkdir(mode=0o700)
        for name in sorted(os.listdir(fd)):
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    copy_dir(child, target / name)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    current = os.fstat(child)
                    if not stat.S_ISREG(current.st_mode) or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                        raise RecoveryError('Database file changed during evidence capture')
                    out = os.open(target / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(out, 'wb') as writer:
                        while True:
                            chunk = os.read(child, 1024 * 1024)
                            if not chunk:
                                break
                            writer.write(chunk)
                finally:
                    os.close(child)
            else:
                raise RecoveryError('Database contains a symlink/special file; review before recovery')
    try:
        copy_dir(source_fd, Path(destination))
        verify_directory(source, source_fd)
    except OSError:
        raise RecoveryError('Private database evidence capture failed') from None
    finally:
        os.close(source_fd)


def atomic_checkpoint(node, path, old, new):
    path = checkpoint_path(node, path)
    if node.inspect()['running']:
        raise RecoveryError('Container is running; checkpoint not changed')
    directory_fd = open_directory(path.parent)
    tmp = None
    installed = False
    try:
        prior = read_regular_at(directory_fd, path.name, 128, allow_missing=True)
        if (parse_checkpoint(prior[0]) if prior else None) != old:
            raise RecoveryError('Checkpoint changed since diagnosis; recompute the plan')
        fd, tmp = private_temp_at(directory_fd, '.checkpoint.')
        with os.fdopen(fd, 'w') as f:
            f.write(str(integer(new, 'saved checkpoint')) + '\n')
            f.flush()
            os.fsync(f.fileno())
        verify_directory(path.parent, directory_fd)
        if old is None:
            os.link(tmp, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
        else:
            os.replace(tmp, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            tmp = None
        installed = True
        os.fsync(directory_fd)
        verify_directory(path.parent, directory_fd)
    except (OSError, RecoveryError) as exc:
        if installed:
            raise CheckpointInstalledError('Checkpoint installed; subsequent durability/path check failed') from None
        if isinstance(exc, RecoveryError):
            raise
        raise RecoveryError('Checkpoint installation failed') from None
    finally:
        if tmp is not None:
            os.unlink(tmp, dir_fd=directory_fd)
        os.close(directory_fd)


def remove_installed_checkpoint(node, path, expected):
    path = checkpoint_path(node, path)
    if node.inspect()['running']:
        raise RecoveryError('Container running; rollback refused')
    directory_fd = open_directory(path.parent)
    try:
        prior = read_regular_at(directory_fd, path.name, 128)
        if parse_checkpoint(prior[0]) != expected:
            raise RecoveryError('Checkpoint changed; rollback refused')
        verify_directory(path.parent, directory_fd)
        os.unlink(path.name, dir_fd=directory_fd)
        os.fsync(directory_fd)
        verify_directory(path.parent, directory_fd)
    except OSError:
        raise RecoveryError('Checkpoint rollback removal failed') from None
    finally:
        os.close(directory_fd)


def perform_recovery(node, changes, confirm, restart=False, pre_write=None, records=None):
    if os.getuid() != node.expected_uid:
        raise RecoveryError('Operator UID does not match the verified container file owner')
    snap = node.inspect()
    node.key_ready()
    if snap['running'] and not changes and not restart:
        return None
    for path, (old, new) in changes.items():
        checkpoint_path(node, path)
        if read_checkpoint(path, node.cfg / 'db') != old:
            raise RecoveryError('Checkpoint changed before recovery')
        integer(new, 'saved checkpoint')
    backup = Path(tempfile.mkdtemp(prefix='federator-recovery.', dir=node.repo.parent))
    os.chmod(backup, 0o700)
    (backup / 'state.json').write_text(json.dumps(snap, indent=2))
    backup_db(node, backup / 'db-before')
    try:
        (backup / 'logs.txt').write_text(redact_logs(node.logs(300)))
    except RecoveryError:
        (backup / 'logs.txt').write_text('Bounded log capture unavailable.\n')
    if snap['running']:
        if not confirm('Stop only this federator container before the reviewed recovery?'):
            return None
        fresh = node.inspect()
        node.key_ready()
        if fresh['running']:
            node.runner.run(['docker', 'stop', '--time', '30', node.container_id], timeout=40)
    if node.inspect()['running']:
        raise RecoveryError('Container did not stop; checkpoints unchanged')
    for path, (old, new) in changes.items():
        if read_checkpoint(path, node.cfg / 'db') != old:
            raise RecoveryError('Checkpoint changed during stop; checkpoints not overwritten')
    backup_db(node, backup / 'db-after-stop')
    if pre_write:
        pre_write()
    (backup / 'plan.json').write_text(json.dumps(records or [], indent=2))
    written = []
    try:
        for path, (old, new) in changes.items():
            try:
                atomic_checkpoint(node, path, old, new)
            except CheckpointInstalledError:
                written.append((path, old, new))
                raise
            written.append((path, old, new))
    except RecoveryError:
        # Roll back only our exact writes while the container is still stopped.
        rollback_failed = False
        for path, old, new in reversed(written):
            try:
                if old is None:
                    remove_installed_checkpoint(node, path, new)
                else:
                    atomic_checkpoint(node, path, new, old)
            except RecoveryError:
                rollback_failed = True
        if rollback_failed:
            raise RecoveryError('Recovery failed and rollback is unverified; leave the container stopped '
                                'and review the private evidence backup: ' + str(backup)) from None
        raise
    if confirm('Start this existing container with the preserved/restored key and reviewed cursors?'):
        fresh = node.inspect()
        node.key_ready()
        if not fresh['running']:
            node.runner.run(['docker', 'start', node.container_id], timeout=30)
        if not node.inspect()['running']:
            raise RecoveryError('Container exited after start; inspect fresh logs before retrying')
    print('Private recovery evidence:', backup)
    return backup


def ensure_signing_key(node, confirm, aws_secrets=True):
    """Require the existing identity; AWS restoration is opt-out, never automatic fallback."""
    key = safe_path(node.cfg / 'federator.key', node.cfg)
    if not key.exists():
        if not aws_secrets:
            raise RecoveryError('AWS secret recovery disabled. Manually restore the original federator key '
                                'to the selected config/federator.key (owner UID 1000, mode 600), '
                                'verify its public signer, then rerun with --no-aws-secrets. '
                                'See tools/FEDERATOR_RECOVERY.md. Container not started.')
        if not confirm('Discover this EC2 instance and restore its ORIGINAL missing signing secret?'):
            raise RecoveryError('Missing key left unchanged; container not started')
        if not restore_original_key(node, confirm):
            raise RecoveryError('Key restoration declined; container not started')
    node.key_ready()


def restart_only(node, confirm, aws_secrets=True):
    """Start the pinned container without stopping it or touching any database file."""
    snap = node.inspect()
    if snap['running']:
        print('Existing container is running; restart-only leaves it running.')
        return False
    if os.getuid() != node.expected_uid:
        raise RecoveryError('Operator UID does not match the verified container file owner')
    ensure_signing_key(node, confirm, aws_secrets)
    if not confirm('Start this existing container with the original key and unchanged database/fallbacks?'):
        print('Container start declined; database unchanged.')
        return False
    fresh = node.inspect()
    node.key_ready()
    if fresh['running']:
        print('Container started independently; no further action performed.')
        return False
    node.runner.run(['docker', 'start', node.container_id], timeout=30)
    if not node.inspect()['running']:
        raise RecoveryError('Container exited after start; inspect fresh logs before retrying')
    print('Existing container started; process start does not prove participation or transfer completion.')
    return True


def local_diagnosis(node, evidence=None):
    config, main, side = load_public_config(node)
    external = 'Ethereum' if node.profile['chain'] == 1 else 'BSC'
    cursors = []
    for name, source, path in (
            ('Rootstock→' + external, main, node.cfg / 'db' / 'lastBlock.txt'),
            (external + '→Rootstock', side, node.cfg / 'db' / 'side-fed' / 'lastBlock.txt')):
        # A follower may never have created the side-fed directory. Preserve absence.
        path = safe_path(path, node.cfg / 'db')
        existing = read_checkpoint(path, node.cfg / 'db') if path.parent.exists() else None
        fallback = integer(source['fromBlock'])
        cursors.append({'direction': name, 'saved': existing, 'fallback': fallback,
                        'next_scan': max(existing if existing is not None else fallback, fallback) + 1})
        print(f'{name}: saved cursor={existing}; fallback={fallback}; '
              f'next scan={max(existing if existing is not None else fallback, fallback) + 1}')
        if existing is None:
            print('  Cursor absent; configured fallback preserved. Historical catch-up may be required.')
    if evidence is not None:
        evidence['cursors'] = cursors
        evidence['configured_other_peer_gate'] = config['minimumPeerAmount']
    print('Local evidence only: no chain quorum or transfer completion is verified.')
    return config


class RPC:
    def __init__(self, url, timeout=10):
        if not isinstance(url, str) or urlsplit(url).scheme not in ('http', 'https'):
            raise RecoveryError('RPC URL is missing or unsupported')
        self.url, self.timeout = url, timeout

    def call(self, method, params):
        request = urllib.request.Request(
            self.url, data=json.dumps({'jsonrpc': '2.0', 'id': 1,
                                      'method': method, 'params': params}).encode(),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as res:
                body = res.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise RecoveryError('RPC response exceeds the bounded payload size')
            result = json.loads(body)
        except urllib.error.HTTPError as exc:
            raise RecoveryError(f'{method}: HTTP {exc.code} (endpoint withheld)') from None
        except (OSError, ValueError, urllib.error.URLError):
            raise RecoveryError(f'{method}: transport/JSON failure (endpoint withheld)') from None
        if not isinstance(result, dict) or result.get('id') != 1:
            raise RecoveryError(f'{method}: malformed RPC response')
        if result.get('error'):
            code = result['error'].get('code') if isinstance(result['error'], dict) else None
            code = code if type(code) is int and -(2**31) <= code < 2**31 else 'unknown'
            raise RecoveryError(f'{method}: RPC error {code} (message withheld)')
        if 'result' not in result:
            raise RecoveryError(f'{method}: RPC result missing')
        return result['result']


def result_address(value):
    raw = hex_bytes(value, 32)
    if raw[:12] != b'\0' * 12:
        raise RecoveryError('Malformed contract address result')
    return '0x' + raw[-20:].hex()


class Direction:
    def __init__(self, name, source_chain, destination_chain, source, destination, table,
                 rpc_factory=None):
        self.name, self.source_chain, self.destination_chain = name, source_chain, destination_chain
        self.source, self.destination, self.table = source, destination, table
        rpc_factory = rpc_factory or RPC
        self.source_rpc, self.destination_rpc = rpc_factory(source['host']), rpc_factory(destination['host'])
        if (integer(self.source_rpc.call('eth_chainId', [])) != source_chain or
                integer(self.destination_rpc.call('eth_chainId', [])) != destination_chain):
            raise RecoveryError(name + ': RPC chain ID mismatch')
        confirmations_for(table, source_chain, '', 0)
        self.minimum = integer(table[str(source_chain)]['minConfirmation'])
        self.source_bridge = address(source['bridge'])
        self.destination_bridge = address(destination['bridge'])
        self.source_head = integer(self.source_rpc.call('eth_blockNumber', []))
        self.refresh_destination()
        actual = result_address(self.contract(self.destination_bridge, SELECTORS['federation']))
        if actual != address(destination['federation']):
            raise RecoveryError(name + ': deployed federation differs from config; review required')
        self.federation = actual
        self.required = integer(self.contract(actual, SELECTORS['required']))
        raw = hex_bytes(self.contract(actual, SELECTORS['members']))
        if len(raw) < 64 or int.from_bytes(raw[:32], 'big') != 32:
            raise RecoveryError('Malformed federation membership result')
        n = int.from_bytes(raw[32:64], 'big')
        if not 1 <= n <= 100 or len(raw) != 64 + n * 32:
            raise RecoveryError('Invalid federation membership size')
        self.members = [result_address('0x' + raw[i:i + 32].hex()) for i in range(64, len(raw), 32)]
        if len(set(self.members)) != n or not 1 <= self.required <= n:
            raise RecoveryError('Invalid federation membership/required threshold')
        self.threshold = max(self.required, n // 2 + 1)
        self.receipt_cache = {}

    def refresh_destination(self):
        self.destination_pin = hex(integer(self.destination_rpc.call('eth_blockNumber', [])))

    def contract(self, target, data):
        return self.destination_rpc.call('eth_call', [{'to': target, 'data': data}, self.destination_pin])

    def source_header(self, block):
        result = self.source_rpc.call('eth_getBlockByNumber', [hex(block), False])
        if not isinstance(result, dict) or integer(result.get('number')) != block:
            raise RecoveryError('Source block header is absent/mismatched')
        hex_bytes(result.get('hash'), 32)
        return result

    def receipt_events(self, tx_hash):
        hex_bytes(tx_hash, 32)
        tx_hash = tx_hash.lower()
        if tx_hash not in self.receipt_cache:
            receipt = self.source_rpc.call('eth_getTransactionReceipt', [tx_hash])
            if not isinstance(receipt, dict) or integer(receipt.get('status')) != 1:
                raise RecoveryError('Supplied source transaction is missing or failed')
            if receipt.get('transactionHash', '').lower() != tx_hash:
                raise RecoveryError('Source receipt transaction identity mismatch')
            block = integer(receipt.get('blockNumber'))
            if block > self.source_head:
                raise RecoveryError('Source receipt is newer than the snapshot; rerun diagnosis')
            header = self.source_header(block)
            if receipt.get('blockHash', '').lower() != header['hash'].lower():
                raise ChainChanged('Source receipt block is not canonical')
            events = []
            for log in receipt.get('logs', []):
                if log.get('address', '').lower() == self.source_bridge and log.get('topics', [])[:1] == [CROSS_TOPIC]:
                    item = decode_cross(log, self.source_bridge)
                    if item.tx_hash != tx_hash or item.block != block or item.block_hash != header['hash'].lower():
                        raise RecoveryError('Receipt Cross event identity mismatch')
                    events.append(item)
            if not events:
                raise RecoveryError('Supplied transaction has no Cross event for this bridge')
            self.receipt_cache[tx_hash] = events
        return self.receipt_cache[tx_hash]

    def check(self, event):
        bid = self.contract(self.destination_bridge, abi_call(
            SELECTORS['bridge_id'], ['bytes32', 'bytes32', 'address', 'uint256', 'uint32'],
            [event.block_hash, event.tx_hash, event.receiver, event.amount, event.log_index]))
        fid = self.contract(self.federation, abi_call(
            SELECTORS['fed_id'], ['address', 'address', 'uint256', 'string', 'bytes32',
                                  'bytes32', 'uint32', 'uint8', 'uint256', 'bytes'],
            [event.token, event.receiver, event.amount, event.symbol, event.block_hash,
             event.tx_hash, event.log_index, event.decimals, event.granularity, event.user_data]))
        hex_bytes(bid, 32)
        hex_bytes(fid, 32)
        bd = integer(self.contract(self.destination_bridge,
                                  abi_call(SELECTORS['bridge_done'], ['bytes32'], [bid])))
        fd = integer(self.contract(self.federation,
                                  abi_call(SELECTORS['fed_done'], ['bytes32'], [fid])))
        votes = integer(self.contract(self.federation,
                                     abi_call(SELECTORS['votes'], ['bytes32'], [fid])))
        if bd not in (0, 1) or fd not in (0, 1) or bd != fd or votes > len(self.members):
            raise RecoveryError('Destination processing states disagree; manual review required')
        depth = confirmations_for(self.table, self.source_chain, event.symbol, event.amount)
        return CheckedEvent(event, bool(bd), bool(fd), votes,
                            self.source_head - event.block >= depth, bid, fid)

    def audit(self, start, end, max_pages, max_events=200):
        # Validate all covered logs, not merely successful receipt examples.
        before = {b: self.source_header(b)['hash'].lower() for b in set([start, end])}
        events = scan_cross(self.source_rpc, self.source_bridge, start, end, max_pages,
                            progress=lambda a, b: print(f'  Audit {self.name}: {a}..{b}', flush=True))
        if len(events) > max_events:
            raise IncompleteAudit('Too many events for bounded destination checks; narrow the audit',
                                  unverified=events)
        statuses = []
        try:
            for item in events:
                if item not in self.receipt_events(item.tx_hash):
                    raise RecoveryError('Scanned Cross event differs from its successful receipt')
                statuses.append(self.check(item))
            for b, expected in before.items():
                if self.source_header(b)['hash'].lower() != expected:
                    raise ChainChanged('Source reorg during audit; no checkpoint proposal is safe')
        except RecoveryError as exc:
            raise IncompleteAudit(str(exc), known=statuses,
                                  unverified=events[len(statuses):],
                                  chain_changed=isinstance(exc, ChainChanged)) from None
        return Audit(start, end, self.source_head, statuses)


def load_public_config(node):
    try:
        config = parse_public_config((node.cfg / 'config.js').read_text())
        if config['main_json'] != 'rskmainnet.json' or config['side_json'] != node.profile['json']:
            raise RecoveryError('Public config chain mapping differs from the selected profile')
        main = json.loads((node.cfg / config['main_json']).read_text())
        side = json.loads((node.cfg / config['side_json']).read_text())
        if (address(main['bridge']) != node.profile['rootstock_bridge'] or
                address(side['bridge']) != node.profile['external_bridge']):
            raise RecoveryError('Bridge addresses differ from the reviewed profile')
        for chain in (main, side):
            integer(chain['fromBlock'], 'configured fallback')
            address(chain['federation'])
        return config, main, side
    except (OSError, ValueError, KeyError, TypeError):
        raise RecoveryError('Public node configuration is incomplete/unsupported') from None


def load_directions(node):
    config, main, side = load_public_config(node)
    external = 'Ethereum' if node.profile['chain'] == 1 else 'BSC'
    reverse = Direction('Rootstock→' + external, 30, node.profile['chain'],
                        main, side, config['table'])
    inbound = Direction(external + '→Rootstock', node.profile['chain'], 30,
                        side, main, config['table'])
    return config, [(reverse, node.cfg / 'db' / 'lastBlock.txt'),
                    (inbound, node.cfg / 'db' / 'side-fed' / 'lastBlock.txt')]


def parse_time(text):
    try:
        # Docker RFC3339Nano fractions exceed Python3.8's fromisoformat support.
        text = re.sub(r'(\.\d{6})\d+(?=Z$|[+-]\d{2}:\d{2}$)', r'\1', text)
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def fresh_role(text, started):
    since = parse_time(started)
    result = {'peers': None, 'node': None, 'leader': None, 'role': 'unverified',
              'time': None, 'peer_time': None, 'role_time': None, 'activity': None,
              'main_scan': None, 'side_scan': None, 'messages': []}
    for raw in text.splitlines():
        prefix = raw.split(' ', 1)[0]
        when = parse_time(prefix)
        if when is None or since is None or when < since:
            continue
        line = redact_logs(raw)
        joined = re.search(r'Joined federators network.*Node id:\s*(\S+)', line)
        if joined:
            result['node'] = joined.group(1)
        peer = re.search(r'(\d+) total peer\(s\).*Leader:\s*(\S+)', line)
        if peer:
            result['peers'], result['leader'] = int(peer.group(1)), peer.group(2)
            result['time'] = prefix
            result['peer_time'] = prefix
        poll = re.search(r'\((\d+) other peers, node ([^,]+), leader ([^)]+)\)', line)
        waiting = re.search(r'Waiting for enough peers \(now (\d+)\. node ([^,]+), leader ([^)]+)\)', line)
        if poll or waiting:
            m = poll or waiting
            result.update(peers=int(m.group(1)), node=m.group(2), leader=m.group(3), time=prefix)
            result['role'] = ('waiting' if waiting else
                              'follower' if 'Not leader' in line else 'leader')
            result['activity'] = prefix
            result['peer_time'] = result['role_time'] = prefix
        page = re.search(r'(MAIN|SIDE)-FEDERATOR.*(?:newFromBlock:\s*|until block\s*)(\d+)', line)
        if page:
            result['main_scan' if page.group(1) == 'MAIN' else 'side_scan'] = int(page.group(2))
            result['activity'] = prefix
        if 'signature request has been received' in line or 'Submission received' in line:
            result['activity'] = prefix
        if re.search(r'Federators -|MAIN-FEDERATOR|SIDE-FEDERATOR|Not leader|This node is a leader|ENOENT|isEthereumChain|P2P', line):
            result['messages'].append(line[:500])
    result['messages'] = result['messages'][-20:]
    return result


def role_ready(role, minimum, poll_minutes, now):
    for field in ('activity', 'peer_time', 'role_time'):
        stamp = parse_time(role.get(field))
        if stamp is None or not -30 <= (now - stamp).total_seconds() <= max(60, poll_minutes * 180 + 10):
            return False
    return (role.get('peers') is not None and role['peers'] >= minimum and
            role.get('role') in ('leader', 'follower'))


def ask_yes(question):
    return input(question + ' [y/N] ').strip().lower() in ('y', 'yes')


def restore_original_key(node, confirm):
    node.inspect()
    if os.getuid() != node.expected_uid:
        raise RecoveryError('Use the verified Ubuntu UID for key restoration; do not run as root')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = 'http://169.254.169.254/latest'
    try:
        token_req = urllib.request.Request(base + '/api/token', method='PUT',
                    headers={'X-aws-ec2-metadata-token-ttl-seconds': '300'})
        with opener.open(token_req, timeout=10) as res:
            token = res.read(2048).decode()
        identity_req = urllib.request.Request(base + '/dynamic/instance-identity/document',
                         headers={'X-aws-ec2-metadata-token': token})
        with opener.open(identity_req, timeout=10) as res:
            identity = json.loads(res.read(16384))
        instance, region = identity['instanceId'], identity['region']
        if not re.fullmatch(r'i-[0-9a-f]+', instance) or not re.fullmatch(r'[a-z0-9-]+', region):
            raise RecoveryError('EC2 identity is invalid')
    except (OSError, ValueError, KeyError, UnicodeError):
        raise RecoveryError('IMDSv2 instance identity lookup failed; no secret accessed') from None
    secret_name = node.runner.run([
        'aws', 'ec2', 'describe-instances', '--region', region, '--instance-ids', instance,
        '--cli-connect-timeout', '10', '--cli-read-timeout', '20', '--query',
        "Reservations[0].Instances[0].Tags[?Key=='Name'].Value|[0]", '--output', 'text'], timeout=40).strip()
    if secret_name == 'None' or not re.fullmatch(r'[A-Za-z0-9/_+=.@-]{1,512}', secret_name):
        raise RecoveryError('EC2 Name-tag secret identifier is missing/invalid')
    other = 'eth' if node.profile['chain'] == 56 else 'bsc'
    if other in secret_name.lower():
        raise RecoveryError('Instance secret identifier appears to belong to the other bridge')
    if not confirm(f'Restore ORIGINAL instance secret {secret_name!r} for {node.profile["env"]}?'):
        return False
    raw = node.runner.run([
        'aws', 'secretsmanager', 'get-secret-value', '--region', 'us-east-2', '--secret-id', secret_name,
        '--cli-connect-timeout', '10', '--cli-read-timeout', '20', '--output', 'json'], timeout=40)
    try:
        value = json.loads(raw)['SecretString']
    except (ValueError, KeyError, TypeError):
        raise RecoveryError('Existing AWS secret did not contain the expected SecretString') from None
    node.inspect()
    install_key(node.cfg, value, node.expected_uid)
    print('Existing signing key restored privately (UID checked, mode 600).')
    return True


def print_event(direction, item):
    status = 'processed' if item.bridge_processed else 'pending'
    eligible = 'confirmed/eligible' if item.eligible else 'awaiting source confirmations'
    print(f'  {direction.name}: source block {item.event.block}, {item.event.symbol}, {status}, '
          f'{item.votes} persistent votes, {eligible}')
    print(f'    source transaction {item.event.tx_hash}; log index {item.event.log_index}')
    print(f'    TxIdU {item.federation_id}; destination snapshot {int(direction.destination_pin, 16)}')


def key_metadata(node):
    key = safe_path(node.cfg / 'federator.key', node.cfg)
    key_meta = {'present': key.exists(), 'contents': 'withheld'}
    if key_meta['present']:
        meta = key.stat()
        key_meta.update(uid=meta.st_uid, mode=f'{stat.S_IMODE(meta.st_mode):03o}')
        try:
            node.key_ready()
            key_meta['validation'] = 'valid'
        except RecoveryError as exc:
            key_meta['validation'] = redact_logs(str(exc))
    return key_meta


def inspect_node(node, evidence=None, since=None, until=None):
    snap = node.inspect()
    print(f'{utc_now()} | version {VERSION} | {node.profile["env"]} | {node.container}')
    print(f'Container: {snap["status"]}; image {snap["image"]}; OOM={snap["oom"]}; '
          f'restart policy={snap["restart"] or "none"}')
    key_meta = key_metadata(node)
    if key_meta['present']:
        print(f'Key file present: UID={key_meta["uid"]}, mode={key_meta["mode"]}; contents withheld')
    else:
        print('Key file absent: required before a stopped container can start.')
    capture = capture_logs(node, since, until)
    role = None
    if capture['status'] == 'captured':
        role = fresh_role(capture['text'], snap['started'])
        print(f'Log-window role (may be stale): {role["role"]}; other peers={role["peers"]}; '
              f'leader={role["leader"]}; node={role["node"]}')
        # Keep exceptions and stack context; do not filter through participation regexes.
        for line in capture['text'].splitlines()[-80:]:
            print('  ' + line)
        if capture['truncated']:
            print('  Log text truncated at the capture size limit.')
    else:
        print('Bounded direct log read unavailable; no role readiness is inferred:', capture['failure'])
    if evidence is not None:
        evidence.update(container=snap, key=key_meta, logs=capture, role=role)
    return snap, role


def watch(node, config, entries, targets_by_name, seconds, evidence=None):
    deadline, ready_polls = time.monotonic() + seconds, set()
    current_run = None
    evidence = evidence if evidence is not None else {}
    evidence.update(node_participation='unverified', transfer_completion='not_checked')
    while True:
        snap = node.inspect()
        if not snap['running']:
            raise RecoveryError('Federator exited; retain restored key/backups and inspect fresh logs')
        if snap['started'] != current_run:
            ready_polls.clear()
            current_run = snap['started']
        evidence['container_after'] = snap
        capture = capture_logs(node)
        evidence['watch_logs'] = capture
        role = (fresh_role(capture['text'], snap['started']) if capture['status'] == 'captured' else
                {'peers': None, 'role': 'unverified'})
        transport_ready = role_ready(role, config['minimumPeerAmount'], config['runEvery'],
                                     datetime.now(timezone.utc))
        if transport_ready:
            # A peer-join or scan message cannot count as a second role poll.
            ready_polls.add(role.get('role_time'))
        else:
            ready_polls.clear()
        print(f'{utc_now()} | role={role["role"]}, other peers={role["peers"]}', flush=True)
        evidence['watch_role'] = role
        checked_targets, all_processed, failed_read = 0, True, False
        for direction, _ in entries:
            wanted = targets_by_name.get(direction.name, [])
            if not wanted:
                continue
            try:
                direction.refresh_destination()
                for old in wanted:
                    item = direction.check(old.event)
                    print_event(direction, item)
                    checked_targets += 1
                    all_processed = all_processed and item.bridge_processed
            except RecoveryError as exc:
                failed_read = True
                print('Fresh destination read unavailable:', exc)
        evidence['node_participation'] = 'verified' if len(ready_polls) >= 2 else 'unverified'
        if checked_targets or failed_read:
            evidence['transfer_completion'] = ('unavailable' if failed_read else
                                                'processed' if all_processed else 'pending')
        if len(ready_polls) >= 2 and not failed_read and (not checked_targets or all_processed):
            print('Node participation verified by fresh role/peer messages.')
            print('Supplied target transfers processed.' if checked_targets else
                  'No target transfer supplied; process readiness is not transfer completion.')
            return True
        left = deadline - time.monotonic()
        if left <= 0:
            print('Watch deadline reached. No further restart or cursor change was attempted.')
            print('Node/transfer recovery is incomplete or unverified; keep the fresh evidence.')
            return False
        time.sleep(min(20, left))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='federator-recovery ' + VERSION)
    parser.add_argument('--report', type=Path, help='explicit exclusive mode-600 JSON report; review before sharing')
    parser.add_argument('--logs-since', help='log-window start, offset-aware instant (Z for UTC)')
    parser.add_argument('--logs-until', help='log-window end, offset-aware instant (Z for UTC); maximum 24-hour window')
    parser.add_argument('--bridge', choices=sorted(PROFILES), required=True)
    parser.add_argument('--repo', type=Path, default=Path.home() / 'Bridge-SC')
    parser.add_argument('--container', default='bridge-sc_federation_1')
    parser.add_argument('--local-only', action='store_true', help='local diagnosis without chain RPC')
    parser.add_argument('--restart-only', action='store_true', help='requires --recover; start existing stopped container without cursor edits or RPC')
    parser.add_argument('--no-aws-secrets', dest='aws_secrets', action='store_false',
                        help='disable EC2/AWS key recovery; manually restore the original key before recovery')
    parser.add_argument('--recover', action='store_true', help='interactive local mutation; requires a terminal')
    parser.add_argument('--tx', action='append', default=[], help='external-source target hash; repeatable')
    parser.add_argument('--completed-tx', action='append', default=[], help='external-source completed anchor hash')
    parser.add_argument('--rootstock-tx', action='append', default=[], help='Rootstock-source target hash')
    parser.add_argument('--rootstock-completed-tx', action='append', default=[], help='Rootstock-source completed anchor hash')
    parser.add_argument('--lookback', type=int, default=None, help='recent source blocks to audit per direction (default 1000)')
    parser.add_argument('--max-pages', type=int, default=None, help='100-block page limit per audit (default 100)')
    parser.add_argument('--no-scan', action='store_true', help='receipt checks only; cannot establish an audited frontier')
    parser.add_argument('--watch-seconds', type=int, default=600, help='bounded post-start verification (default 600)')
    args = parser.parse_args(argv)
    if args.logs_since is not None or args.logs_until is not None:
        try:
            args.logs_since, args.logs_until = log_window(args.logs_since, args.logs_until)
        except RecoveryError as exc:
            parser.error(str(exc))
    if args.restart_only and not args.recover:
        parser.error('--restart-only requires --recover')
    if args.local_only and args.recover and not args.restart_only:
        parser.error('--local-only recovery requires --restart-only to preserve cursors')
    if args.local_only or args.restart_only:
        if (args.tx or args.completed_tx or args.rootstock_tx or args.rootstock_completed_tx or
                args.lookback is not None or args.max_pages is not None or args.no_scan):
            parser.error('local/restart-only modes refuse transfer/audit/replay options; run separate chain diagnosis')
    args.lookback = 1000 if args.lookback is None else args.lookback
    args.max_pages = 100 if args.max_pages is None else args.max_pages
    if not 1 <= args.lookback <= 10000000 or not 1 <= args.max_pages <= 10000 or not 0 <= args.watch_seconds <= 3600:
        parser.error('invalid audit/watch bounds')
    if args.recover and not sys.stdin.isatty():
        parser.error('--recover requires an interactive terminal; no yes/force mode exists')
    if args.recover and os.getuid() != 1000:
        parser.error('--recover must run as the verified Ubuntu UID 1000, without sudo')
    report = open_report(args.report) if args.report else None
    started = time.monotonic()
    evidence = {'version': VERSION, 'started_utc': utc_now(), 'bridge': args.bridge,
                'mode': 'restart-only' if args.restart_only else 'local-only' if args.local_only else
                        'replay-recovery' if args.recover else 'chain-diagnosis',
                'aws_secret_recovery': args.aws_secrets,
                'node_participation': 'unverified', 'transfer_completion': 'not_checked',
                'sharing_notice': 'Best-effort sanitizer; review manually before sharing.'}
    try:
        result = run(args, evidence)
        evidence.update(outcome='complete' if result == 0 else 'unverified', exit_code=result)
        return result
    except RecoveryError as exc:
        evidence.update(outcome='failed', failure=redact_logs(str(exc)))
        raise
    except (KeyboardInterrupt, EOFError):
        evidence.update(outcome='interrupted', failure='Operator input interrupted; inspect container before retrying')
        raise
    finally:
        evidence.update(finished_utc=utc_now(), duration_seconds=round(time.monotonic() - started, 3))
        if report is not None:
            with report:
                try:
                    report.write(json.dumps(sanitized(evidence), indent=2, ensure_ascii=True) + '\n')
                    report.flush()
                    os.fsync(report.fileno())
                except OSError:
                    raise RecoveryError('Private report write failed; check container state before retrying') from None


def run(args, evidence):
    node = Node(args.repo, args.bridge, args.container)
    snap, role = inspect_node(node, evidence, args.logs_since, args.logs_until)
    if args.local_only or args.restart_only:
        config = local_diagnosis(node, evidence)
        if args.restart_only:
            restart_only(node, ask_yes, args.aws_secrets)
            evidence['container_after'] = node.inspect()
            evidence['key_after'] = key_metadata(node)
            if node.inspect()['running']:
                return 0 if watch(node, config, [], {}, args.watch_seconds, evidence) else 3
            print('Container remains stopped; participation unverified.')
        else:
            print('Diagnosis only: no keys, checkpoints or containers changed.')
        return 0
    config, entries = load_directions(node)
    print('Each direction requires', entries[0][0].threshold, 'destination validations; configured other-peer gate',
          config['minimumPeerAmount'])
    if args.recover:
        if not args.tx:
            args.tx = input('Pending external-source EventTx hashes (space-separated; blank skips): ').split()
        if not args.completed_tx:
            args.completed_tx = input('Known completed external-source EventTx anchor (blank uses bounded discovery): ').split()
        reverse_path = entries[0][1]
        if read_checkpoint(reverse_path, node.cfg / 'db') is None:
            if not args.rootstock_tx:
                args.rootstock_tx = input('Pending ROOTSTOCK-source EventTx hashes, if known (blank skips): ').split()
            if not args.rootstock_completed_tx:
                args.rootstock_completed_tx = input('Known completed ROOTSTOCK-source EventTx anchor (blank skips): ').split()
    evidence['cursors'] = []
    evidence['targets'] = []
    evidence['configured_other_peer_gate'] = config['minimumPeerAmount']
    targets_by_name, anchors_by_name, audits, partial_known, changes, records = {}, {}, {}, {}, {}, []
    for number, (direction, path) in enumerate(entries):
        existing = read_checkpoint(path, node.cfg / 'db')
        fallback = integer(direction.source['fromBlock'])
        next_block = max(existing if existing is not None else fallback, fallback) + 1
        evidence['cursors'].append({'direction': direction.name, 'saved': existing,
                                    'fallback': fallback, 'next_scan': next_block,
                                    'source_head': direction.source_head})
        print(f'\n{direction.name}: saved cursor={existing}; fallback={fallback}; next scan={next_block}; '
              f'source head={direction.source_head}')
        hashes = args.rootstock_tx if number == 0 else args.tx
        completed = args.rootstock_completed_tx if number == 0 else args.completed_tx
        targets, anchors = [], []
        for tx in hashes + completed:
            for event in direction.receipt_events(tx):
                checked = direction.check(event)
                print_event(direction, checked)
                if tx in completed:
                    if not checked.bridge_processed or not checked.eligible:
                        raise RecoveryError('Supplied completed anchor is pending/unconfirmed')
                    anchors.append(checked)
                else:
                    targets.append(checked)
        targets_by_name[direction.name], anchors_by_name[direction.name] = targets, anchors
        for item in targets:
            evidence['targets'].append({'direction': direction.name, 'source_block': item.event.block,
                                       'processed': item.bridge_processed, 'eligible': item.eligible,
                                       'votes': item.votes})
        if evidence['targets']:
            evidence['transfer_completion'] = ('processed' if all(item['processed'] for item in evidence['targets'])
                                                else 'pending')
        pending = [x.event.block for x in targets if not x.bridge_processed]
        if pending and next_block < min(pending):
            gap = min(pending) - next_block
            print(f'  Cursor is {gap:,} source blocks behind the earliest supplied pending event '
                  f'(~{math.ceil(gap / 100):,} scan pages).')
        if number == 0 and next_block + 100000 < direction.source_head:
            print('  Rootstock-first historical scan may delay the external-source loop.')
        if role and role.get('role') == 'follower' and pending:
            print('  This node is a follower. Inspect/recover the elected leader for immediate scan progress.')
        audit = None
        partial_known[direction.name] = []
        if not args.no_scan:
            # Use the minimum scan depth, then gate each event by token/amount.
            end = direction.source_head - direction.minimum
            start = max(fallback + 1, end - args.lookback + 1)
            if end >= start:
                try:
                    audit = direction.audit(start, end, args.max_pages)
                    print(f'  Complete audit coverage {start}..{end}: '
                          f'latest eligible completed event={audit.latest_completed}; '
                          f'first pending/unconfirmed event={audit.first_blocked}; '
                          f'covered whole-block frontier={audit.safe_frontier}.')
                    print('  This frontier proves only the covered window, not every older deposit.')
                except RecoveryError as exc:
                    if isinstance(exc, ChainChanged) or getattr(exc, 'chain_changed', False):
                        raise RecoveryError('Source chain changed during diagnosis; rerun before recovery') from None
                    print('  Audit unavailable/incomplete:', exc)
                    print('  No frontier is inferred from partial pages. Verified receipts remain evidence only.')
                    if isinstance(exc, IncompleteAudit):
                        partial_known[direction.name] = exc.known + [
                            CheckedEvent(e, False, False, 0, False) for e in exc.unverified]
                        if partial_known[direction.name]:
                            print('  Retained verified/unresolved event blocks as replay blockers:',
                                  sorted(set(x.event.block for x in partial_known[direction.name])))
        audits[direction.name] = audit
    if not args.recover:
        print('\nDiagnosis only: no keys, checkpoints or containers changed. Use --recover for reviewed actions.')
        return 0

    print('\nInteractive recovery: blank/No declines an action. Keep this terminal private.')
    ensure_signing_key(node, ask_yes, args.aws_secrets)
    for direction, path in entries:
        existing = read_checkpoint(path, node.cfg / 'db')
        if existing is not None and input(f'Keep {direction.name} saved cursor {existing}? [Y/n] ').strip().lower() not in ('n', 'no'):
            continue
        audit = audits[direction.name]
        known = (targets_by_name[direction.name] + anchors_by_name[direction.name] +
                 (audit.events if audit else []) + partial_known[direction.name])
        suggestion = suggest_replay(audit, known)
        text = input(f'{direction.name}: first SOURCE block to replay '
                     f'(suggested {suggestion}; blank aborts): ').strip()
        if not text:
            raise RecoveryError('Replay block not selected; no cursor write/start performed')
        first = integer(text, 'first replay block')
        fallback = integer(direction.source['fromBlock'])
        if first <= fallback or first > direction.source_head:
            raise RecoveryError('Replay block conflicts with the configured lower bound/source snapshot')
        anchor_hash = direction.source_header(first)['hash'].lower()
        complete = ''
        if existing is None or first - 1 > existing:
            print('One completed transaction alone does not establish completeness of older deposits.')
            complete = input(f'Type ALL BEFORE {direction.source_chain}:{first} PROCESSED only if verified: ')
        saved = validate_replay(first, existing, known, complete, direction.source_chain)
        print(f'Replay {direction.name}: write saved {saved}; next scan starts at whole source block {first}.')
        if input(f'Type WRITE {direction.source_chain}:{saved} to select this change: ').strip() != f'WRITE {direction.source_chain}:{saved}':
            raise RecoveryError('Cursor change declined; no checkpoint/start performed')
        changes[path] = (existing, saved)
        records.append({'utc': utc_now(), 'direction': direction.name, 'source_chain': direction.source_chain,
                        'first_block': first, 'source_hash': anchor_hash, 'old_saved': existing,
                        'new_saved': saved, 'completeness_statement': complete})
    def recheck_anchors():
        for record in records:
            direction = next(d for d, _ in entries if d.name == record['direction'])
            if direction.source_header(record['first_block'])['hash'].lower() != record['source_hash']:
                raise RecoveryError('Source replay anchor changed; no cursor write is safe')
    restart = False
    if node.inspect()['running'] and not changes:
        restart = ask_yes('Restart this already-running federator to release a diagnosed stalled poll?')
    backup = perform_recovery(node, changes, ask_yes, restart, recheck_anchors, records)
    evidence['container_after'] = node.inspect()
    evidence['key_after'] = key_metadata(node)
    if backup is None:
        print('No stop/checkpoint/start action performed.')
    if node.inspect()['running']:
        if not watch(node, config, entries, targets_by_name, args.watch_seconds, evidence):
            return 3
    else:
        print('Container remains stopped; no process recovery is claimed.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RecoveryError as exc:
        print('Recovery stopped:', redact_logs(str(exc)), file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('Interrupted. Check existing container state; do not repeat a Docker action blindly.', file=sys.stderr)
        sys.exit(130)
