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
import urllib.request
from urllib.parse import urlsplit

VERSION = '1.1.1'
APP_REVISION = 'ba94a39855c97c81345c6dc5c3b835a9ffa7f900'
APP_IMAGE = ('sovryn/fed-tokenbridge:eth-repair-' + APP_REVISION +
             '@sha256:c479986db984be7cefd865e2f71dd0cec43128c83e61ae65ec5f2e2ddcc0fc44')
BASE_IMAGE_ID = 'sha256:eb153b412d54517818953f45990a8a5c8cf552d64e881410134a6c406a0c785c'
APP_IMAGE_ID = 'sha256:359c86c374970d1f8d6f803eb597e6713fa11695e6b3a3b7bf1ebd4503354bf4'
BRANCH = 'federator-diagnostics-recovery-upgrade'
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


def make_override(container, image, repo):
    """Accept the reviewed default deployment only; never silently drop custom settings."""
    cfg = str(Path(repo) / 'federator-env/mainnet-ETH-RSK')
    if (container.get('Image') != BASE_IMAGE_ID or image.get('Id') != BASE_IMAGE_ID or
            image.get('Os') != 'linux' or image.get('Architecture') != 'amd64'):
        observed = container.get('Image')
        observed = observed if isinstance(observed,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',observed) else 'unavailable'
        refuse('Image compatibility failed: installed '+observed+'; supported baseline '+BASE_IMAGE_ID+'; Linux amd64 required')
    if container.get('State', {}).get('Status') not in ('running', 'exited'):
        refuse('An incomplete earlier upgrade or unsupported container state needs attention')
    current, original = container['Config'], image['Config']
    if current.get('User') not in ('node', '1000', '1000:1000'):
        refuse('Container user is outside the UID1000 deployment profile')
    if any(current.get(k) != original.get(k) for k in ('Entrypoint', 'Cmd', 'WorkingDir', 'StopSignal')):
        refuse('Custom application startup is configured')
    # ArgsEscaped is Windows-only image metadata; Linux container inspect may omit it.
    if any(v is not None and type(v) is not bool
           for v in (current.get('ArgsEscaped'), original.get('ArgsEscaped'))):
        refuse('Unrecognized ArgsEscaped metadata (values withheld)')
    config_runtime = {'ArgsEscaped','Hostname','Domainname','User','Env','Labels','Image','AttachStdin',
                      'AttachStdout','AttachStderr','ExposedPorts','Volumes'}
    for key in sorted(current.keys() | original.keys()):
        if key not in config_runtime and current.get(key) != original.get(key) and (current.get(key) or original.get(key)):
            field = key if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key) else 'unrecognized field'
            refuse('Custom image/container configuration is present (' + field + '; values withheld)')
    if current.get('AttachStdin'):
        refuse('Custom attached standard input is configured')
    if not set(current.get('ExposedPorts') or {}).issubset(set(original.get('ExposedPorts') or {}) | {'30303/tcp'}):
        refuse('Custom exposed container ports are configured')
    if not set(current.get('Volumes') or {}).issubset({'/app/federator/config','/app/federator/db'}):
        refuse('Custom image volume declarations are configured')
    actual, baseline = environment(current), environment(original)
    changed = {k for k in actual.keys() | baseline.keys() if k != 'TZ' and actual.get(k) != baseline.get(k)}
    if changed or actual.get('TZ') not in (None, 'UTC'):
        refuse('Custom application environment is configured (values withheld)')
    if current.get('Tty') or current.get('OpenStdin') or current.get('StdinOnce'):
        refuse('Custom interactive container startup is configured')
    if current.get('Domainname') or current.get('Hostname') not in (None, '', container['Id'][:12]):
        refuse('Custom container hostname is configured')
    mounts = container.get('Mounts') or []
    expected = {'/app/federator/config': cfg, '/app/federator/db': cfg + '/db'}
    if (len(mounts) != 2 or {m.get('Destination'): m.get('Source') for m in mounts} != expected or
            any(m.get('Type') != 'bind' or not m.get('RW') or
                m.get('Propagation', 'rprivate') not in ('', 'rprivate') for m in mounts)):
        refuse('Existing config/database mounts do not match the selected ETH checkout')
    labels = current.get('Labels') or {}
    project = labels.get('com.docker.compose.project', '')
    if (not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', project) or
            labels.get('com.docker.compose.service') != 'federation'):
        refuse('Container is outside a supported Compose federation project')
    extra_labels = {k:v for k,v in labels.items() if not k.startswith('com.docker.compose.')
                    and v != (original.get('Labels') or {}).get(k)}
    if any(not isinstance(v,str) or '$' in v or k.startswith('org.opencontainers.image.') for k,v in extra_labels.items()):
        refuse('Custom discovery labels require a reviewed literal-value deployment')
    host = container['HostConfig']
    ports = host.get('PortBindings') or {}
    bindings = ports.get('30303/tcp') or []
    if (set(ports) != {'30303/tcp'} or len(bindings) != 1 or
            bindings[0].get('HostPort') != '4444' or bindings[0].get('HostIp', '') not in ('', '0.0.0.0')):
        refuse('Custom peer port bindings are configured')
    network = project + '_default'
    if (host.get('NetworkMode') != network or
            set(container.get('NetworkSettings', {}).get('Networks') or {}) != {network}):
        refuse('Custom application networking is configured')
    endpoint = container['NetworkSettings']['Networks'][network]
    automatic_aliases = {container['Id'][:12], 'federation', 'bridge-sc_federation_1'}
    if endpoint.get('IPAMConfig') or endpoint.get('DriverOpts') or endpoint.get('Links'):
        refuse('Static network addressing or custom endpoint settings are configured')
    if any(not set(endpoint.get(k) or []).issubset(automatic_aliases) for k in ('Aliases','DNSNames')):
        refuse('Custom network aliases are configured')
    dynamic_endpoint = {'Aliases','DNSNames','NetworkID','EndpointID','Gateway','IPAddress',
                        'IPPrefixLen','IPv6Gateway','GlobalIPv6Address','GlobalIPv6PrefixLen','MacAddress'}
    if any(v and k not in dynamic_endpoint for k,v in endpoint.items()):
        refuse('Unsupported nonempty network endpoint settings are configured')
    policy = host.get('RestartPolicy') or {}
    if policy.get('Name', '') not in ('', 'no') or policy.get('MaximumRetryCount', 0) != 0:
        refuse('A custom restart policy is configured')
    zero_fields = ('Memory', 'MemoryReservation', 'MemorySwap', 'NanoCpus', 'CpuShares',
                   'CpuPeriod', 'CpuQuota', 'CpusetCpus', 'CpusetMems', 'BlkioWeight',
                   'OomKillDisable', 'OomScoreAdj', 'PublishAllPorts', 'Privileged',
                   'ReadonlyRootfs', 'AutoRemove', 'Init', 'PidMode', 'UTSMode', 'UsernsMode',
                   'Dns', 'DnsOptions', 'DnsSearch', 'ExtraHosts', 'Links', 'VolumesFrom',
                   'CapAdd', 'CapDrop', 'Devices', 'DeviceRequests', 'SecurityOpt', 'Sysctls',
                   'Ulimits', 'Tmpfs', 'StorageOpt', 'CgroupParent', 'GroupAdd')
    if any(host.get(k) not in (None, False, 0, '', [], {}) for k in zero_fields):
        refuse('Custom application limits, privileges or host settings are configured')
    if (host.get('PidsLimit') not in (None, 0, -1) or host.get('MemorySwappiness') is not None or
            host.get('ShmSize', 67108864) != 67108864 or
            host.get('Runtime', 'runc') not in ('', 'runc') or
            host.get('IpcMode', 'private') not in ('', 'private')):
        refuse('Custom process/runtime limits are configured')
    # Docker20.10 default OCI protections, checked against moby/v20.10.5/oci/defaults.go.
    protections = {
        'MaskedPaths': {'/proc/asound','/proc/acpi','/proc/kcore','/proc/keys','/proc/latency_stats',
                        '/proc/timer_list','/proc/timer_stats','/proc/sched_debug','/proc/scsi','/sys/firmware'},
        'ReadonlyPaths': {'/proc/bus','/proc/fs','/proc/irq','/proc/sys','/proc/sysrq-trigger'}}
    for key, expected_paths in protections.items():
        if host.get(key) is not None and set(host[key]) != expected_paths:
            refuse('Custom process filesystem protections are configured')
    binds = host.get('Binds')
    if binds:
        allowed_binds = {source+':'+target for target,source in expected.items()}
        normalized = {str(Path(b.split(':')[0]))+':'+str(Path(b.split(':')[1]))
                      for b in binds if len(b.split(':')) in (2,3) and
                      (len(b.split(':'))==2 or b.split(':')[2]=='rw')}
        if len(normalized) != 2 or len(binds) != 2 or normalized != allowed_binds:
            refuse('Custom bind mount options are configured')
    if host.get('CgroupnsMode') not in (None,'','host','private'):
        refuse('Unsupported cgroup namespace mode is configured')
    handled_host = set(zero_fields) | set(protections) | {
        'Binds','PortBindings','NetworkMode','RestartPolicy','PidsLimit','MemorySwappiness',
        'ShmSize','Runtime','IpcMode','LogConfig','CgroupnsMode','ConsoleSize','Isolation'}
    if host.get('ConsoleSize', [0,0]) not in (None, [], [0,0]) or host.get('Isolation') not in (None,'','default'):
        refuse('Custom terminal or process isolation settings are configured')
    if any(v for k,v in host.items() if k not in handled_host):
        refuse('Unsupported nonempty Docker host settings are configured')
    if set((host.get('LogConfig') or {}).get('Config') or {}) - {'max-size','max-file'}:
        refuse('Custom local logging options are configured')
    if host.get('LogConfig', {}).get('Type', '') not in ('', 'json-file'):
        refuse('A different local log driver is configured')
    result = {'services': {'federation': {
        'image': APP_IMAGE, 'container_name': 'bridge-sc_federation_1', 'user': '1000:1000',
        'restart': 'no', 'environment': {'TZ': 'UTC'},
        'volumes': [{'type': 'bind', 'source': source, 'target': target}
                    for target, source in expected.items()],
        'logging': {'driver': 'json-file', 'options': {'max-size': '20m', 'max-file': '5'}}}}}
    if extra_labels:result['services']['federation']['labels'] = extra_labels
    if host.get('CgroupnsMode'):result['services']['federation']['cgroup'] = host['CgroupnsMode']
    return result


