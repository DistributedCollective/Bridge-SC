#!/usr/bin/env python3
"""Prepare/apply a stopped-Agent Docker-file log cutover; never restart the bridge."""
import argparse
import copy
import hashlib
import inspect
import io
import tarfile
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

VERSION = '1.0.6'
PERSISTENT_PATH = '/var/log/datadog/bridge-log-state'
AGENT_CONFIG = '/etc/datadog-agent/datadog.yaml'
DOCKER_CONFIG = '/etc/datadog-agent/datadog-docker.yaml'
MAX_BYTES = 8 * 1024 * 1024
LABEL = 'org.bridge.dd-recovery.owner'


class RepairError(Exception):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cutover_registry(registry, path, offset, when):
    if not isinstance(registry, dict) or type(registry.get('Version')) is not int or registry['Version'] != 2:
        raise RepairError('Unsupported Agent registry schema; no patch prepared')
    entries = registry.get('Registry')
    key = 'file:' + path
    if not isinstance(entries, dict) or not isinstance(entries.get(key), dict):
        raise RepairError('Exact Docker file source absent from registry; collection mode needs review')
    if entries[key].get('TailingMode') not in ('', 'beginning', 'end'):
        raise RepairError('Selected registry source has an unsupported tailing mode')
    old = entries[key].get('Offset')
    if not isinstance(old, str) or not re.fullmatch(r'[0-9]{1,19}', old):
        raise RepairError('Selected source does not have a numeric file offset')
    if type(offset) is not int or not 0 <= int(old) <= offset < 2**63:
        raise RepairError('Cutover would decrease progress or exceeds supported file bounds')
    result = copy.deepcopy(registry)
    result['Registry'][key]['Offset'] = str(offset)
    result['Registry'][key]['LastUpdated'] = when
    return result


def persistent_config(config, env):
    if not isinstance(config, dict):
        raise RepairError('Unsupported Agent configuration shape')
    result = copy.deepcopy(config)
    logs = result.get('logs_config') or {}
    if not isinstance(logs, dict):
        raise RepairError('Unsupported logs_config shape')
    if env.get('DD_CONF_PATH', '/etc/datadog-agent') != '/etc/datadog-agent' or env.get('DD_CONFIG_FILE', AGENT_CONFIG) != AGENT_CONFIG:
        raise RepairError('Custom Agent main-config location requires review')
    if config.get('confd_path', '/etc/datadog-agent/conf.d') != '/etc/datadog-agent/conf.d' or env.get('DD_CONFD_PATH', '/etc/datadog-agent/conf.d') != '/etc/datadog-agent/conf.d':
        raise RepairError('Custom integration configuration path requires review')
    if 'DD_LOGS_CONFIG_RUN_PATH' in env:
        raise RepairError('Immutable registry-path environment override requires a separate Agent deployment review')
    for key in ('docker_container_use_file', 'docker_container_force_use_file', 'k8s_container_use_kubelet_api'):
        if key in logs and type(logs[key]) is not bool:
            raise RepairError('Unsupported collector flag type')
    value = env.get('DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE')
    if value is not None and value.lower() not in ('true', 'false'):
        raise RepairError('Unsupported collector environment value')
    if env.get('DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE', '').lower() == 'false' or logs.get('docker_container_use_file') is False:
        raise RepairError('Socket collection selected; file-offset repair refused')
    logs['run_path'] = PERSISTENT_PATH
    result['logs_config'] = logs
    return result


def ensure_file_collection(registry, cid, config, env):
    logs = config.get('logs_config') or {}
    def effective(name, key):
        value = env.get(name)
        if value is not None:
            if value.lower() not in ('true', 'false'):
                raise RepairError('Unsupported collector environment value')
            return value.lower() == 'true'
        return logs.get(key) is True
    if effective('DD_LOGS_CONFIG_K8S_CONTAINER_USE_KUBELET_API', 'k8s_container_use_kubelet_api'):
        raise RepairError('Kubelet API collection is outside this Docker-file repair')
    entries = registry.get('Registry')
    if not isinstance(entries, dict):
        raise RepairError('Unsupported registry entries')
    entry = entries.get('docker:' + cid, {})
    if not isinstance(entry, dict):
        raise RepairError('Unsupported socket registry entry')
    if entry.get('Offset') and not effective('DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE', 'docker_container_force_use_file'):
        raise RepairError('Legacy socket cursor can override file collection; separate migration review required')


