#!/usr/bin/env python3
"""Interactive ETH upgrade wizard with automatic checks and a pinned approved handoff."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
import types
import urllib.request
from urllib.parse import urlsplit

VERSION = '1.3.1'
APP_REVISION = 'ba94a39855c97c81345c6dc5c3b835a9ffa7f900'
APP_IMAGE = ('sovryn/fed-tokenbridge:eth-repair-' + APP_REVISION +
             '@sha256:c479986db984be7cefd865e2f71dd0cec43128c83e61ae65ec5f2e2ddcc0fc44')
BASE_IMAGE_ID = 'sha256:eb153b412d54517818953f45990a8a5c8cf552d64e881410134a6c406a0c785c'
APP_IMAGE_ID = 'sha256:359c86c374970d1f8d6f803eb597e6713fa11695e6b3a3b7bf1ebd4503354bf4'
TOOL_REVISION = 'daf296389a0539ca477e37f8d2de1aaaaedd8474'
BRANCH = 'federator-diagnostics-recovery-upgrade'
ENVIRONMENT_SHA256 = '1dec671b46f00db14dfa4aaf1073bebbbbf9784d0a45418ede6c2f891469e9c9'
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
COMPOSE_URL = 'https://github.com/docker/compose/releases/download/v2.40.3/docker-compose-linux-x86_64'
COMPOSE_SHA256 = 'dba9d98e1ba5bfe11d88c99b9bd32fc4a0624a30fafe68eea34d61a3e42fd372'


class LaunchError(Exception):
    pass


def refuse(reason):
    raise LaunchError(reason + '. Keep existing services running. No automatic upgrade was started; '
                      'send only this error to the release coordinator for a matching deployment plan.')


def environment(config):
    result = {}
    for item in config.get('Env') or []:
        if not isinstance(item, str) or '=' not in item:
            refuse('Unrecognized container environment')
        key, value = item.split('=', 1)
        if key in result:
            refuse('Duplicate container environment name')
        result[key] = value
    return result


def make_override(container, image, repo, issues=None):
    """Accept the reviewed default deployment only; never silently drop custom settings."""
    findings = []
    def block(reason):
        findings.append(reason)
    cfg = str(Path(repo) / 'federator-env/mainnet-ETH-RSK')
    if (container.get('Image') != BASE_IMAGE_ID or image.get('Id') != BASE_IMAGE_ID or
            image.get('Os') != 'linux' or image.get('Architecture') != 'amd64'):
        observed = container.get('Image')
        observed = observed if isinstance(observed,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',observed) else 'unavailable'
        block('Image compatibility failed: installed '+observed+'; supported baseline '+BASE_IMAGE_ID+'; Linux amd64 required')
    if container.get('State', {}).get('Status') not in ('running', 'exited'):
        block('An incomplete earlier upgrade or unsupported container state needs attention')
    current, original = container['Config'], image['Config']
    if current.get('User') not in ('node', '1000', '1000:1000'):
        block('Container user is outside the UID1000 deployment profile')
    if any(current.get(k) != original.get(k) for k in ('Entrypoint', 'Cmd', 'WorkingDir', 'StopSignal')):
        block('Custom application startup is configured')
    # ArgsEscaped is Windows-only image metadata; Linux container inspect may omit it.
    if any(v is not None and type(v) is not bool
           for v in (current.get('ArgsEscaped'), original.get('ArgsEscaped'))):
        block('Unrecognized ArgsEscaped metadata (values withheld)')
    config_runtime = {'ArgsEscaped','Hostname','Domainname','User','Env','Labels','Image','AttachStdin',
                      'AttachStdout','AttachStderr','ExposedPorts','Volumes'}
    for key in sorted(current.keys() | original.keys()):
        if key not in config_runtime and current.get(key) != original.get(key) and (current.get(key) or original.get(key)):
            field = key if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key) else 'unrecognized field'
            block('Custom image/container configuration is present (' + field + '; values withheld)')
    if current.get('AttachStdin'):
        block('Custom attached standard input is configured')
    if not set(current.get('ExposedPorts') or {}).issubset(set(original.get('ExposedPorts') or {}) | {'30303/tcp'}):
        block('Custom exposed container ports are configured')
    if not set(current.get('Volumes') or {}).issubset({'/app/federator/config','/app/federator/db'}):
        block('Custom image volume declarations are configured')
    try:
        actual, baseline = environment(current), environment(original)
    except LaunchError:
        block('Malformed container environment (values withheld)')
        actual, baseline = {}, {}
    changed = {k for k in actual.keys() | baseline.keys() if k != 'TZ' and actual.get(k) != baseline.get(k)}
    if changed or actual.get('TZ') not in (None, 'UTC'):
        block('Custom application environment is configured (values withheld)')
    if current.get('Tty') or current.get('OpenStdin') or current.get('StdinOnce'):
        block('Custom interactive container startup is configured')
    if current.get('Domainname') or current.get('Hostname') not in (None, '', container['Id'][:12]):
        block('Custom container hostname is configured')
    mounts = container.get('Mounts') or []
    expected = {'/app/federator/config': cfg, '/app/federator/db': cfg + '/db'}
    if (len(mounts) != 2 or {m.get('Destination'): m.get('Source') for m in mounts} != expected or
            any(m.get('Type') != 'bind' or not m.get('RW') or
                m.get('Propagation', 'rprivate') not in ('', 'rprivate') for m in mounts)):
        block('Existing config/database mounts do not match the selected ETH checkout')
    labels = current.get('Labels') or {}
    project = labels.get('com.docker.compose.project', '')
    if (not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', project) or
            labels.get('com.docker.compose.service') != 'federation'):
        block('Container is outside a supported Compose federation project')
    extra_labels = {k:v for k,v in labels.items() if not k.startswith('com.docker.compose.')
                    and v != (original.get('Labels') or {}).get(k)}
    if any(not isinstance(v,str) or '$' in v or k.startswith('org.opencontainers.image.') for k,v in extra_labels.items()):
        block('Custom discovery labels require a reviewed literal-value deployment')
    host = container['HostConfig']
    ports = host.get('PortBindings') or {}
    bindings = ports.get('30303/tcp') or []
    if (set(ports) != {'30303/tcp'} or len(bindings) != 1 or
            bindings[0].get('HostPort') != '4444' or bindings[0].get('HostIp', '') not in ('', '0.0.0.0')):
        block('Custom peer port bindings are configured')
    network = project + '_default'
    if (host.get('NetworkMode') != network or
            set(container.get('NetworkSettings', {}).get('Networks') or {}) != {network}):
        block('Custom application networking is configured')
    endpoint = (container.get('NetworkSettings', {}).get('Networks') or {}).get(network, {})
    automatic_aliases = {container['Id'][:12], 'federation', 'bridge-sc_federation_1'}
    if endpoint.get('IPAMConfig') or endpoint.get('DriverOpts') or endpoint.get('Links'):
        block('Static network addressing or custom endpoint settings are configured')
    if any(not set(endpoint.get(k) or []).issubset(automatic_aliases) for k in ('Aliases','DNSNames')):
        block('Custom network aliases are configured')
    dynamic_endpoint = {'Aliases','DNSNames','NetworkID','EndpointID','Gateway','IPAddress',
                        'IPPrefixLen','IPv6Gateway','GlobalIPv6Address','GlobalIPv6PrefixLen','MacAddress'}
    if any(v and k not in dynamic_endpoint for k,v in endpoint.items()):
        block('Unsupported nonempty network endpoint settings are configured')
    policy = host.get('RestartPolicy') or {}
    if policy.get('Name', '') not in ('', 'no') or policy.get('MaximumRetryCount', 0) != 0:
        block('A custom restart policy is configured')
    zero_fields = ('Memory', 'MemoryReservation', 'MemorySwap', 'NanoCpus', 'CpuShares',
                   'CpuPeriod', 'CpuQuota', 'CpusetCpus', 'CpusetMems', 'BlkioWeight',
                   'OomKillDisable', 'OomScoreAdj', 'PublishAllPorts', 'Privileged',
                   'ReadonlyRootfs', 'AutoRemove', 'Init', 'PidMode', 'UTSMode', 'UsernsMode',
                   'Dns', 'DnsOptions', 'DnsSearch', 'ExtraHosts', 'Links', 'VolumesFrom',
                   'CapAdd', 'CapDrop', 'Devices', 'DeviceRequests', 'SecurityOpt', 'Sysctls',
                   'Ulimits', 'Tmpfs', 'StorageOpt', 'CgroupParent', 'GroupAdd')
    nondefault = [k for k in zero_fields if host.get(k) not in (None, False, 0, '', [], {})]
    if nondefault:
        block('Custom application limits, privileges or host settings are configured: ' + ', '.join(nondefault))
    runtime_bad = []
    if host.get('PidsLimit') not in (None, 0, -1):runtime_bad.append('PidsLimit')
    if host.get('MemorySwappiness') is not None:runtime_bad.append('MemorySwappiness')
    if host.get('ShmSize', 67108864) != 67108864:runtime_bad.append('ShmSize')
    if host.get('Runtime', 'runc') not in ('', 'runc'):runtime_bad.append('Runtime')
    if host.get('IpcMode', 'private') not in ('', 'private', 'shareable'):runtime_bad.append('IpcMode')
    if runtime_bad:block('Custom process/runtime limits are configured: ' + ', '.join(runtime_bad))
    # Docker20.10 default OCI protections, checked against moby/v20.10.5/oci/defaults.go.
    protections = {
        'MaskedPaths': {'/proc/asound','/proc/acpi','/proc/kcore','/proc/keys','/proc/latency_stats',
                        '/proc/timer_list','/proc/timer_stats','/proc/sched_debug','/proc/scsi','/sys/firmware'},
        'ReadonlyPaths': {'/proc/bus','/proc/fs','/proc/irq','/proc/sys','/proc/sysrq-trigger'}}
    for key, expected_paths in protections.items():
        if host.get(key) is not None and set(host[key]) != expected_paths:
            block('Custom process filesystem protections are configured')
    binds = host.get('Binds')
    if binds:
        allowed_binds = {source+':'+target for target,source in expected.items()}
        normalized = {str(Path(b.split(':')[0]))+':'+str(Path(b.split(':')[1]))
                      for b in binds if len(b.split(':')) in (2,3) and
                      (len(b.split(':'))==2 or b.split(':')[2]=='rw')}
        if len(normalized) != 2 or len(binds) != 2 or normalized != allowed_binds:
            block('Custom bind mount options are configured')
    if host.get('CgroupnsMode') not in (None,'','host','private'):
        block('Unsupported cgroup namespace mode is configured')
    handled_host = set(zero_fields) | set(protections) | {
        'Binds','PortBindings','NetworkMode','RestartPolicy','PidsLimit','MemorySwappiness',
        'ShmSize','Runtime','IpcMode','LogConfig','CgroupnsMode','ConsoleSize','Isolation'}
    if host.get('ConsoleSize', [0,0]) not in (None, [], [0,0]) or host.get('Isolation') not in (None,'','default'):
        block('Custom terminal or process isolation settings are configured')
    if any(v for k,v in host.items() if k not in handled_host):
        block('Unsupported nonempty Docker host settings are configured')
    if set((host.get('LogConfig') or {}).get('Config') or {}) - {'max-size','max-file'}:
        block('Custom local logging options are configured')
    if host.get('LogConfig', {}).get('Type', '') not in ('', 'json-file'):
        block('A different local log driver is configured')
    result = {'services': {'federation': {
        'image': APP_IMAGE, 'container_name': 'bridge-sc_federation_1', 'user': '1000:1000',
        'restart': 'no', 'environment': {'TZ': 'UTC'},
        'ipc': host.get('IpcMode') or 'private',
        'volumes': [{'type': 'bind', 'source': source, 'target': target}
                    for target, source in expected.items()],
        'logging': {'driver': 'json-file', 'options': {'max-size': '20m', 'max-file': '5'}}}}}
    if extra_labels:result['services']['federation']['labels'] = extra_labels
    if host.get('CgroupnsMode'):result['services']['federation']['cgroup'] = host['CgroupnsMode']
    if findings:
        if issues is not None:
            issues.extend(findings)
            return None
        refuse('Deployment audit found ' + str(len(findings)) + ' blockers:\n- ' + '\n- '.join(findings))
    return result


def environment_component():
    path=Path(__file__).resolve().with_name('federator_environment.py')
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as source:
            info=os.fstat(source.fileno());raw=source.read(256*1024+1)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (os.getuid(),0) or
                info.st_mode&0o022 or hashlib.sha256(raw).hexdigest()!=ENVIRONMENT_SHA256):
            raise ValueError()
    except (OSError,ValueError):
        raise LaunchError('Verified environment component missing or changed. Use the complete reviewed download block; services unchanged.') from None
    module=types.ModuleType('federator_environment');module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def capture_snapshot(repo,runner,operator,container,image,previous_run=None):
    component=environment_component()
    report=component.collect(repo,runner,operator,container,image,previous_run,progress=lambda message:print(message,flush=True))
    issues=[]
    try:
        if container.get('Image')!=APP_IMAGE_ID or image.get('Id')!=APP_IMAGE_ID:
            make_override(container,image,repo,issues=issues)
    except (KeyError,TypeError,ValueError,AttributeError):
        issues.append('Deployment shape could not be fully audited; use the complete packet for review')
    report['checks']=[{'status':'BLOCKER','summary':reason} for reason in issues]
    if not issues:report['checks'].append({'status':'PASS','summary':'Existing deployment matches the supported replacement profile' if container.get('Image')!=APP_IMAGE_ID else 'Approved application image already installed; no replacement required'})
    agent=report.get('agent',{})
    state=agent.get('deployment',{}).get('State',{})
    if agent.get('status')=='OBSERVED' and (state.get('Running') is not True or state.get('Paused')):
        finding={'status':'BLOCKER','summary':'Datadog Agent is not running or is paused; preserve its saved checkpoint before a matched recovery'}
        if state.get('Status')=='exited' and state.get('Running') is False and not state.get('Paused'):
            finding['recovery']='stopped_agent'
        report['checks'].append(finding)
    collection=agent.get('collection') or {}
    if agent.get('status')=='OBSERVED' and not collection:
        report['checks'].append({'status':'UNKNOWN','summary':'Datadog credential validity and logging checkpoint were not captured; metadata inspection is not delivery proof'})
    version=collection.get('version')
    legacy_image='sha256:4b37339b169c666008e4717eebc7f529329656f9ed13619f1d54d40a85adeeb8'
    legacy_supported=version=='7.32.4' and agent.get('deployment',{}).get('Image')==legacy_image
    if isinstance(version,str) and re.fullmatch(r'7\.\d+\.\d+',version) and int(version.split('.')[1])<33 and not legacy_supported:
        report['checks'].append({'status':'BLOCKER','summary':'Datadog Agent '+version+' is older than the verified7.33+ repair; prepare its matched update from this packet'})
    for field,title in [('api_key_present','Datadog API credential is absent'),('logs_enabled','Datadog log collection is disabled')]:
        if collection.get(field) is False:report['checks'].append({'status':'BLOCKER','summary':title})
    schema=collection.get('registry_schema')
    if schema is not None and schema!=2:report['checks'].append({'status':'BLOCKER','summary':'Datadog logging registry schema is unsupported'})
    for key,title in [('docker','Docker metadata'),('agent','Datadog metadata'),('application_probe','Application versions and RPC metadata')]:
        if report.get(key,{}).get('status')=='UNAVAILABLE':report['checks'].append({'status':'UNKNOWN','summary':title+' could not be captured'})
    if report.get('source_consistency',{}).get('status')=='CHANGED':
        report['checks'].append({'status':'BLOCKER','summary':'Source process changed during collection; this packet is not a stable deployment profile'})
    configuration=report.get('configuration',{})
    if configuration.get('config_status')!='OBSERVED':report['checks'].append({'status':'UNKNOWN','summary':'Static public configuration could not be captured'})
    if not report.get('docker',{}).get('compose_version'):
        report['checks'].append({'status':'SETUP','summary':'Docker Compose v2 is missing or unavailable; the verified installer is available after profile review'})
    configured=configuration.get('configured_signer')
    rpc=report.get('application_probe',{}).get('rpc',{})
    observed_members=[]
    for label,chain_id in (('ethereum','0x1'),('rootstock','0x1e')):
        values=rpc.get(label,{})
        if values.get('status')=='OBSERVED':
            if values.get('chainId')!=chain_id:
                report['checks'].append({'status':'BLOCKER','summary':label+' RPC did not return the expected chain identity'})
            members=values.get('members');required=values.get('required')
            if members and required:
                observed_members.append(sorted(x.lower() for x in members))
                gate=max(required,len(members)//2+1)-1
                if gate!=configuration.get('minimumPeerAmount'):
                    report['checks'].append({'status':'BLOCKER','summary':label+' Federation quorum disagrees with the configured peer gate'})
                if configured and configured.lower() not in [x.lower() for x in members]:
                    report['checks'].append({'status':'BLOCKER','summary':label+' configured public signer is not a Federation member'})
            settings=configuration.get('chains',{}).get(label,{})
            if values.get('bridgeFederation') and settings.get('federation') and values['bridgeFederation'].lower()!=settings['federation'].lower():
                report['checks'].append({'status':'BLOCKER','summary':label+' Bridge points at a different Federation than the configured one'})
    if len(observed_members)==2 and observed_members[0]!=observed_members[1]:
        report['checks'].append({'status':'BLOCKER','summary':'Ethereum and Rootstock Federation member sets differ'})
    for name,info in configuration.get('key_files',{}).items():
        if info.get('present') and (info.get('symlink') or not info.get('regular')):
            report['checks'].append({'status':'BLOCKER','summary':name+' is not a supported regular credential file; contents were not read'})
    if not configuration.get('key_files',{}).get('federator.key',{}).get('present'):
        report['checks'].append({'status':'INFO','summary':'Temporary signing file absent; expected for a running node, original custody remains required for restart'})
    report['status']='BLOCKED' if any(c['status']=='BLOCKER' for c in report['checks']) else 'CAPTURED_NOT_UPGRADE_APPROVAL'
    return report


def same_process(before, after):
    for key in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts', 'NetworkSettings'):
        left,right=before.get(key),after.get(key)
        if key=='Mounts':
            canonical=lambda values:sorted(json.dumps(v,sort_keys=True) for v in values or [])
            left,right=canonical(left),canonical(right)
        if left != right:
            refuse('Container identity or deployment changed during preparation')
    for key in ('Status', 'StartedAt'):
        if before['State'].get(key) != after['State'].get(key):
            refuse('Application process changed during preparation')


def write_private(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(body);out.flush();os.fsync(out.fileno())


class Runner:
    def run(self, args, timeout=20):
        try:
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise LaunchError('Required ' + args[0] + ' operation unavailable or timed out; services unchanged.') from None
        if result.returncode:
            raise LaunchError('Required ' + args[0] + ' operation failed; services unchanged. '
                              'Retry once connectivity/access is restored; raw output withheld.')
        if len(result.stdout) > 8 * 1024 * 1024:
            raise LaunchError('Operation output exceeded the preparation bound; services unchanged.')
        return result.stdout.decode('utf8')


def inspect_one(runner, args):
    value = json.loads(runner.run(DOCKER + args))
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise LaunchError('Docker inspection did not identify exactly one object; services unchanged.')
    return value[0]


def private_base():
    base = Path.home() / '.local/share/bridge-ops'
    parent = Path.home()
    for name in ('.local', 'share', 'bridge-ops'):
        parent = parent / name
        if parent.is_symlink():
            raise LaunchError('Symlink in private operations path; services unchanged.')
        parent.mkdir(mode=0o700, exist_ok=True)
    if base.stat().st_uid != os.getuid():
        raise LaunchError('Private operations directory has another owner; services unchanged.')
    base.chmod(0o700)
    return base


class OfficialReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if (target.scheme != 'https' or target.hostname not in ('github.com', 'release-assets.githubusercontent.com') or
                target.port not in (None, 443) or target.username or target.password):
            raise LaunchError('Compose download redirected outside the official release hosts.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def install_compose():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise LaunchError('The optional Compose installer supports only Linux amd64.')
    config = Path(os.environ.get('DOCKER_CONFIG') or str(Path.home()/'.docker')).expanduser().absolute()
    for part in (config,) + tuple(config.parents):
        if part.is_symlink():raise LaunchError('Symlink in effective Docker configuration path; nothing installed.')
    config.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = config/'cli-plugins'
    for path in (config, parent):
        if path.is_symlink():raise LaunchError('Symlink in user Compose plugin path; nothing installed.')
        path.mkdir(mode=0o700, exist_ok=True)
        if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o022:
            raise LaunchError('Compose plugin path must be owned and not writable by other accounts.')
    target = parent/'docker-compose'
    if target.exists() or target.is_symlink():
        raise LaunchError('User Compose plugin already exists; it was not overwritten. Have the host administrator repair its installation.')
    fd, temp = tempfile.mkstemp(prefix='.compose-download-', dir=parent)
    digest = hashlib.sha256();size = 0;deadline = time.monotonic()+240
    try:
        with os.fdopen(fd, 'wb') as out:
            with urllib.request.build_opener(OfficialReleaseRedirect()).open(COMPOSE_URL, timeout=20) as response:
                while True:
                    chunk = response.read(1024*1024)
                    if not chunk:break
                    size += len(chunk)
                    if size > 100*1024*1024 or time.monotonic() > deadline:
                        raise LaunchError('Compose download exceeded its bounds; no plugin installed.')
                    digest.update(chunk);out.write(chunk)
            out.flush();os.fsync(out.fileno())
        if digest.hexdigest() != COMPOSE_SHA256:
            raise LaunchError('Compose checksum mismatch; no plugin installed.')
        os.chmod(temp, 0o755)
        installed = os.stat(temp, follow_symlinks=False)
        os.link(temp, target, follow_symlinks=False)
        try:Runner().run(DOCKER+['compose','version'])
        except LaunchError:
            try:observed = target.lstat()
            except FileNotFoundError:observed = None
            if observed is not None and (observed.st_dev,observed.st_ino) == (installed.st_dev,installed.st_ino):target.unlink()
            raise LaunchError("Docker could not load the verified Compose plugin; only this attempt's unchanged file was removed. "
                              'Existing services are unchanged; have the host administrator check Docker CLI compatibility.') from None
    finally:
        os.unlink(temp)
    print('Verified Compose v2.40.3 installed in your account; Docker services were not restarted.', flush=True)


def upgrade_command(packet, repo, operator, signer, manual):
    args = ['/bin/bash', str(packet/'upgrade.sh'), '--repo', str(repo), '--revision', TOOL_REVISION, '--app-revision', APP_REVISION,
            '--image', APP_IMAGE, '--override', str(packet/'override.json'),
            '--operator', operator, '--expected-signer', signer]
    if manual:args.append('--no-aws-secrets')
    return args


def require_operator():
    if os.getuid() != 1000 or os.geteuid() != 1000:
        raise LaunchError('Log in as ubuntu UID1000 (sudo -iu ubuntu from root), then repeat the command.')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64','amd64'):
        raise LaunchError('Run this launcher on the native Linux amd64 federator host.')


def step(number, title):
    print('['+str(number)+'/4] '+title, flush=True)


def prompted_value(prompt, supplied, valid, error, interactive, default=None):
    if supplied is not None and valid(supplied):
        return supplied
    if not interactive:
        raise LaunchError(error+' Provide the corresponding option or run in an interactive terminal.')
    if supplied is not None:
        print(error, flush=True)
    while True:
        try:value = input(prompt).strip()
        except EOFError:
            raise LaunchError('Terminal input ended. No upgrade started.') from None
        if not value and default is not None:value = default
        if valid(value):return value
        print(error, flush=True)


def main(argv=None, runner=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Run without options for the interactive wizard. Missing identity and key-custody inputs '
        'are requested with validation. --prepare-only never opens the upgrader. '
        '--upgrade skips only the launcher decision; the approved maintenance confirmation remains. '
        '--version prints the launcher version without accessing Docker.'))
    parser.add_argument('--version', action='version', version='eth-upgrade-launcher '+VERSION)
    parser.add_argument('--repo', type=Path, default=Path.home()/'Bridge-SC')
    parser.add_argument('--operator', help='anonymous node label fed_1..fed_5; prompted if missing')
    parser.add_argument('--expected-signer', help='existing public federator address; prompted if missing')
    custody = parser.add_mutually_exclusive_group()
    custody.add_argument('--no-aws-secrets', dest='key_source', action='store_const', const='manual',
                         help='manual original-key custody; hidden key input in the approved upgrader')
    custody.add_argument('--aws-secrets', dest='key_source', action='store_const', const='aws',
                         help='restore the original AWS secret')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--upgrade', action='store_true', help='open approved upgrader after checks without a launcher decision prompt')
    mode.add_argument('--prepare-only', action='store_true', help='check and prepare files only; never open the approved upgrader')
    mode.add_argument('--collect-only', action='store_true', help='collect one sanitized environment packet; no signer/custody prompts and no upgrade')
    mode.add_argument('--replay-environment', type=Path, help='audit a collected environment JSON offline; no Docker/network or service changes')
    parser.add_argument('--previous-run', type=Path, help='include a sanitized original container from a saved private upgrade run')
    mode.add_argument('--install-compose', action='store_true', help='install pinned user Compose plugin only')
    args = parser.parse_args(argv)
    if args.replay_environment:
        component=environment_component()
        try:
            report=component.load_replay(args.replay_environment)
            deployments=[('current',report['deployment'])]
            if isinstance(report.get('previous_deployment'),dict) and 'container' in report['previous_deployment']:
                deployments.append(('original',report['previous_deployment']))
            blocked=False
            for label,data in deployments:
                issues=[];make_override(data['container'],data['image'],Path(data['repo']),issues=issues)
                print(label+': '+str(len(issues))+' deployment blockers')
                for issue in issues:print('- '+issue)
                blocked=blocked or bool(issues)
            print('Offline deployment replay only; no Docker, network, signing or captured command was executed.')
            return 1 if blocked else 0
        except (component.EnvironmentError,OSError,ValueError,KeyError,TypeError,AttributeError,RecursionError):
            raise LaunchError('Replay packet malformed or unavailable; no captured command was executed.') from None
    require_operator()
    if args.install_compose:
        print('Installing and verifying the pinned user Compose plugin; services remain unchanged.',flush=True)
        install_compose();return 0
    interactive = sys.stdin.isatty()
    if args.upgrade and not interactive:
        raise LaunchError('Run the command directly in interactive Bash; do not pipe it or use yes.')
    step(1,'Identify this node for read-only environment capture' if args.collect_only else 'Identify this node and signing-key custody')
    args.operator = prompted_value('Node label (fed_1..fed_5): ',args.operator,
        lambda value: bool(re.fullmatch(r'fed_[1-5]',value)),
        'Enter a node label from fed_1 through fed_5.',interactive)
    if not args.collect_only:
        args.expected_signer = prompted_value('Existing PUBLIC federator address (0x..., not a private key): ',args.expected_signer,
            lambda value: bool(re.fullmatch(r'0x[0-9a-fA-F]{40}',value)),
            'Enter a public address: 0x followed by exactly 40 hexadecimal characters.',interactive)
        if args.key_source is None and not interactive:
            args.key_source = 'aws'
        args.key_source = prompted_value('Original signing-key custody [aws/manual] (default aws): ',args.key_source,
            lambda value: value in ('aws','manual'),
            'Enter aws for your original AWS secret, or manual for private key entry.',interactive,default='aws')
    step(2,'Check account, repository and upgrade lock')
    runner = runner or Runner();repo = args.repo.absolute()
    origin = runner.run(['git','-C',str(repo),'remote','get-url','origin']).strip()
    if origin not in ('https://github.com/DistributedCollective/Bridge-SC',
                      'https://github.com/DistributedCollective/Bridge-SC.git',
                      'git@github.com:DistributedCollective/Bridge-SC',
                      'git@github.com:DistributedCollective/Bridge-SC.git',
                      'ssh://git@github.com/DistributedCollective/Bridge-SC.git'):
        raise LaunchError('Use the approved Bridge-SC checkout; services unchanged.')
    base = private_base()
    fd = os.open(base/'eth-upgrade.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid():
            raise LaunchError('Upgrade lock is not an owned regular file; services unchanged.')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise LaunchError('Another upgrade holds the lock. If it is only at the launcher decision or missing-override input prompt, '
                              'decline or press Ctrl+C there, then repeat this command. If service changes already started, '
                              'keep that run and send its last phase to the coordinator.') from None
        step(3,'Audit deployment and prepare the approved package; services remain unchanged')
        c,image={},{}
        try:
            c = inspect_one(runner,['inspect','bridge-sc_federation_1'])
            image = inspect_one(runner,['image','inspect',c['Image']])
        except (LaunchError,KeyError):
            print('Docker deployment metadata unavailable; collecting remaining host evidence without service changes.',flush=True)
        report=capture_snapshot(repo,runner,args.operator,c,image,args.previous_run)
        component=environment_component()
        capture_dir=Path(tempfile.mkdtemp(prefix='environment.',dir=base));capture_dir.chmod(0o700)
        bundle=component.write_bundle(report,capture_dir)
        print(component.summary(report),flush=True)
        print('Environment packet: '+str(bundle),flush=True)
        if args.collect_only:
            step(4,'Environment captured; no upgrade started. Send only the ZIP packet to your coordinator')
            return 0
        if any(check.get('status')=='BLOCKER' and check.get('recovery')!='stopped_agent' for check in report['checks']):
            raise LaunchError('All detected deployment blockers are listed above. Services unchanged. Send only '+str(bundle)+'; do not rerun the upgrade or send raw configuration.')
        if c['Image'] == APP_IMAGE_ID and image.get('Id') == APP_IMAGE_ID:
            if any(check.get('status')=='BLOCKER' for check in report['checks']):
                raise LaunchError('Application image is already approved but Datadog still requires recovery; no application replacement or restart performed. Send the saved environment packet.')
            step(4,'Approved application image is already installed; no upgrade or restart performed');return 0
        override = make_override(c,image,repo)
        try:runner.run(DOCKER+['compose','version'])
        except LaunchError:
            if args.prepare_only or not interactive:
                command = 'python3 '+shlex.quote(str(Path(__file__).resolve()))+' --install-compose'
                raise LaunchError('Docker Compose v2 is missing/unusable. Run: '+command+
                                  '\nThen repeat the same upgrade command. Neither service was changed.') from None
            answer=prompted_value('Install the verified Compose plugin in your account now? [y/N] ',None,
                lambda value:value.lower() in ('','y','yes','n','no'), 'Enter y or n.',True)
            if answer.lower() not in ('y','yes'):
                print('No plugin installed and no upgrade started; services unchanged.',flush=True);return 0
            print('Installing the verified Compose plugin; services remain unchanged.',flush=True)
            install_compose()
            runner.run(DOCKER+['compose','version'])
        print('Fetching and verifying the pinned upgrade tools; no service is stopped.',flush=True)
        runner.run(['git','-C',str(repo),'fetch','--no-tags','origin',BRANCH],timeout=180)
        runner.run(['git','-C',str(repo),'merge-base','--is-ancestor',TOOL_REVISION,'FETCH_HEAD'])
        script = runner.run(['git','-C',str(repo),'show',TOOL_REVISION+':tools/upgrade-eth-federator.sh']).encode()
        packet = Path(tempfile.mkdtemp(prefix='auto-eth-upgrade.',dir=base));packet.chmod(0o700)
        write_private(packet/'upgrade.sh',script)
        blob = runner.run(['git','-C',str(repo),'hash-object',str(packet/'upgrade.sh')]).strip()
        expected = runner.run(['git','-C',str(repo),'rev-parse',TOOL_REVISION+':tools/upgrade-eth-federator.sh']).strip()
        if not re.fullmatch(r'[0-9a-f]{40}',expected) or blob != expected:raise LaunchError('Approved upgrade script verification failed; services unchanged.')
        same_process(c,inspect_one(runner,['inspect','bridge-sc_federation_1']))
        write_private(packet/'override.json',(json.dumps(override,indent=2)+'\n').encode())
        print('Host checks passed. Compose override prepared automatically: '+str(packet/'override.json'),flush=True)
        step(4,'Preparation complete')
        if args.prepare_only or (not args.upgrade and not interactive):
            print('Preparation only; no service stopped and no upgrade started.',flush=True);return 0
        if not args.upgrade:
            answer = prompted_value('Open the approved upgrade now? [y/N] ',None,
                lambda value: value.lower() in ('','y','yes','n','no'),
                'Enter y to open the approved upgrader, or n to finish without upgrading.',True)
            if answer.lower() not in ('y','yes'):
                print('No upgrade started. Prepared files are kept in '+str(packet),flush=True);return 0
        # A pause at the decision prompt must not authorize a changed process.
        same_process(c,inspect_one(runner,['inspect','bridge-sc_federation_1']))
    finally:
        os.close(fd)
    print('Starting approved upgrade. Answer y to the upgrade-window prompt only when you are ready; '
          'it handles backup, key restoration, restart and monitoring.',flush=True)
    command = upgrade_command(packet,repo,args.operator,args.expected_signer,args.key_source == 'manual')
    os.execv(command[0],command)
    return 0


if __name__ == '__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:
        print('Cancelled. If the approved upgrader had already started, use its last printed phase and private run directory.',file=sys.stderr);sys.exit(130)
    except (LaunchError,OSError,ValueError,KeyError,TypeError) as exc:
        message = str(exc) if isinstance(exc,LaunchError) else 'Preparation failed; services unchanged. Raw configuration withheld.'
        print(message,file=sys.stderr);sys.exit(1)