def same_process(before, after):
    for key in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts', 'NetworkSettings'):
        if before.get(key) != after.get(key):
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
    args = ['/bin/bash', str(packet/'upgrade.sh'), '--repo', str(repo), '--revision', APP_REVISION,
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
    mode.add_argument('--install-compose', action='store_true', help='install pinned user Compose plugin only')
    args = parser.parse_args(argv)
    require_operator()
    if args.install_compose:
        print('Installing and verifying the pinned user Compose plugin; services remain unchanged.',flush=True)
        install_compose();return 0
    interactive = sys.stdin.isatty()
    if args.upgrade and not interactive:
        raise LaunchError('Run the command directly in interactive Bash; do not pipe it or use yes.')
    step(1,'Identify this node and signing-key custody')
    args.operator = prompted_value('Node label (fed_1..fed_5): ',args.operator,
        lambda value: bool(re.fullmatch(r'fed_[1-5]',value)),
        'Enter a node label from fed_1 through fed_5.',interactive)
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
        c = inspect_one(runner,['inspect','bridge-sc_federation_1'])
        image = inspect_one(runner,['image','inspect',c['Image']])
        if c['Image'] == APP_IMAGE_ID and image.get('Id') == APP_IMAGE_ID:
            step(4,'Approved application image is already installed; no upgrade or restart performed');return 0
        override = make_override(c,image,repo)
        try:runner.run(DOCKER+['compose','version'])
        except LaunchError:
            command = 'python3 '+shlex.quote(str(Path(__file__).resolve()))+' --install-compose'
            raise LaunchError('Docker Compose v2 is missing/unusable. Run: '+command+
                              '\nThen repeat the same upgrade command. Neither service was changed.') from None
        print('Fetching and verifying the pinned upgrade tools; no service is stopped.',flush=True)
        runner.run(['git','-C',str(repo),'fetch','--no-tags','origin',BRANCH],timeout=180)
        runner.run(['git','-C',str(repo),'merge-base','--is-ancestor',APP_REVISION,'FETCH_HEAD'])
        script = runner.run(['git','-C',str(repo),'show',APP_REVISION+':tools/upgrade-eth-federator.sh']).encode()
        packet = Path(tempfile.mkdtemp(prefix='auto-eth-upgrade.',dir=base));packet.chmod(0o700)
        write_private(packet/'upgrade.sh',script)
        blob = runner.run(['git','-C',str(repo),'hash-object',str(packet/'upgrade.sh')]).strip()
        expected = runner.run(['git','-C',str(repo),'rev-parse',APP_REVISION+':tools/upgrade-eth-federator.sh']).strip()
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
