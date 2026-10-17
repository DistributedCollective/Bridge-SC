#!/usr/bin/env python3
"""Read-only federator dependency diagnostics. Python 3.8+, standard library only."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time

VERSION = '1.0.0'
MAX_LOG_CHARS = 1024 * 1024
PROFILES = {'eth-rsk': ('mainnet-ETH-RSK', 'mainnet.json', 1),
            'bsc-rsk': ('mainnet-BSC-RSK', 'bmainnet.json', 56)}


class DiagnosticError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_time(value):
    try:
        value = re.sub(r'(\.\d{6})\d+(?=Z$|[+-]\d\d:\d\d$)', r'\1', value)
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def safe_path(path, root):
    path, root = Path(path).absolute(), Path(root).resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        raise DiagnosticError('Path escapes the reviewed directory') from None
    for part in [path] + list(path.parents):
        try:
            part.resolve().relative_to(root)
        except ValueError:
            continue
        if part.is_symlink():
            raise DiagnosticError('Symlink in diagnostic path')
        if part.resolve() == root:
            break
    return path.resolve()


def read_public(path, root, limit=512 * 1024):
    path = safe_path(path, root)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise DiagnosticError('Public settings must be regular files')
            raw = f.read(limit + 1)
        if len(raw) > limit:
            raise DiagnosticError('Public settings exceed bounded size')
        return raw.decode('utf8')
    except (OSError, UnicodeError):
        raise DiagnosticError('Public settings unavailable') from None


def strip_comments(text):
    return re.sub(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|//[^\n]*|/\*.*?\*/',
                  lambda m: m.group(1) or ' ', text, flags=re.S)


def public_settings(cfg, profile):
    text = strip_comments(read_public(cfg / 'config.js', cfg))
    result = {}
    for field, name in [('mainchain', 'main_json'), ('sidechain', 'side_json')]:
        m = re.search(r'\b' + field + r'\s*:\s*require\([\'"]\./([\w.-]+\.json)[\'"]\)', text)
        if not m:
            raise DiagnosticError('Unsupported static chain mapping')
        result[name] = m.group(1)
    if result['main_json'] != 'rskmainnet.json' or result['side_json'] != PROFILES[profile][1]:
        raise DiagnosticError('Public chain mapping disagrees with selected profile')
    for field, name, default in [('minimumPeerAmount', 'minimum_peers', None), ('runEvery', 'poll_minutes', 2)]:
        m = re.search(r'\b' + field + r'\s*:\s*(\d+)\s*[,}]', text)
        result[name] = int(m.group(1)) if m else default
    if not result['minimum_peers'] or not 1 <= result['minimum_peers'] <= 100:
        raise DiagnosticError('Static peer gate unsupported')
    m = re.search(r'\bfederatorAddress\s*:\s*[\'"](0x[0-9a-fA-F]{40})[\'"]', text)
    result['configured_signer'] = m.group(1).lower() if m else None
    result['signer_notice'] = 'configured public label; not proof of the running signing key'
    result['config_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    return result


class Runner:
    def run(self, args, timeout=10, input_text=None, limit=MAX_LOG_CHARS):
        if getattr(self, 'deadline', None) is not None:
            timeout = min(timeout, self.deadline - time.monotonic())
            if timeout <= 0:
                raise DiagnosticError('Overall diagnostic deadline reached')
        command = ['docker', '--host', 'unix:///var/run/docker.sock'] + args[1:] if args[0] == 'docker' else args
        try:
            result = subprocess.run(command, input=input_text, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT if args[:2] == ['docker', 'logs'] else subprocess.PIPE,
                                    text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise DiagnosticError('Command unavailable or timed out') from None
        if result.returncode:
            raise DiagnosticError('Command failed; raw output withheld')
        # Full secret-bearing output is never printed. Log consumers only emit aggregates.
        if len(result.stdout) > limit:
            raise DiagnosticError('Command output exceeds bounded size')
        return result.stdout


class Container:
    FORMAT = ('{"id":{{json .Id}},"status":{{json .State.Status}},"running":{{json .State.Running}},'
              '"started":{{json .State.StartedAt}},"finished":{{json .State.FinishedAt}},'
              '"exit":{{.State.ExitCode}},"oom":{{.State.OOMKilled}},"restarts":{{.RestartCount}},'
              '"image_id":{{json .Image}},"mounts":{{json .Mounts}}}')

    def __init__(self, repo, profile, name, runner):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise DiagnosticError('Invalid container name')
        self.repo = Path(repo).expanduser().resolve()
        self.cfg = self.repo / 'federator-env' / PROFILES[profile][0]
        self.name, self.runner, self.identity, self.image_id, self.directories = name, runner, None, None, {}

    def inspect(self):
        try:
            snap = json.loads(self.runner.run(['docker', 'inspect', self.name, '--format', self.FORMAT]))
            if not re.fullmatch(r'[0-9a-f]{64}', snap['id']) or not re.fullmatch(r'sha256:[0-9a-f]{64}', snap['image_id']):
                raise DiagnosticError('Invalid container/image identity')
            if self.identity and (self.identity != snap['id'] or self.image_id != snap['image_id']):
                raise DiagnosticError('Container or image was replaced during diagnosis')
            roots = {'/app/federator/config': self.cfg, '/app/federator/db': self.cfg / 'db'}
            mounts = {}
            for m in snap['mounts']:
                dest = m['Destination']
                if (not isinstance(dest, str) or not dest.startswith('/') or dest.startswith('//') or
                        str(PurePosixPath(dest)) != dest or '..' in PurePosixPath(dest).parts or dest in mounts or
                        any(dest.startswith(root + '/') for root in roots)):
                    raise DiagnosticError('Unsafe/overriding config or database mount')
                mounts[dest] = Path(m['Source']).resolve()
            for dest, path in roots.items():
                safe_path(path, self.repo)
                if mounts.get(dest) != path.resolve():
                    raise DiagnosticError('Mounts disagree with selected host/profile')
                meta = path.stat()
                if not stat.S_ISDIR(meta.st_mode):
                    raise DiagnosticError('Mount directory unavailable')
                identity = (meta.st_dev, meta.st_ino)
                if path in self.directories and identity != self.directories[path]:
                    raise DiagnosticError('Mount directory replaced during diagnosis')
                self.directories[path] = identity
            if snap['status'] not in ('running', 'exited') or type(snap['running']) is not bool:
                raise DiagnosticError('Unsupported container state')
            self.identity, self.image_id = snap['id'], snap['image_id']
            return {k: snap[k] for k in ('id', 'status', 'running', 'started', 'finished', 'exit', 'oom', 'restarts', 'image_id')}
        except (OSError, ValueError, KeyError, TypeError):
            raise DiagnosticError('Restricted container inspection unavailable') from None


def log_summary(text, started, minimum, now=None):
    now = now or datetime.now(timezone.utc)
    beginning = parse_time(started)
    counts = {'auth_type_error': 0, 'missing_key': 0, 'npm_failure': 0, 'gas_oracle': 0}
    peers, role_time, role, skew = None, None, 'unverified', None
    lines = text.splitlines()[-2000:]
    for index, line in enumerate(lines):
        docker_time = parse_time(line.split(' ', 1)[0])
        if docker_time is None or beginning is None or docker_time < beginning:
            continue
        context = '\n'.join(lines[index:index + 12])
        if 'TypeError' in line and ('RSKKeyedAuth' in context or 'Buffer.concat' in context or 'stream' in context or 'Received null' in line):
            counts['auth_type_error'] += 1
        if 'ENOENT' in line and 'federator.key' in line:
            counts['missing_key'] += 1
        if 'npm ERR!' in line:
            counts['npm_failure'] += 1
        if 'runGasPriceService' in line or 'etherscan' in line.lower():
            counts['gas_oracle'] += 1
        match = re.search(r'\((\d+) other peers, node [^,]+, leader [^)]+\)', line)
        waiting = re.search(r'Waiting for enough peers \(now (\d+)\. node [^,]+, leader [^)]+\)', line)
        match = match or waiting
        if match and -30 <= (now - docker_time).total_seconds() <= 370:
            peers, role_time = int(match.group(1)), docker_time.isoformat().replace('+00:00', 'Z')
            role = 'waiting' if waiting else 'follower' if 'Not leader' in line else 'leader' if 'leader --' in line or 'This node is a leader' in line else 'unverified'
        app = re.search(r'\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)\]', line)
        if app:
            app_time = parse_time(app.group(1) + 'Z')
            if app_time:
                skew = round((docker_time - app_time).total_seconds())
    return {'fatal_counts': counts, 'fresh_other_peers': peers, 'role': role, 'role_time': role_time,
            'configured_other_peer_gate': minimum, 'peer_gate_met': peers is not None and peers >= minimum,
            'app_clock_skew_seconds': skew, 'app_clock_notice': 'timezone-free app dates compared as UTC only; source timezone unknown',
            'raw_logs': 'withheld; aggregate markers only'}


def datadog_summary(runner, cid):
    try:
        raw = runner.run(['docker', 'inspect', 'datadog-agent', '--format',
                          '{"id":{{json .Id}},"running":{{json .State.Running}}}'])
        state = json.loads(raw)
        if not re.fullmatch(r'[0-9a-f]{64}', state['id']) or state['running'] is not True:
            return {'status': 'WARN', 'agent': 'not_running'}
        raw = runner.run(['docker', 'exec', state['id'], 'agent', 'status'], timeout=15)
        counters = {}
        for field in ('LogsProcessed', 'LogsSent', 'BytesSent', 'BytesSentUncompressed', 'LogsDropped'):
            match = re.search(r'\b' + field + r'\s*:\s*(\d[\d,]*)', raw)
            if match:
                counters[field] = int(match.group(1).replace(',', ''))
        return {'status': 'WARN', 'agent': 'running', 'source_discovered': cid in raw,
                'counters': counters, 'notice': 'counters/discovery do not prove current log delivery'}
    except (DiagnosticError, ValueError, KeyError, TypeError):
        return {'status': 'SKIP', 'agent': 'unavailable', 'notice': 'no API-key validation, environment dump or submission attempted'}


def safe_result(value):
    # Only fixed summaries leave Node. Also scrub exceptional provider/test payloads defensively.
    if isinstance(value, str):
        value = re.sub(r'(?i)\b[a-z][a-z0-9+.-]*://\S+', '[URL withheld]', value)
        value = re.sub(r'(?i)(private[_-]?key|api[_-]?key|token|password|secret)\s*[:=]\s*\S+', '[credential withheld]', value)
        return value
    if isinstance(value, dict):
        return {k: safe_result(v) for k, v in value.items() if k not in ('Env', 'raw', 'url', 'apikey', 'key', 'message', 'stack')}
    if isinstance(value, list):
        return [safe_result(x) for x in value]
    return value


def runtime_probe(container, profile, versions, runner, timeout=50):
    snap = container.inspect()
    args = ['docker', 'exec', '-i', container.identity, 'node', '-', profile]
    utility = None
    if not snap['running']:
        if not versions:
            return {'checks': [{'name': 'runtime', 'status': 'SKIP', 'failure': 'STOPPED'}]}
        utility = 'federator-dependency-versions-' + secrets.token_hex(8)
        args = ['docker', 'run', '--rm', '--name', utility, '-i', '--network', 'none', '--read-only', '--log-driver', 'none',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '64',
                '--memory', '128m', '--entrypoint', 'node', container.image_id, '-', profile]
    remaining = min(timeout, getattr(runner, 'deadline', None) - time.monotonic()) if getattr(runner, 'deadline', None) is not None else timeout
    if remaining <= 1:
        return {'checks': [{'name': 'runtime', 'status': 'WARN', 'failure': 'WALL_DEADLINE'}]}
    args.extend(['--budget-ms', str(min(45000, int((remaining - 1) * 1000)))])
    if versions:
        args.append('--versions-only')
    try:
        body = runner.run(args, timeout=timeout, input_text=NODE_CORE + '\n' + NODE_ENTRY)
        value = json.loads(body)
        if not isinstance(value, dict) or not isinstance(value.get('checks'), list):
            raise DiagnosticError('Malformed runtime evidence')
        return safe_result(value)
    except (DiagnosticError, ValueError, TypeError):
        evidence = {'checks': [{'name': 'runtime', 'status': 'WARN', 'failure': 'UNAVAILABLE_OR_TIMEOUT'}]}
        if utility is not None:
            # Only our randomly named, mount-free utility is removable; never the federator.
            previous = getattr(runner, 'deadline', None)
            try:
                runner.deadline = None
                runner.run(['docker', 'rm', '--force', utility], timeout=3)
                evidence['offline_utility_cleanup'] = 'completed'
            except DiagnosticError:
                evidence['offline_utility_cleanup'] = 'unavailable_or_already_absent'
            finally:
                runner.deadline = previous
        return evidence


def collect(args, runner, evidence=None):
    node = Container(args.repo, args.profile, args.container, runner)
    snap = node.inspect()
    settings = ({'minimum_peers': None, 'notice': 'versions-only skips config reads'} if args.versions_only else
                public_settings(node.cfg, args.profile))
    report = evidence if evidence is not None else {}
    report.update({'version': VERSION, 'utc': utc_now(), 'profile': args.profile, 'container': snap,
              'public_settings': settings, 'p2p_active_connect': 'SKIP',
              'p2p_notice': 'DNS and admitted-peer logs only; raw TCP connects may trigger remote handshake faults',
              'runtime_samples': [], 'log_samples': [], 'root_candidates': [],
                   'observed_not_running': not snap['running'], 'container_end': snap})
    try:
        commit = runner.run(['git', '-C', str(node.repo), 'rev-parse', 'HEAD']).strip()
        report['host_commit'] = commit if re.fullmatch(r'[0-9a-f]{40}', commit) else None
    except DiagnosticError:
        report['host_commit'] = None
    report['host_commit_notice'] = 'host checkout is not proof of image build revision'
    try:
        image = json.loads(runner.run(['docker', 'image', 'inspect', node.image_id, '--format',
            '{"digests":{{json .RepoDigests}},"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}},"created":{{json .Created}}}']))
        report['image'] = {'id': node.image_id, 'digests': [x.split('@')[-1] for x in image.get('digests') or []
                            if re.search(r'@sha256:[0-9a-f]{64}$', x)],
                           'revision': image.get('revision') if re.fullmatch(r'[0-9a-f]{7,40}', image.get('revision') or '') else None,
                           'created': image.get('created')}
    except (DiagnosticError, ValueError, TypeError):
        report['image'] = {'id': node.image_id, 'metadata': 'unavailable'}
    disk = os.statvfs(node.cfg / 'db')
    report['host_disk'] = {'free_bytes': disk.f_bavail * disk.f_frsize, 'free_inodes': disk.f_favail}
    start = time.monotonic()
    deadline = start + max(90, args.watch + 50)
    count = 1 if args.versions_only or not snap['running'] else args.samples
    for index in range(count):
        if args.watch and index:
            delay = max(0, start + args.watch * index / max(1, count - 1) - time.monotonic())
            if delay:
                time.sleep(min(delay, max(0, deadline - time.monotonic())))
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            report['runtime_samples'].append({'checks': [{'name': 'watch', 'status': 'WARN', 'failure': 'WALL_DEADLINE'}]})
            break
        report['runtime_samples'].append(runtime_probe(node, args.profile, args.versions_only, runner, min(50, remaining)))
        if not args.versions_only:
            fresh = node.inspect()
            report['container_end'] = fresh
            report['observed_not_running'] = report['observed_not_running'] or not fresh['running']
            try:
                end = datetime.now(timezone.utc)
                raw = runner.run(['docker', 'logs', '--timestamps', '--tail', '2000', '--since',
                    (end - timedelta(minutes=15)).isoformat(), '--until', end.isoformat(), node.identity], timeout=10)
                report['log_samples'].append(log_summary(raw, fresh['started'], settings['minimum_peers']))
            except DiagnosticError:
                report['log_samples'].append({'status': 'WARN', 'failure': 'CAPTURE_UNAVAILABLE_OR_TOO_LARGE'})
            try:
                stats = json.loads(runner.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', node.identity]))
                report['docker_resources'] = {key: stats.get(key) for key in ('CPUPerc', 'MemUsage', 'MemPerc', 'PIDs', 'BlockIO')}
            except (DiagnosticError, ValueError, TypeError):
                report['docker_resources'] = {'status': 'SKIP'}
    try:
        report['container_end'] = node.inspect()
    except DiagnosticError as exc:
        if 'replaced' in str(exc) or 'mount' in str(exc).lower():
            raise
        report['container_end'] = {'running': None, 'status': 'unverified'}
        report['root_candidates'].append('container_end_state_unverified')
    report['observed_not_running'] = report['observed_not_running'] or report['container_end']['running'] is False
    report['datadog'] = datadog_summary(runner, node.identity) if not args.versions_only and report['container_end']['running'] else {'status': 'SKIP'}
    checks = [c for sample in report['runtime_samples'] for c in sample.get('checks', [])]
    if report['observed_not_running']:
        report['root_candidates'].append('container_stopped: version evidence does not establish participation')
    if any(c.get('status') == 'FAIL' for c in checks):
        report['root_candidates'].append('dependency_failure: compare repeated inside-container samples')
    if any(c.get('failure') == 'DNS' for c in checks):
        report['root_candidates'].append('DNS/provider_path')
    if any(log.get('fatal_counts', {}).get('auth_type_error') for log in report['log_samples']):
        report['root_candidates'].append('authentication_stream_fault: gas oracle error alone is not process-crash proof')
    if report['log_samples'] and not report['log_samples'][-1].get('peer_gate_met'):
        report['root_candidates'].append('fresh_peer_gate_unverified')
    report['status'] = ('FAIL' if report['observed_not_running'] or any(c.get('status') == 'FAIL' for c in checks) else
                        'WARN' if report['root_candidates'] or any(c.get('status') in ('WARN', 'SKIP') for c in checks) else 'PASS')
    report.pop('failure', None)
    report['notice'] = 'read-only observations, not transfer settlement; review report before sharing'
    return safe_result(report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=sorted(PROFILES), required=True)
    parser.add_argument('--container', default='bridge-sc_federation_1')
    parser.add_argument('--repo', type=Path, default=Path.home() / 'Bridge-SC')
    parser.add_argument('--versions-only', action='store_true')
    parser.add_argument('--watch', type=int, default=0, help='observation window seconds, 0..600; at most 3 samples')
    parser.add_argument('--samples', type=int, default=2, help='1..3 inside-container samples')
    parser.add_argument('--output', type=Path, help='exclusive private JSON file; no raw logs/credentials')
    args = parser.parse_args(argv)
    if not 0 <= args.watch <= 600 or not 1 <= args.samples <= 3 or args.versions_only and args.watch:
        parser.error('invalid watch/sample bounds or versions-only combination')
    report_file = None
    if args.output:
        path = Path(args.output).expanduser().absolute()
        path = safe_path(path, path.parent)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
            report_file = os.fdopen(fd, 'w')
        except OSError:
            raise DiagnosticError('Private report destination exists or is unavailable') from None
    start = time.monotonic()
    result = {'utc': utc_now(), 'status': 'FAIL', 'failure': 'DIAGNOSIS_INCOMPLETE'}
    try:
        runner = Runner()
        runner.deadline = start + max(90, args.watch + 50)
        result = collect(args, runner, result)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'PASS' else 2
    except DiagnosticError:
        result['status'] = 'FAIL'
        result['failure'] = 'GUARD_OR_DEADLINE_FAILURE'
        raise
    finally:
        if report_file:
            result = safe_result(result)
            with report_file:
                result['duration_seconds'] = round(time.monotonic() - start, 3)
                report_file.write(json.dumps(result, indent=2) + '\n')
                report_file.flush()
                os.fsync(report_file.fileno())

# Executed with node stdin inside the pinned existing container (or an offline image
# for versions only). No config module is required and no signing/P2P APIs are used.
NODE_CORE = r'''
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const dns = require('dns');
const http = require('http');
const https = require('https');
const os = require('os');
const APP = '/app/federator';
const CFG = APP + '/config';
const MAX_BODY = 128 * 1024;
const REQUEST_MS = 5000;
const PROFILE = {
  'eth-rsk': {side:'mainnet.json',chain:1,bridge:'0x33c0d33a0d4312562ad622f91d12b0ac47366ee1',rsk:'0x1ccad820b6d031b41c54f1f3da11c0d48b399581'},
  'bsc-rsk': {side:'bmainnet.json',chain:56,bridge:'0xdfc7127593c8af1a17146893f10e08528f4c2aa7',rsk:'0x971b97c8cc82e7d27bc467c2dc3f219c6ee2e350'}
};
const SELECT = {federation:'0xea217091',members:'0x9eab5253',required:'0xdc8452cd',owner:'0x8da5cb5b'};
function file(p, limit=512*1024) {
  const s=fs.lstatSync(p);
  if (!s.isFile() || s.isSymbolicLink() || s.size>limit) throw Error('FILE');
  return fs.readFileSync(p).toString('utf8');
}
function comments(t) {
  return t.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,(all,quoted)=>quoted||' ');
}
function readPublic(profile) {
  const p=PROFILE[profile]; if(!p) throw Error('PROFILE');
  const t=comments(file(CFG+'/config.js'));
  const main=t.match(/\bmainchain\s*:\s*require\(['"]\.\/([\w.-]+\.json)['"]\)/);
  const side=t.match(/\bsidechain\s*:\s*require\(['"]\.\/([\w.-]+\.json)['"]\)/);
  if(!main || !side || main[1]!=='rskmainnet.json' || side[1]!==p.side) throw Error('CONFIG');
  const peer=t.match(/\bminimumPeerAmount\s*:\s*(\d+)/);
  const signer=t.match(/\bfederatorAddress\s*:\s*['"](0x[0-9a-fA-F]{40})['"]/);
  return {main_json:main[1],side_json:side[1],minimum_peers:peer?Number(peer[1]):null,
          signer:signer?signer[1].toLowerCase():null};
}
function validQuantity(v) {
  if(typeof v!=='string' || !/^0x(?:0|[1-9a-f][0-9a-f]*)$/i.test(v) || v.length>66) return null;
  try {return BigInt(v).toString();} catch(e) {return null;}
}
function validNetwork(v) {return typeof v==='string' && /^(?:0|[1-9][0-9]*)$/.test(v) && v.length<=20 ? v : null;}
function addr(v) {return typeof v==='string' && /^0x[0-9a-f]{40}$/i.test(v)?v.toLowerCase():null;}
function wordAddress(v) {
  return typeof v==='string' && /^0x0{24}[0-9a-f]{40}$/i.test(v) ? v.slice(0,2)+v.slice(-40).toLowerCase():null;
}
function uintWord(v) {return typeof v==='string' && /^0x[0-9a-f]{64}$/i.test(v) ? Number(BigInt(v)):null;}
function memberList(v) {
  if(typeof v!=='string' || !/^0x[0-9a-f]+$/i.test(v) || v.length<130) return null;
  const n=Number(BigInt('0x'+v.slice(66,130)));
  if(v.slice(2,66)!=='0'.repeat(62)+'20' || !Number.isSafeInteger(n) || n<1 || n>100 || v.length!==130+n*64) return null;
  const out=[];for(let i=0;i<n;i++) {const a=wordAddress('0x'+v.slice(130+i*64,194+i*64));if(!a || out.includes(a))return null;out.push(a);}
  return out;
}
function safeFailure(e) {
  const code=e && e.code;
  if(['ENOTFOUND','EAI_AGAIN'].includes(code)) return 'DNS';
  if(['ETIMEDOUT','TIMEOUT'].includes(code)) return 'TIMEOUT';
  if(['CERT_HAS_EXPIRED','DEPTH_ZERO_SELF_SIGNED_CERT','UNABLE_TO_VERIFY_LEAF_SIGNATURE','ERR_TLS_CERT_ALTNAME_INVALID'].includes(code)) return 'TLS';
  return 'TRANSPORT';
}
function request(url, body=null) {
  return new Promise(resolve=>{
    let target;try{target=new URL(url);}catch(e){return resolve({failure:'URL'});}
    if(!['http:','https:'].includes(target.protocol))return resolve({failure:'URL'});
    let done=false, req, timer;const transport={};const start=Date.now();
    const finish=(x,providerBody=false)=>{if(done)return;if(!x||typeof x!=='object'||Array.isArray(x))x={failure:'JSON_SHAPE'};else if(providerBody)x={body:x};done=true;clearTimeout(timer);resolve(Object.assign(x,{transport:Object.assign(transport,{duration_ms:Date.now()-start})}));};
    timer=setTimeout(()=>{finish({failure:'TIMEOUT'});if(req)req.destroy();},REQUEST_MS);
    try {
      req=(target.protocol==='https:'?https:http).request(target,{
        method:body===null?'GET':'POST',rejectUnauthorized:true,
        headers:{'Content-Type':'application/json','Accept-Encoding':'identity','User-Agent':'federator-dependencies/1.0'}
      },res=>{
        transport.http_status=res.statusCode;
        if(res.statusCode!==200){finish({failure:'HTTP',http_status:res.statusCode});res.destroy();return;}
        let size=0,chunks=[];
        res.on('data',chunk=>{size+=Buffer.byteLength(chunk);if(size>MAX_BODY){finish({failure:'BODY_LIMIT'});res.destroy();req.destroy();}else chunks.push(Buffer.from(chunk));});
        res.on('error',e=>finish({failure:safeFailure(e)}));
        res.on('end',()=>{if(done)return;try{finish(JSON.parse(Buffer.concat(chunks).toString('utf8')),true);}catch(e){finish({failure:'JSON'});}});
      });
      req.on('socket',socket=>{
        socket.on('lookup',(err)=>{transport.dns=err?'FAIL':'PASS';});
        socket.on('secureConnect',()=>{transport.tls_authorized=socket.authorized===true;transport.tls_protocol=socket.getProtocol();});
      });
      req.on('error',e=>finish({failure:safeFailure(e)}));
      if(body!==null)req.write(JSON.stringify(body));req.end();
    } catch(e) {finish({failure:safeFailure(e)});if(req)req.destroy();}
  });
}
const INTERNAL_FAILURES=new Set(['URL','DNS','TIMEOUT','TLS','TRANSPORT','HTTP','BODY_LIMIT','JSON','JSON_SHAPE']);
function transportSummary(value) {
  if(!value||typeof value!=='object')return undefined;
  const out={};
  if(['PASS','FAIL'].includes(value.dns))out.dns=value.dns;
  if(typeof value.tls_authorized==='boolean')out.tls_authorized=value.tls_authorized;
  if(typeof value.tls_protocol==='string'&&/^TLSv1(?:\.[0-3])?$/.test(value.tls_protocol))out.tls_protocol=value.tls_protocol;
  if(Number.isInteger(value.http_status)&&value.http_status>=100&&value.http_status<=599)out.http_status=value.http_status;
  if(Number.isFinite(value.duration_ms)&&value.duration_ms>=0&&value.duration_ms<=600000)out.duration_ms=value.duration_ms;
  return out;
}
function internalFailure(value) {
  if(!value||typeof value!=='object')return {failure:'JSON_SHAPE'};
  if(!Object.prototype.hasOwnProperty.call(value,'failure'))return null;
  const out={failure:INTERNAL_FAILURES.has(value.failure)?value.failure:'JSON_SHAPE',transport:transportSummary(value.transport)};
  if(Number.isInteger(value.http_status)&&value.http_status>=100&&value.http_status<=599)out.http_status=value.http_status;
  return out;
}
async function rpc(url,method,params) {
  const response=await request(url,{jsonrpc:'2.0',id:1,method,params});
  const failure=internalFailure(response);if(failure)return failure;
  const v=response.body,transport=transportSummary(response.transport);
  if(!v||typeof v!=='object'||Object.prototype.hasOwnProperty.call(v,'failure'))return {failure:'RPC_SHAPE',transport};
  if(v.error){const code=v.error.code;return {failure:'RPC',rpc_code:Number.isInteger(code)&&code>=-2147483648&&code<=2147483647?code:null,transport};}
  if(v.id!==1 || !Object.prototype.hasOwnProperty.call(v,'result'))return {failure:'RPC_SHAPE',transport};
  return {result:v.result,transport};
}
function summarizeLogs(v,historical) {
  if(!Array.isArray(v))return {status:'FAIL',failure:'LOG_SHAPE'};
  const truncated=v.length>500;
  const valid=v.slice(0,500).every(x=>x && validQuantity(x.blockNumber)!==null && x.removed!==true);
  return {status:!valid?'FAIL':truncated || historical && v.length===0?'WARN':'PASS',count:Math.min(v.length,500),
          truncated,notice:historical && v.length===0?'empty history is not proof of no deposits':'bounded log availability, not settlement/completeness'};
}
function oracleSummary(v) {
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.prototype.hasOwnProperty.call(v,'failure'))
    return {status:'FAIL',failure:'JSON_SHAPE',raw_body:'withheld'};
  const raw=v && v.result;const value=raw && typeof raw==='object'?raw.SafeGasPrice:null;
  const valid=typeof value==='string' && /^\d+(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value)) && Number(value)>0;
  return {status:v && v.status==='1' && valid?'PASS':'FAIL',safe_gwei:valid?value:null,
          deprecated:typeof raw==='string' && /deprecated|v1 endpoint/i.test(raw),raw_body:'withheld'};
}
function oracleResponse(value) {
  const failure=internalFailure(value);
  return failure?Object.assign({status:'FAIL'},failure):oracleSummary(value.body);
}
function signingScalarShape(value) {return typeof value==='string'&&/^(?:0x)?[0-9a-f]{64}$/i.test(value.trim());}
function versions() {
  const out={node:process.version,packages:{},source_sha256:{}};
  for(const pkg of ['web3','ethers','ataraxia','ataraxia-tcp','ataraxia-transport','ataraxia-transport-streams','sodium-secretstream','sodium-native','ethereumjs-tx','@ethereumjs/tx','@ethereumjs/common']) {
    try {const filename=require.resolve(pkg+'/package.json',{paths:[APP]});const p=JSON.parse(file(filename));out.packages[pkg]=typeof p.version==='string'&&/^\d+\.\d+\.\d+[\w.+-]*$/.test(p.version)?p.version:'unsupported';}
    catch(e){out.packages[pkg]='unavailable';}
  }
  for(const rel of ['src/main.js','src/lib/p2p.js','src/lib/ClientId.js','src/lib/Federator.js','src/services/Scheduler.js','src/lib/TransactionSender.js','src/lib/GasPriceFetcher.js','src/lib/GasPriceAvg.js','src/lib/GasServices.js','src/vendors/RSKKeyedAuth.js','package.json','package-lock.json']) {
    try {out.source_sha256[rel]=crypto.createHash('sha256').update(file(APP+'/'+rel,4*1024*1024)).digest('hex');}
    catch(e){out.source_sha256[rel]='unavailable';}
  }
  try {const gas=file(APP+'/src/lib/GasPriceFetcher.js');out.gas_strategy=gas.includes('/v2/api')?'v2_present':'legacy_v1_or_unknown';}catch(e){out.gas_strategy='unavailable';}
  return out;
}
function resources() {
  const out={probe_node_rss_bytes:process.memoryUsage().rss,total_ram_bytes:os.totalmem(),free_ram_bytes:os.freemem(),cgroup:{},checkpoints:{}};
  for(const p of ['/sys/fs/cgroup/memory.current','/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory/memory.usage_in_bytes','/sys/fs/cgroup/memory/memory.limit_in_bytes']) {
    try {const v=file(p,256).trim();if(/^\d+$/.test(v)||v==='max')out.cgroup[path.basename(p)]=v;}catch(e){}
  }
  for(const rel of ['lastBlock.txt','side-fed/lastBlock.txt']) {
    try {const v=file(APP+'/db/'+rel,128).trim();out.checkpoints[rel]=/^\d{1,20}$/.test(v)?v:'invalid';}
    catch(e){out.checkpoints[rel]='absent_or_unavailable';}
  }
  try {const p=file('/proc/1/stat',4096).replace(/^.*\) /,'').split(' ');out.container_init_process1={state:p[0],cpu_user_ticks:p[11],cpu_system_ticks:p[12],rss_pages:p[21]};}catch(e){out.container_init_process1='unavailable';}
  return out;
}
function resolveDNS(host) {
  return new Promise(resolve=>{
    let done=false;const timer=setTimeout(()=>{done=true;resolve({status:'WARN',failure:'TIMEOUT'});},REQUEST_MS);
    dns.lookup(host,(e)=>{if(done)return;done=true;clearTimeout(timer);resolve(e?{status:'FAIL',failure:'DNS'}:{status:'PASS'});});
  });
}
function feeReadiness(block,now=Date.now()/1000) {
  const fee=block&&validQuantity(block.baseFeePerGas),stamp=block&&validQuantity(block.timestamp);
  const age=stamp===null||stamp===undefined?null:now-Number(stamp);
  const positive=fee!==null&&fee!==undefined&&BigInt(fee)>0n;
  return {status:positive&&age!==null&&age>=-30&&age<=120?'PASS':'FAIL',base_fee_wei:fee,age_seconds:age,
          failure:positive&&age!==null&&age>=-30&&age<=120?null:'FRESH_POSITIVE_BASE_FEE_UNAVAILABLE'};
}
async function chainChecks(label,cfg,expected,signer,minimum,add,saved=null,events=null) {
  let u;try{u=new URL(cfg.host);if(!['https:','http:'].includes(u.protocol))throw Error('URL');}
  catch(e){add({name:label+'.rpc',status:'FAIL',failure:'CONFIG_URL'});return;}
  const endpoint_hash=crypto.createHash('sha256').update(cfg.host).digest('hex');
  const a=await rpc(cfg.host,'eth_chainId',[]),b=await rpc(cfg.host,'net_version',[]);
  const chain=validQuantity(a.result),net=validNetwork(b.result);
  const status=chain===String(expected)&&net===String(expected)?'PASS':'FAIL';
  add({name:label+'.rpc',status,chain_id:chain?Number(chain):null,net_version:net?Number(net):null,
       failure:a.failure||b.failure||(status==='FAIL'?'CHAIN_ID_OR_NET_VERSION':null),rpc_code:a.rpc_code||b.rpc_code||null,
       transport:a.transport,endpoint_hash});
  if(status!=='PASS')return;
  const block=await rpc(cfg.host,'eth_getBlockByNumber',['latest',false]);
  const head=block.result&&validQuantity(block.result.number),timestamp=block.result&&validQuantity(block.result.timestamp);
  const age=timestamp===null||timestamp===undefined?null:Math.floor(Date.now()/1000)-Number(timestamp);
  add({name:label+'.head',status:head && age!==null && age>=-30 && age<300?'PASS':'WARN',number:head,
       timestamp_utc:timestamp?new Date(Number(timestamp)*1000).toISOString():null,age_seconds:age,
       base_fee_wei:block.result?validQuantity(block.result.baseFeePerGas):null,
       rsk_minimum_gas_wei:block.result?validQuantity(block.result.minimumGasPrice):null,failure:block.failure||null});
  if(expected===1)add(Object.assign({name:label+'.fee_readiness'},feeReadiness(block.result)));
  for(const method of ['eth_syncing','eth_gasPrice']) {
    const v=await rpc(cfg.host,method,[]);const good=method==='eth_syncing'?v.result===false:validQuantity(v.result)!==null&&validQuantity(v.result)!=='0';
    add({name:label+'.'+method,status:v.failure?'FAIL':good?'PASS':'WARN',failure:v.failure||null,
         value:method==='eth_syncing'?(v.result===false?'not_syncing':'syncing_or_unknown'):validQuantity(v.result)});
  }
  if(head) {
    const n=Number(head);const windows=[['recent',Math.max(0,n-99),n]];
    const cursor=typeof saved==='string' && /^\d{1,20}$/.test(saved)?Number(saved):null;
    if(Number.isSafeInteger(cursor)&&cursor>0&&cursor<=n)windows.push(['saved_cursor',cursor,Math.min(n,cursor+1)]);
    const fallback=Number(cfg.fromBlock);
    if(Number.isSafeInteger(fallback)&&fallback>0&&fallback<=n)windows.push(['configured_history',fallback,Math.min(n,fallback+1)]);
    if(expected===1)windows.push(['known_history',26155960,26155963]);
    for(const [name,start,end] of windows) {
      const v=await rpc(cfg.host,'eth_getLogs',[{address:cfg.bridge,fromBlock:'0x'+start.toString(16),toBlock:'0x'+end.toString(16),topics:['0x33409cca56f705a7bbed38b7db57cf3a63317f3c1b9a747bbfb3d3ecffa84f6f']}]);
      add(Object.assign({name:label+'.'+name,from_block:start,to_block:end},v.failure?{status:'WARN',failure:v.failure}:summarizeLogs(v.result,name!=='recent')));
      if(events && name==='known_history' && Array.isArray(v.result) && v.result.length>0 && v.result.length<=500) events.push(v.result[0]);
    }
  }
  const blockTag=head?'0x'+Number(head).toString(16):'latest';
  const call=async(target,data)=>rpc(cfg.host,'eth_call',[{to:target,data},blockTag]);
  for(const field of ['bridge','federation','multiSig','allowTokens','erc777Converter']) {
    const target=addr(cfg[field]);if(!target){add({name:label+'.code.'+field,status:'WARN',failure:'CONFIG_ADDRESS'});continue;}
    const v=await rpc(cfg.host,'eth_getCode',[target,blockTag]);
    add({name:label+'.code.'+field,status:typeof v.result==='string'&&/^0x[0-9a-f]+$/i.test(v.result)&&v.result!=='0x0'?'PASS':'FAIL',
         bytecode_bytes:typeof v.result==='string'?Math.max(0,(v.result.length-2)/2):null,failure:v.failure||null});
  }
  const fed=await call(cfg.bridge,SELECT.federation),actual=wordAddress(fed.result);
  add({name:label+'.federation_mapping',status:actual===addr(cfg.federation)?'PASS':'FAIL',actual,configured:addr(cfg.federation),failure:fed.failure||null});
  if(actual!==addr(cfg.federation))return;
  const members=await call(actual,SELECT.members),required=await call(actual,SELECT.required);
  const list=memberList(members.result),r=uintWord(required.result);
  for(const [kind,target] of [['bridge',cfg.bridge],['federation',actual]]) {
    const owner=await call(target,SELECT.owner),ownerAddress=wordAddress(owner.result);
    const matches=ownerAddress!==null && ownerAddress===addr(cfg.multiSig);
    add({name:label+'.owner.'+kind,status:matches?'PASS':'WARN',owner:ownerAddress,matches_multisig:matches,failure:owner.failure||null});
  }
  const good=list && Number.isSafeInteger(r)&&r>0&&r<=list.length;
  const gate=good?Math.max(r,Math.floor(list.length/2)+1)-1:null;
  add({name:label+'.members_and_gate',status:!good?'FAIL':minimum!==gate || !signer || !list.includes(signer)?'WARN':'PASS',member_count:list?list.length:null,members:list,
       required:r,other_signature_gate:gate,configured_other_peer_gate:minimum,configured_signer_is_member:list&&signer?list.includes(signer):null,
       signer_notice:'configured public label, not proof of running signing key'});
  if(signer)for(const [method,tag] of [['eth_getBalance','latest'],['eth_getTransactionCount','latest'],['eth_getTransactionCount','pending']]) {
    const v=await rpc(cfg.host,method,[signer,tag]);add({name:label+'.signer.'+method+'.'+tag,status:validQuantity(v.result)!==null?'PASS':'WARN',value:validQuantity(v.result),failure:v.failure||null});
  }
}
async function signatureReadBoundary(chains,event,add) {
  if(!event || !chains.side || !chains.main) {
    add({name:'signature_request_read',status:'SKIP',failure:'KNOWN_EVENT_UNAVAILABLE'});return;
  }
  try {
    const lib=require(require.resolve('ethers',{paths:[APP]})).ethers;
    const ba=JSON.parse(file('/app/abis/Bridge.json')),fa=JSON.parse(file('/app/abis/Federation.json'));
    const source=new lib.utils.Interface(ba.abi||ba),destination=new lib.utils.Interface(fa.abi||fa);
    if(addr(event.address)!==addr(chains.side.bridge)||event.removed===true)throw Error('EVENT');
    const decoded=source.parseLog(event);if(decoded.name!=='Cross')throw Error('EVENT');
    const e=decoded.args;
    const arguments_=[e._tokenAddress,e._to,e._amount,e._symbol,event.blockHash,event.transactionHash,
                      Number(BigInt(event.logIndex)),e._decimals,e._granularity,e._userData];
    const data=destination.encodeFunctionData('getTransactionIdU',arguments_);
    const value=await rpc(chains.main.host,'eth_call',[{to:chains.main.federation,data},'latest']);
    add({name:'signature_request_read',status:typeof value.result==='string'&&/^0x[0-9a-f]{64}$/i.test(value.result)?'PASS':'WARN',
         failure:value.failure||null,notice:'read boundary only; no signing, vote, settlement or broadcast'});
    for(const method of ['eth_getTransactionByHash','eth_getTransactionReceipt']) {
      const v=await rpc(chains.side.host,method,[event.transactionHash]);
      const hash=v.result&&(method==='eth_getTransactionByHash'?v.result.hash:v.result.transactionHash);
      add({name:'source_history.'+method,status:hash===event.transactionHash?'PASS':'WARN',failure:v.failure||null});
    }
  }catch(e){add({name:'signature_request_read',status:'SKIP',failure:'ABI_EVENT_OR_VERSION_UNAVAILABLE'});}
}
function membershipSummary(checks) {
  const main=checks.find(x=>x.name==='main.members_and_gate'),side=checks.find(x=>x.name==='side.members_and_gate');
  if(!main || !side || !Array.isArray(main.members)||!Array.isArray(side.members))
    return {name:'cross_chain_members',status:'WARN',same_members:null,failure:'MEMBERS_UNAVAILABLE'};
  const equal=JSON.stringify(main.members.slice().sort())===JSON.stringify(side.members.slice().sort());
  return {name:'cross_chain_members',status:equal?'PASS':'WARN',same_members:equal};
}
async function mainProbe(profile,versionsOnly,out={versions:versions(),checks:[]}) {const add=v=>out.checks.push(v);
  if(versionsOnly)return out;
  out.resources=resources();
  let settings;try{settings=readPublic(profile);}catch(e){add({name:'public_config',status:'FAIL',failure:'STATIC_CONFIG_UNAVAILABLE'});return out;}
  out.configured_signer=settings.signer;out.signer_notice='public configuration label; signing key is never read';
  const jobs=[],chains={},events=[];
  for(const [label,name,chain] of [['main',settings.main_json,30],['side',settings.side_json,PROFILE[profile].chain]]) {
    try {
      const c=JSON.parse(file(CFG+'/'+name));
      if(addr(c.bridge)!==(label==='main'?PROFILE[profile].rsk:PROFILE[profile].bridge))throw Error('PROFILE');
      chains[label]=c;
      const saved=out.resources.checkpoints[label==='main'?'lastBlock.txt':'side-fed/lastBlock.txt'];
      jobs.push(()=>chainChecks(label,c,chain,settings.signer,settings.minimum_peers,add,saved,events));
    }catch(e){add({name:label+'.config',status:'FAIL',failure:'JSON_OR_PROFILE_ADDRESS'});}
  }
  jobs.push(async()=>{
    try {
      const text=comments(file(CFG+'/peers.config.js'));
      const json=text.replace(/^\s*module\.exports\s*=\s*/,'').replace(/;\s*$/,'').replace(/,\s*([}\]])/g,'$1');
      const peers=JSON.parse(json).peers;
      if(!Array.isArray(peers)||peers.length>100)throw Error('PEERS');
      out.configured_peer_count=peers.length;
      for(let i=0;i<peers.length;i++){
        const p=peers[i];if(typeof p.ip!=='string'||p.ip.length>253||!Number.isInteger(p.port)||p.port<1||p.port>65535){add({name:'p2p.dns.'+i,status:'WARN',failure:'TARGET_CONFIG'});continue;}
        add(Object.assign({name:'p2p.dns.'+i,address:addr(p.address),port:p.port,connect:'SKIP'},await resolveDNS(p.ip)));
      }
    }catch(e){add({name:'p2p.config',status:'WARN',failure:'STATIC_PEERS_UNAVAILABLE'});}
  });
  if(profile==='eth-rsk')jobs.push(async()=>{
    let key;try{key=file(CFG+'/etherscan.key',1024).trim();}catch(e){}
    if(signingScalarShape(key)) {
      add({name:'etherscan.v1',status:'SKIP',failure:'CREDENTIAL_SHAPE_REJECTED'});
      add({name:'etherscan.v2',status:'FAIL',failure:'CREDENTIAL_SHAPE_REJECTED'});return;
    }
    const legacy=oracleResponse(await request('https://api.etherscan.io/api?module=gastracker&action=gasoracle'));
    if(legacy.failure)legacy.status='WARN';
    if(legacy.deprecated && out.versions.gas_strategy==='v2_present')legacy.status='WARN';
    add(Object.assign({name:'etherscan.v1',notice:'retired endpoint; compare embedded gas strategy'},legacy));
    if(!key){add({name:'etherscan.v2',status:'SKIP',failure:'API_KEY_UNAVAILABLE'});return;}
    const value=await request('https://api.etherscan.io/v2/api?chainid=1&module=gastracker&action=gasoracle&apikey='+encodeURIComponent(key));
    add(Object.assign({name:'etherscan.v2'},oracleResponse(value)));
  });
  else add({name:'etherscan',status:'SKIP',notice:'non-ETH profile'});
  // At most three jobs at a time, two RPC dependencies run concurrently; each request has an absolute deadline.
  let cursor=0;await Promise.all(Array.from({length:Math.min(3,jobs.length)},async()=>{
    while(cursor<jobs.length){const job=jobs[cursor++];try{await job();}catch(e){add({name:'probe',status:'WARN',failure:'PROBE_SHAPE_OR_UNAVAILABLE'});}}
  }));
  add(membershipSummary(out.checks));
  if(profile==='eth-rsk')await signatureReadBoundary(chains,events[0],add);
  else add({name:'signature_request_read',status:'SKIP',notice:'known event check is ETH-specific'});
  return out;
}
'''
NODE_ENTRY = r'''
const profile=process.argv[2];
const versionsOnly=process.argv.includes('--versions-only');
const budgetIndex=process.argv.indexOf('--budget-ms');
const supplied=budgetIndex<0?45000:Number(process.argv[budgetIndex+1]);
const budget=Number.isInteger(supplied)&&supplied>=1&&supplied<=45000?supplied:100;
let ended=false;const partial={versions:versions(),checks:[]};
function finish(out) {
  if(ended)return;ended=true;clearTimeout(timer);
  // Flush the bounded report, then exit this diagnostic child, including pending DNS handles.
  const forced=setTimeout(()=>process.exit(0),500);forced.unref();
  process.stdout.write(JSON.stringify(out)+'\n',()=>{clearTimeout(forced);process.exit(0);});
}
const timer=setTimeout(()=>{partial.checks.push({name:'runtime',status:'WARN',failure:'WALL_DEADLINE'});finish(partial);},budget);
mainProbe(profile,versionsOnly,partial).then(finish)
.catch(()=>{partial.checks.push({name:'runtime',status:'WARN',failure:'UNAVAILABLE'});finish(partial);});

'''

if __name__ == '__main__':
    try:
        sys.exit(main())
    except DiagnosticError:
        print('Diagnosis failed safely; raw command/configuration output withheld.', file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('Diagnosis interrupted; no service actions were performed.', file=sys.stderr)
        sys.exit(130)