def tail_boundary(data, base):
    end = data.rfind(b'\n')
    if end < 0:
        raise RepairError('No complete Docker JSON record in bounded tail')
    begin = data.rfind(b'\n', 0, end) + 1
    if begin == 0 and base:
        raise RepairError('Last complete record exceeds bounded tail')
    try:
        row = json.loads(data[begin:end])
        stamp = row['time']
    except (ValueError, KeyError, UnicodeError):
        raise RepairError('Invalid complete Docker record') from None
    if not isinstance(stamp, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z', stamp):
        raise RepairError('Docker record timestamp is unsupported')
    return {'offset': base + end + 1, 'last_record_utc': stamp}


class Docker:
    def call(self, args, timeout=20, optional=False):
        command = ['docker', '--host', 'unix:///var/run/docker.sock'] + list(args)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        sel = selectors.DefaultSelector()
        buffers = {proc.stdout: bytearray(), proc.stderr: bytearray()}
        for stream in buffers:
            os.set_blocking(stream.fileno(), False)
            sel.register(stream, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout
        try:
            while sel.get_map():
                if time.monotonic() > deadline:
                    raise RepairError('Docker operation timed out; inspect the Agent state before retrying')
                for key, _ in sel.select(.1):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        sel.unregister(key.fileobj)
                    else:
                        buffers[key.fileobj].extend(chunk)
                        if sum(len(x) for x in buffers.values()) > MAX_BYTES:
                            raise RepairError('Docker output limit exceeded')
            code = proc.wait(timeout=max(.1, deadline - time.monotonic()))
            if code and not optional:
                raise RepairError('Docker operation failed (exit %s); raw output withheld' % code)
            return bytes(buffers[proc.stdout]) if not code else None
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            sel.close()
            for stream in buffers:
                stream.close()

    def inspect(self, name, agent=False):
        fields = {'id': '.Id', 'image': '.Image', 'state': '.State', 'mounts': '.Mounts', 'log_path': '.LogPath', 'log_config': '.HostConfig.LogConfig'}
        if agent:
            fields.update(env='.Config.Env', user='.Config.User', labels='.Config.Labels', command='.Config.Cmd', entrypoint='.Config.Entrypoint')
        else:
            fields.update(labels='.Config.Labels')
        fmt = '{' + ','.join(json.dumps(k) + ':{{json ' + v + '}}' for k, v in fields.items()) + '}'
        try:
            result = json.loads(self.call(['inspect', name, '--format', fmt]))
            if agent:
                raw_env = result.get('env') or []
                result['env_fingerprint'] = sha(json.dumps(raw_env).encode())
                allowed = {'DD_LOGS_ENABLED', 'DD_LOGS_CONFIG_RUN_PATH', 'DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE', 'DD_LOGS_CONFIG_DOCKER_CONTAINER_FORCE_USE_FILE', 'DD_LOGS_CONFIG_K8S_CONTAINER_USE_KUBELET_API', 'DD_CONF_PATH', 'DD_CONFIG_FILE', 'DD_CONFD_PATH', 'DD_CONFIG_PROVIDERS', 'DD_EXTRA_CONFIG_PROVIDERS'}
                result['env'] = [entry for entry in raw_env if entry.split('=', 1)[0] in allowed]
                result['api_key_present'] = any(entry.startswith('DD_API_KEY=') and entry != 'DD_API_KEY=' for entry in raw_env)
            else:
                result['labels'] = {k: v for k, v in (result.get('labels') or {}).items() if k.startswith('com.datadoghq.ad.')}
            return result
        except ValueError:
            raise RepairError('Restricted Docker inspection unavailable') from None

    def copy_out(self, cid, path, destination):
        if destination.is_symlink():
            raise RepairError('Symlink copy destination refused')
        raw = self.call(['cp', cid + ':' + path, '-'])
        try:
            with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive:
                members = archive.getmembers()
                if len(members) != 1 or not members[0].isfile() or not 0 <= members[0].size <= MAX_BYTES:
                    raise RepairError('Unexpected copied Agent file')
                data = archive.extractfile(members[0]).read(MAX_BYTES + 1)
        except (tarfile.TarError, OSError):
            raise RepairError('Invalid copied Agent archive') from None
        if len(data) > MAX_BYTES:
            raise RepairError('Copied Agent file exceeds limit')
        fd, name = tempfile.mkstemp(prefix='.copy-', dir=str(destination.parent))
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(data); out.flush(); os.fsync(out.fileno())
            if destination.is_symlink(): raise RepairError('Symlink copy destination refused')
            os.replace(name, str(destination))
        finally:
            if os.path.exists(name): os.unlink(name)
        return data

    def helper(self, image, code, mounts, user=None, read_search=False):
        token = secrets.token_hex(12)
        name = 'bridge-dd-read-' + token
        args = ['run', '--rm', '--pull=never', '--name', name, '--label', LABEL + '=' + token,
                '--network', 'none', '--read-only', '--log-driver', 'none', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', user or str(os.getuid()) + ':' + str(os.getgid()),
                '--entrypoint', '/opt/datadog-agent/embedded/bin/python']
        if read_search:
            args += ['--cap-add', 'DAC_READ_SEARCH']
        for mount in mounts:
            source, target = mount[:2]
            kind = mount[2] if len(mount) == 3 else 'bind'
            if kind not in ('bind', 'volume'):
                raise RepairError('Unsupported mount kind')
            if kind == 'volume' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', source):
                raise RepairError('Unsupported volume name')
            if ',' in source or ',' in target:
                raise RepairError('Unsupported bind path')
            args += ['--mount', 'type=' + kind + ',source=' + source + ',target=' + target + ',readonly']
        try:
            return self.call(args + [image, '-B', '-c', code], timeout=35)
        finally:
            check = self.call(['inspect', name, '--format', '{{index .Config.Labels "' + LABEL + '"}}'], optional=True)
            if check and check.decode().strip() == token:
                self.call(['rm', '-f', name], optional=True)


def scope(agent, source):
    if agent['state'].get('Running') or agent['state'].get('Paused') or agent['state'].get('Status') != 'exited':
        raise RepairError('Agent must be stopped, not Docker-paused; no change made')
    if not source['state'].get('Running') or source['state'].get('Paused'):
        raise RepairError('Expected the existing ETH federator running')
    return validate_layout(agent, source)


def validate_layout(agent, source):
    """Validate supported file/volume geometry without changing runtime state."""
    if agent.get('entrypoint') not in (None, [], ['/bin/entrypoint.sh']):
        raise RepairError('Custom Agent entrypoint requires review')
    if agent.get('command') not in (None, [], ['/bin/entrypoint.sh'], ['agent', 'run']):
        raise RepairError('Custom Agent launcher needs configuration-path review')
    if agent.get('user') not in ('', '0', 'root', '0:0', 'root:root'):
        raise RepairError('Custom non-root Agent requires permission review')
    cid = source['id']
    if not re.fullmatch('[0-9a-f]{64}', cid) or source['log_config'].get('Type') != 'json-file':
        raise RepairError('Only the verified Docker JSON-file source is supported')
    mounts = {m['Destination']: m for m in source['mounts']}
    cfg = mounts.get('/app/federator/config', {}).get('Source', '')
    if not cfg.endswith('/federator-env/mainnet-ETH-RSK') or mounts.get('/app/federator/db', {}).get('Source') != cfg + '/db':
        raise RepairError('Source is not the expected ETH deployment')
    source_path = source.get('log_path', '')
    suffix = '/containers/' + cid + '/' + cid + '-json.log'
    if not source_path.endswith(suffix):
        raise RepairError('Unexpected source log path')
    mapped = None
    volume = None
    for m in agent['mounts']:
        destination = m['Destination'].rstrip('/')
        if any(destination == path or path.startswith(destination + '/') for path in (AGENT_CONFIG, DOCKER_CONFIG)):
            raise RepairError('Mounted Agent main config requires a separate patch review')
        prefix = m.get('Source', '').rstrip('/')
        if m.get('Type') == 'bind' and prefix and source_path.startswith(prefix + '/'):
            candidate = m['Destination'].rstrip('/') + source_path[len(prefix):]
            if candidate.endswith(suffix):
                if mapped is not None:
                    raise RepairError('Ambiguous Agent log mounts')
                mapped = candidate
        if m['Destination'] == '/var/log/datadog' and m.get('Type') == 'volume' and m.get('RW'):
            volume = m.get('Name')
    if not mapped or not volume or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', volume):
        raise RepairError('Expected file mount and writable Agent log volume are unavailable')
    # Validate effective backing mounts, including nested shadow mounts.
    for target, backing in ((PERSISTENT_PATH, '/var/log/datadog'), (mapped, None)):
        covering = [m for m in agent['mounts'] if target == m['Destination'].rstrip('/') or target.startswith(m['Destination'].rstrip('/') + '/')]
        actual = max(covering, key=lambda m: len(m['Destination']))
        if backing and actual['Destination'] != backing:
            raise RepairError('Persistent destination is shadowed by another mount')
        if not backing and (actual.get('Type') != 'bind' or actual.get('Source', '').rstrip('/') + target[len(actual['Destination'].rstrip('/')):] != source_path):
            raise RepairError('Source log is shadowed by another mount')
        if any(m['Destination'].startswith(target.rstrip('/') + '/') for m in agent['mounts']):
            raise RepairError('Nested mount shadows the repair destination')
    return mapped, volume



def config_path(docker, agent):
    # Inspect the standard Docker-image alias without extracting/following links.
    import io
    import tarfile
    raw = docker.call(['cp', agent['id'] + ':' + AGENT_CONFIG, '-'])
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive:
            members = archive.getmembers()
            if len(members) == 1 and Path(members[0].name).name == 'datadog.yaml':
                row = members[0]
                if row.isfile():
                    return AGENT_CONFIG
                if row.issym() and row.linkname in (DOCKER_CONFIG, 'datadog-docker.yaml'):
                    return DOCKER_CONFIG
    except tarfile.TarError:
        pass
    raise RepairError('Main config is not a regular file or the standard Docker-image alias')


def safe_path(value, existing=False):
    raw = Path(value).expanduser()
    if '..' in raw.parts:
        raise RepairError('Parent components in output path refused')
    p = raw.absolute()
    for q in [p] + list(p.parents):
        if q.is_symlink():
            raise RepairError('Symlink output path refused')
    if existing:
        m = p.stat()
        if not p.is_dir() or m.st_uid != os.getuid() or stat.S_IMODE(m.st_mode) != 0o700:
            raise RepairError('Expected private operator-owned repair directory')
    return p



def ensure_output_outside_source(output, source):
    for mount in source['mounts']:
        path = mount.get('Source')
        if path and (str(output) == path or str(output).startswith(path.rstrip('/') + '/')):
            raise RepairError('Repair output must be outside every live application mount')


def ensure_registry_start_modes(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'start_position' and child not in ('beginning', 'end'):
                raise RepairError('Forced/unknown log start position can override registry; no patch applied')
            ensure_registry_start_modes(child)
    elif isinstance(value, list):
        for child in value:
            ensure_registry_start_modes(child)


def check_discovery(docker, agent, source, config, env, destination):
    # External configuration providers are outside this offline repair's scope.
    for key in ('config_providers', 'extra_config_providers'):
        if config.get(key):
            raise RepairError('Explicit configuration providers require separate collection review')
    if env.get('DD_CONFIG_PROVIDERS') or env.get('DD_EXTRA_CONFIG_PROVIDERS'):
        raise RepairError('Explicit configuration providers require separate collection review')
    ensure_registry_start_modes(config)
    for key, value in (source.get('labels') or {}).items():
        if key.endswith('.logs'):
            ensure_registry_start_modes(json.loads(value))
    raw = docker.call(['cp', agent['id'] + ':/etc/datadog-agent/conf.d', '-'])
    write_private_bytes(destination, raw)
    code = 'import json,tarfile,yaml\nclass RepairError(Exception): pass\n' + inspect.getsource(ensure_registry_start_modes) + r'''
checked=0
with tarfile.open('/discovery.tar','r:*') as archive:
 for item in archive:
  if item.name.endswith(('.yaml','.yml','.yaml.default','.yml.default')):
   if not item.isfile() or item.size > 8388608:
    raise RepairError('Unsupported integration configuration entry')
   ensure_registry_start_modes(yaml.safe_load(archive.extractfile(item)))
   checked+=1
print(json.dumps({'files_checked':checked}))
'''
    checked = json.loads(docker.helper(agent['image'], code, [(str(destination), '/discovery.tar')]))
    # Tar metadata (mtime) may vary; hash the config contents and member metadata.
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive:
        fingerprint = []
        for item in archive:
            if item.name.endswith(('.yaml', '.yml', '.yaml.default', '.yml.default')):
                if not item.isfile():
                    raise RepairError('Linked integration configuration refused')
                fingerprint.append((item.name, sha(archive.extractfile(item).read())))
    checked['sha256'] = sha(json.dumps(sorted(fingerprint)).encode())
    return checked


def read_json(path):
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > MAX_BYTES:
                raise RepairError('Unsafe private evidence file')
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES: raise RepairError('Private evidence exceeds limit')
        return json.loads(data)
    except (OSError, ValueError):
        raise RepairError('Private evidence unreadable, linked or invalid') from None


def write_private_bytes(path, data):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data); out.flush(); os.fsync(out.fileno())


def write_private(path, value):
    write_private_bytes(path, (json.dumps(value, indent=2) + '\n').encode())


def update_report(output, value):
    target = output / 'report.json'
    if target.is_symlink():
        raise RepairError('Symlink report destination refused')
    fd, name = tempfile.mkstemp(prefix='.report-', dir=str(output))
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(json.dumps(value, indent=2) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, str(target))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def file_snapshot(docker, agent, source):
    code = 'import json,os,re\nclass RepairError(Exception): pass\n' + inspect.getsource(tail_boundary) + '''
fd=os.open('/source.log',os.O_RDONLY)
try:
 s=os.fstat(fd);base=max(0,s.st_size-131072);os.lseek(fd,base,os.SEEK_SET)
 data=os.read(fd,s.st_size-base);result=tail_boundary(data,base)
 result.update(device=s.st_dev,inode=s.st_ino,size=s.st_size)
 print(json.dumps(result))
finally: os.close(fd)
'''
    # Docker JSON logs belong to root; this helper sees only the one read-only log.
    return json.loads(docker.helper(agent['image'], code, [(source['log_path'], '/source.log')], user='0:0'))


def ensure_same(old_agent, old_source, agent, source, running_agent=False):
    if running_agent:
        validate_layout(agent, source)
        if not agent['state'].get('Running') or agent['state'].get('Paused') or not source['state'].get('Running') or source['state'].get('Paused'):
            raise RepairError('Post-start Agent/source are not running')
    else:
        scope(agent, source)
    for old, new in ((old_agent, agent), (old_source, source)):
        for key in ('id', 'image', 'mounts', 'log_path', 'log_config'):
            left, right = old.get(key), new.get(key)
            if key == 'mounts':
                left = sorted(json.dumps(m, sort_keys=True) for m in (left or []))
                right = sorted(json.dumps(m, sort_keys=True) for m in (right or []))
            if left != right:
                raise RepairError('Container identity/layout changed (' + key + '); prepare again')
        if old['state'].get('StartedAt') != new['state'].get('StartedAt'):
            raise RepairError('Container process epoch changed; prepare again')
    if old_source.get('labels') != source.get('labels'):
        raise RepairError('Source discovery labels changed')
    if old_source['state']['StartedAt'] != source['state']['StartedAt']:
        raise RepairError('Federator process changed; no cutoff applied')
    if old_agent.get('env') != agent.get('env') or old_agent.get('env_fingerprint') != agent.get('env_fingerprint'):
        raise RepairError('Agent environment changed')


def prepare(docker, output):
    agent = docker.inspect('datadog-agent', agent=True)
    source = docker.inspect('bridge-sc_federation_1')
    mapped, volume = scope(agent, source)
    ensure_output_outside_source(output, source)
    output.mkdir(mode=0o700)
    update_report(output, {'version': VERSION, 'utc': utc(), 'outcome': 'preparation_in_progress', 'agent_id': agent['id'], 'source_id': source['id'], 'agent_image': agent['image']})
    effective_config = config_path(docker, agent)
    cfg_raw = docker.copy_out(agent['id'], effective_config, output / 'original-config.private.yaml')
    cfg_code = 'import json,yaml,subprocess;print(json.dumps({"config":yaml.safe_load(open("/input.yaml")),"version":subprocess.check_output(["agent","version"]).decode()}))'
    parsed = json.loads(docker.helper(agent['image'], cfg_code, [(str(output / 'original-config.private.yaml'), '/input.yaml')]))
    cfg = parsed['config']
    match = re.search(r'Agent 7\.(\d+)\.', parsed.get('version', ''))
    if not match or int(match[1]) < 33:
        raise RepairError('Expected Agent7.33+ file collector; installed version needs review')
    if not isinstance(cfg, dict):
        raise RepairError('Unsupported Agent configuration')
    env = dict(x.split('=', 1) for x in agent.get('env', []) if '=' in x)
    patched_config = persistent_config(cfg, env)
    discovery = check_discovery(docker, agent, source, cfg, env, output / 'discovery.private.tar')
    logs = cfg.get('logs_config') or {}
    run_path = logs.get('run_path') or '/opt/datadog-agent/run'
    if not isinstance(run_path, str) or not run_path.startswith('/') or '..' in Path(run_path).parts or run_path == PERSISTENT_PATH:
        raise RepairError('Registry path requires review or is already migrated')
    registry_path = run_path.rstrip('/') + '/registry.json'
    registry_raw = docker.copy_out(agent['id'], registry_path, output / 'original-registry.private.json')
    registry = json.loads(registry_raw)
    snapshot = file_snapshot(docker, agent, source)
    cutover_registry(registry, mapped, snapshot['offset'], utc())
    ensure_file_collection(registry, source['id'], cfg, env)
    # Private state may contain API credentials in the original YAML/environment.
    write_private(output / 'context.private.json', {'agent': agent, 'source': source, 'config_path': effective_config, 'mapped_path': mapped, 'log_volume': volume,
                  'old_registry_path': registry_path, 'config_sha256': sha(cfg_raw), 'registry_sha256': sha(registry_raw), 'config': patched_config, 'discovery_sha256': discovery['sha256']})
    report = {'version': VERSION, 'prepared_utc': utc(), 'outcome': 'prepared_agent_still_stopped',
              'source_id': source['id'], 'agent_id': agent['id'], 'agent_image': agent['image'], 'agent_version': parsed['version'].strip(), 'registry_version': registry['Version'],
              'registry_entries': len(registry['Registry']), 'source_log_bytes': snapshot['size'], 'preview_cutover': snapshot,
              'old_registry_path': registry_path, 'new_registry_path': PERSISTENT_PATH + '/registry.json',
              'cutover_note': 'Apply samples a fresh complete-record boundary; old monitoring logs remain local',
              'production_app_changed': False}
    update_report(output, report)
    print('Prepared; Agent remains stopped. Report:', output / 'report.json')
    print('For preparation-only runs, apply with: python3', shlex.quote(str(Path(__file__).resolve())), '--apply', shlex.quote(str(output)))
    return report


class DeliveryPending(RepairError):
    pass


def check_started_progress(docker, output, ctx):
    post = read_json(output / 'poststart.private.json')
    work = output / ('progress-' + secrets.token_hex(6))
    agent = docker.inspect('datadog-agent', agent=True)
    source = docker.inspect('bridge-sc_federation_1')
    ensure_output_outside_source(output, source)
    ensure_same(post['agent'], ctx['source'], agent, source, running_agent=True)
    work.mkdir(mode=0o700)
    mapped, volume = validate_layout(agent, source)
    if mapped != ctx['mapped_path'] or volume != ctx['log_volume']:
        raise RepairError('Post-start source/state-volume mapping changed')
    config = docker.copy_out(agent['id'], config_path(docker, agent), work / 'config.private.yaml')
    if sha(config) != post['config_sha256']:
        raise RepairError('Post-start Agent configuration changed')
    env = dict(x.split('=', 1) for x in agent.get('env', []) if '=' in x)
    discovery = check_discovery(docker, agent, source, ctx['config'], env, work / 'discovery.private.tar')
    if discovery['sha256'] != ctx['discovery_sha256']:
        raise RepairError('Post-start Agent integration configuration changed')
    cutoff = post['cutover']; deadline = time.monotonic() + 60
    while True:
        ensure_same(post['agent'], ctx['source'], docker.inspect('datadog-agent', agent=True),
                    docker.inspect('bridge-sc_federation_1'), running_agent=True)
        registry = json.loads(docker.copy_out(agent['id'], PERSISTENT_PATH + '/registry.json', work / 'registry.private.json'))
        snapshot = file_snapshot(docker, agent, source)
        if any(snapshot[k] != cutoff[k] for k in ('device', 'inode')) or snapshot['offset'] < cutoff['offset']:
            raise RepairError('Post-start source rotated/truncated; inspection required')
        cutover_registry(registry, mapped, snapshot['offset'], utc())
        ensure_file_collection(registry, source['id'], ctx['config'], env)
        observed = int(registry['Registry']['file:' + mapped]['Offset'])
        if observed < cutoff['offset']:
            raise RepairError('Post-start acknowledged checkpoint regressed')
        if observed > cutoff['offset'] or snapshot['offset'] == cutoff['offset']:
            break
        if time.monotonic() >= deadline:
            pending = {'version': VERSION, 'outcome': 'agent_running_delivery_unverified', 'utc': utc(),
                       'cutover_offset': cutoff['offset'], 'acknowledged_offset': observed,
                       'source_delivery': 'UNKNOWN', 'agent_left_running': True}
            update_report(work, pending); update_report(output, pending)
            raise DeliveryPending('Source activity is not yet acknowledged; Agent left running. Recheck the same packet with --apply')
        time.sleep(3)
    ensure_same(post['agent'], ctx['source'], docker.inspect('datadog-agent', agent=True),
                docker.inspect('bridge-sc_federation_1'), running_agent=True)
    advanced = observed > cutoff['offset']
    result = {'version': VERSION, 'outcome': 'agent_running_current_source_offset_advanced' if advanced else 'agent_running_source_idle',
              'cutover_utc': post['utc'], 'cutover_offset': cutoff['offset'], 'acknowledged_offset': observed,
              'last_skipped_docker_record_utc': cutoff['last_record_utc'], 'source_delivery': 'UNKNOWN',
              'agent_id': agent['id'], 'source_id': source['id'], 'new_registry_path': PERSISTENT_PATH + '/registry.json',
              'indexed_visibility': 'not independently verified', 'federator_restarted': False,
              'local_logs_deleted': False, 'resumed_prestart_attempt': post['resumed_prestart_attempt'],
              'attempt_directory': str(work), 'utc': utc()}
    update_report(work, result); update_report(output, result)
    print('Agent running; source checkpoint advanced.' if advanced else 'Agent running; source idle, delivery not verified.',
          'Report:', output / 'report.json')
    return result


def apply(docker, output):
    output = safe_path(output, existing=True)
    ctx = read_json(output / 'context.private.json')
    if (output / 'poststart.private.json').exists() or (output / 'poststart.private.json').is_symlink():
        return check_started_progress(docker, output, ctx)
    agent = docker.inspect('datadog-agent', agent=True)
    source = docker.inspect('bridge-sc_federation_1')
    ensure_output_outside_source(output, source)
    ensure_output_outside_source(output, ctx['source'])
    attempt = output / ('attempt-' + secrets.token_hex(6))
    attempt.mkdir(mode=0o700)
    phase = 'checking_prepared_state'
    attempted_start = False
    previous_report = {}

    def progress(value):
        nonlocal phase
        phase = value
        update_report(attempt, {'version': VERSION, 'utc': utc(), 'phase': value})

    try:
        progress(phase)
        previous_report = read_json(output / 'report.json')
        write_private(attempt / 'previous-report.json', previous_report)
        ctx = read_json(output / 'context.private.json')
        marker = output / 'apply-started.json'
        if marker.is_symlink():
            raise RepairError('Symlink attempt marker refused')
        retry = marker.exists()
        ensure_same(ctx['agent'], ctx['source'], agent, source)
        ensure_output_outside_source(output, source)
        mapped, volume = scope(agent, source)
        if mapped != ctx['mapped_path'] or volume != ctx['log_volume']:
            raise RepairError('Prepared source/volume mapping changed')
        effective_config = config_path(docker, agent)
        if effective_config != ctx.get('config_path', AGENT_CONFIG):
            raise RepairError('Agent config alias changed; inspect before proceeding')
        progress('validating_originals_and_installed_config')
        original = output / 'original-config.private.yaml'
        if original.is_symlink() or sha(original.read_bytes()) != ctx['config_sha256']:
            raise RepairError('Original config backup changed; no repair writes made')
        cfg_code = 'import json,yaml;print(json.dumps(yaml.safe_load(open("/input.yaml"))))'
        original_cfg = json.loads(docker.helper(agent['image'], cfg_code, [(str(original), '/input.yaml')]))
        env = dict(x.split('=', 1) for x in agent.get('env', []) if '=' in x)
        expected_config = persistent_config(original_cfg, env)
        old_path = (original_cfg.get('logs_config') or {}).get('run_path') or '/opt/datadog-agent/run'
        if old_path.rstrip('/') + '/registry.json' != ctx['old_registry_path'] or expected_config != ctx['config']:
            raise RepairError('Prepared config/path was modified; no repair writes made')
        current_cfg = docker.copy_out(agent['id'], effective_config, attempt / 'verified-config.private.yaml')
        is_original = sha(current_cfg) == ctx['config_sha256']
        try:
            is_patched = json.loads(current_cfg) == expected_config
        except (ValueError, UnicodeError):
            is_patched = False
        if not is_original and not (retry and is_patched):
            raise RepairError('Installed Agent config is neither original nor the journalled patch')
        discovery = check_discovery(docker, agent, source, original_cfg, env, attempt / 'verified-discovery.private.tar')
        if discovery['sha256'] != ctx['discovery_sha256']:
            raise RepairError('Agent integration configuration changed')
        current_reg = docker.copy_out(agent['id'], ctx['old_registry_path'], attempt / 'verified-registry.private.json')
        if sha(current_reg) != ctx['registry_sha256']:
            raise RepairError('Original stopped-Agent registry changed; no repair writes made')
        registry = json.loads(current_reg)
        ensure_file_collection(registry, source['id'], original_cfg, env)
        progress('validating_source_and_cutover')
        snapshot = file_snapshot(docker, agent, source)
        preview = read_json(output / 'report.json')['preview_cutover']
        if any(snapshot[x] != preview[x] for x in ('device', 'inode')) or snapshot['size'] < preview['size']:
            raise RepairError('Source log rotated/truncated; no repair writes made')
        if retry:
            journal = read_json(marker)
            cutoff, when = journal['cutover'], journal['utc']
            if any(cutoff[x] != snapshot[x] for x in ('device', 'inode')) or cutoff['offset'] > snapshot['size']:
                raise RepairError('Journalled source log identity/bounds changed')
        else:
            cutoff, when = snapshot, utc()
        patched_registry = cutover_registry(registry, mapped, cutoff['offset'], when)
        stage = attempt / 'bridge-log-state'; stage.mkdir(mode=0o700)
        write_private(stage / 'registry.json', patched_registry)
        write_private(attempt / 'patched-config.private.json', expected_config)
        service = (agent.get('labels') or {}).get('com.docker.compose.service', 'datadog')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', service):
            raise RepairError('Unsupported Compose service label')
        override = {'services': {service: {'environment': {'DD_LOGS_CONFIG_RUN_PATH': PERSISTENT_PATH},
                    'volumes': [{'type': 'volume', 'source': 'bridge_dd_state', 'target': '/var/log/datadog'}]}},
                    'volumes': {'bridge_dd_state': {'external': True, 'name': volume}}}
        write_private(attempt / 'future-agent-override.private.json', override)
        progress('reconciling_installed_registry')
        existing = json.loads(docker.helper(agent['image'], """import json,os,stat
p='/agent-logs/bridge-log-state';r=p+'/registry.json';regular=False
try:
 regular=not os.path.islink(p) and os.path.isdir(p) and not os.path.islink(r) and stat.S_ISREG(os.stat(r).st_mode) and os.stat(r).st_size <= 8388608
except OSError: pass
print(json.dumps({'exists':os.path.lexists(p),'regular':regular}))
""", [(volume, '/agent-logs', 'volume')], user='0:0', read_search=True))
        if existing.get('exists'):
            if not retry or existing.get('regular') is not True:
                raise RepairError('Persistent destination is unrecognised; no overwrite attempted')
            installed = docker.copy_out(agent['id'], PERSISTENT_PATH + '/registry.json', attempt / 'reconciled-registry.private.json')
            if json.loads(installed) != patched_registry:
                raise RepairError('Installed persistent registry is not the journalled patch; no overwrite attempted')
        ensure_same(ctx['agent'], ctx['source'], docker.inspect('datadog-agent', agent=True), docker.inspect('bridge-sc_federation_1'))
        if not retry:
            write_private(marker, {'utc': when, 'cutover': cutoff})
        if not existing.get('exists'):
            progress('copying_persistent_registry')
            docker.call(['cp', str(stage), agent['id'] + ':' + PERSISTENT_PATH])
        if config_path(docker, agent) != effective_config:
            raise RepairError('Agent config alias changed during staging')
        if not is_patched:
            progress('copying_agent_config')
            docker.call(['cp', str(attempt / 'patched-config.private.json'), agent['id'] + ':' + effective_config])
        progress('verifying_installed_files')
        check = docker.copy_out(agent['id'], PERSISTENT_PATH + '/registry.json', attempt / 'installed-registry.private.json')
        check_cfg = docker.copy_out(agent['id'], effective_config, attempt / 'installed-config.private.json')
        if json.loads(check) != patched_registry or json.loads(check_cfg) != expected_config:
            raise RepairError('Installed Agent files did not verify')
        ensure_same(ctx['agent'], ctx['source'], docker.inspect('datadog-agent', agent=True), docker.inspect('bridge-sc_federation_1'))
        latest = file_snapshot(docker, agent, source)
        if any(latest[x] != cutoff[x] for x in ('device', 'inode')) or latest['size'] < cutoff['offset']:
            raise RepairError('Source log changed during staging; Agent remains stopped')
        progress('starting_agent')
        attempted_start = True
        docker.call(['start', agent['id']])
        fresh = docker.inspect('datadog-agent', agent=True)
        expected = copy.deepcopy(agent)
        expected['state']['StartedAt'] = fresh['state'].get('StartedAt')
        ensure_same(expected, source, fresh, docker.inspect('bridge-sc_federation_1'), running_agent=True)
        write_private(output / 'poststart.private.json', {'agent': fresh, 'cutover': cutoff, 'utc': when,
                      'config_sha256': sha(check_cfg), 'resumed_prestart_attempt': retry})
        progress('waiting_for_acknowledged_source_progress')
        return check_started_progress(docker, output, ctx)

    except Exception as exc:
        if attempted_start and not isinstance(exc, DeliveryPending):
            try:
                docker.call(['stop', agent['id']], timeout=25, optional=True)
            except RepairError:
                pass
        actual = 'unknown'
        try:
            state = docker.inspect('datadog-agent', agent=True)
            if agent and state['id'] == agent['id']:
                actual = 'running' if state['state'].get('Running') else state['state'].get('Status', 'unknown')
        except RepairError:
            pass
        failure = {'utc': utc(), 'outcome': 'incomplete', 'phase': phase,
                   'failure': str(exc) if isinstance(exc, RepairError) else type(exc).__name__,
                   'observed_agent_state': actual, 'federator_changed_by_tool': False, 'attempt_directory': str(attempt)}
        write_private(attempt / 'failure.json', failure)
        update_report(attempt, failure)
        summary = dict(previous_report)
        summary.update(failure)
        try:
            update_report(output, summary)
        except (OSError, RepairError):
            pass
        print('Attempt evidence:', attempt / 'failure.json', file=sys.stderr)
        raise


def report_incomplete(docker, output, reason):
    try:
        output = safe_path(output, existing=True)
        ensure_output_outside_source(output, docker.inspect('bridge-sc_federation_1'))
        context = output / 'context.private.json'
        if context.is_file() and not context.is_symlink():
            ensure_output_outside_source(output, read_json(context)['source'])
        report = output / 'report.json'
        if report.is_symlink() or not report.is_file():
            return False
        partial = read_json(report)
        partial.update(outcome='incomplete', failure=reason, finished_utc=utc())
        update_report(output, partial)
        return True
    except (OSError, ValueError, TypeError, KeyError, RepairError):
        return False

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version='dd-agent-recovery ' + VERSION)
    p.add_argument('--repair', action='store_true', help='prepare backups, apply one current-end cutover, and resume only the Agent')
    p.add_argument('--apply', type=Path, help='apply or reconcile a stopped pre-start attempt from its private preparation directory')
    p.add_argument('--output-dir', type=Path, help='new private preparation directory')
    args = p.parse_args(argv)
    output = None
    try:
        if os.getuid() != 1000 or not sys.platform.startswith('linux'):
            raise RepairError('Run as the Linux deployment user UID1000, without sudo')
        if args.apply and (args.output_dir or args.repair):
            raise RepairError('Use preparation or apply, not both')
        docker = Docker()
        if args.apply:
            output = safe_path(args.apply, existing=True)
            apply(docker, output)
        else:
            output = safe_path(args.output_dir or (Path.home() / ('dd-agent-repair-' + secrets.token_hex(6))))
            if output.exists():
                raise RepairError('Preparation directory already exists')
            prepare(docker, output)
            if args.repair:
                apply(docker, output)
        return 0
    except (RepairError, OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.TimeoutExpired) as exc:
        # RepairError messages are fixed text; never print raw config/provider exception output.
        reason = str(exc) if isinstance(exc, RepairError) else type(exc).__name__
        if output and output.exists():
            report_incomplete(docker, output, reason)
        print('Agent repair incomplete: ' + reason, file=sys.stderr)
        print('Retain the private directory and inspect Agent state before retrying.', file=sys.stderr)
        if output:
            print('Evidence directory (if created):', output, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
