#!/usr/bin/env python3
"""Continue a verified ETH upgrade stopped before key restoration/container staging."""
import argparse
import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import termios


class ContinueError(Exception):
    pass


BOUNDARY = '\nif [[ -n "$ROLLBACK_RUN" ]]; then\n'
SUFFIX_MARKER = '# Verified continuation: no prepare/stop/archive steps are rerun.'
TOOLS = ('federator_recovery.py','federator_dependencies.py','federator_watcher.py',
         'etherscan_prerequisite.py','dd_agent_recovery.py','federator_datadog_upgrade.py',
         'federator_upgrade_safety.py')


def private_bytes(path):
    path = Path(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ContinueError('Private evidence file is unavailable or symlinked') from None
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ContinueError('Expected owned private regular evidence file')
        body = source.read(2*1024*1024+1)
        if len(body) > 2*1024*1024:
            raise ContinueError('Evidence exceeds bound')
        return body


def validate_context(c, revision, signer, home):
    fields = ('FED_REPO','REPAIR_REVISION','FED_IMAGE','RELEASE_OVERRIDE','PUBLIC_OPERATOR','EXPECTED_SIGNER',
              'KEY_SOURCE','COMPOSE_PROJECT','CONFIG_DIR','WATCH_SECONDS','COMPOSE_PLAN_SHA256')
    if any(not isinstance(c.get(k),str) or '\0' in c[k] for k in fields):
        raise ContinueError('Invalid saved context')
    repo = home/'Bridge-SC'
    if c['FED_REPO'] != str(repo) or c['CONFIG_DIR'] != str(repo/'federator-env/mainnet-ETH-RSK'):
        raise ContinueError('Unexpected saved repo/config mounts')
    if c['REPAIR_REVISION'] != revision or c['EXPECTED_SIGNER'].lower() != signer.lower():
        raise ContinueError('Saved revision/signer differs from supplied original release')
    if not re.fullmatch(r'sovryn/fed-tokenbridge:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}',c['FED_IMAGE']):
        raise ContinueError('Saved immutable image invalid')
    if not re.fullmatch(r'fed_[1-5]',c['PUBLIC_OPERATOR']) or c['KEY_SOURCE'] not in ('aws','manual'):
        raise ContinueError('Saved operator/key source invalid')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',c['COMPOSE_PROJECT']):
        raise ContinueError('Saved project invalid')
    if not re.fullmatch(r'[0-9a-f]{64}',c['COMPOSE_PLAN_SHA256']):
        raise ContinueError('Saved plan checksum invalid')
    if not c['WATCH_SECONDS'].isdigit() or not 1 <= int(c['WATCH_SECONDS']) <= 86400:
        raise ContinueError('Saved watcher duration invalid')


def verify_original_state(old, current, staged):
    if staged or current.get('running') is not False or any(current.get(k)!=old.get(k) for k in ('id','image_id','started')):
        raise ContinueError('Original container is not the same stopped, unstaged node')


def pre_resume_guard(run, context):
    sys.path.insert(0,str(run))
    import federator_recovery as r
    node = r.Node(Path(context['FED_REPO']),'eth-rsk','bridge-sc_federation_1')
    old = json.loads(private_bytes(run/'before.json'))
    verify_original_state(old,node.inspect(),(run/'replacement.json').exists())
    history = json.loads(private_bytes(run/'history/manifest.json'))
    if history['source_id']!=old['id'] or history['image_id']!=old['image_id']:
        raise ContinueError('History archive belongs to another source')
    for path in (run/'history/docker.log.gz',run/'rollback/old-image.tar'):
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size<=0:
            raise ContinueError('Verified archive missing or changed type/owner')
    if (run/'history/docker.log.gz.partial').exists():
        raise ContinueError('History archive is incomplete')
    if private_bytes(run/'rollback/old-image-id.txt').decode().strip()!=old['image_id']:
        raise ContinueError('Original image archive identity differs')
    names={'config.js','mainnet.json','rskmainnet.json','peers.config.js'}
    if set(history.get('config_sha256',{}))!=names:
        raise ContinueError('Configuration archive manifest incomplete')
    for name in names:
        if hashlib.sha256(private_bytes(run/'history'/name)).hexdigest()!=history['config_sha256'][name]:
            raise ContinueError('Archived configuration changed')
    expected=history.get('uncompressed_bytes')
    if type(expected) is not int or expected<0:
        raise ContinueError('Invalid log archive byte count')
    digest=hashlib.sha256();total=0
    fd=os.open(run/'history/docker.log.gz',os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as raw, gzip.GzipFile(fileobj=raw,mode='rb') as archive:
        for chunk in iter(lambda:archive.read(1024*1024),b''):
            total+=len(chunk)
            if total>expected:raise ContinueError('Log archive exceeds its verified size')
            digest.update(chunk)
    if total!=expected or digest.hexdigest()!=history.get('uncompressed_sha256'):
        raise ContinueError('Log archive no longer matches its verified manifest')


def resume_script(original):
    if original.count(BOUNDARY)!=1:
        raise ContinueError('Unsupported original upgrader entrypoint layout')
    prefix=original.split(BOUNDARY,1)[0]
    return prefix+'\n'+SUFFIX_MARKER+r'''
OPS_DIR=$RESUME_RUN
export OPS_DIR
step 'Verify this saved stopped-node attempt before continuing'
verify_bundle
python3 "$RESUME_TOOL" --guard --run "$OPS_DIR" --revision "$REPAIR_REVISION" --expected-signer "$EXPECTED_SIGNER"
test "$(sha256sum "$OPS_DIR/deployment.private.json" | cut -d ' ' -f 1)" = "$COMPOSE_PLAN_SHA256"
capture_current_state > "$RESUME_ATTEMPT/current-state.private.json"
python3 - <<'CHECK'
import json,os
from pathlib import Path
run=Path(os.environ['OPS_DIR']);attempt=Path(os.environ['RESUME_ATTEMPT'])
if json.loads((run/'stopped-state.json').read_text())!=json.loads((attempt/'current-state.private.json').read_text()):
 raise SystemExit('Config/checkpoints changed since stop; continuation refused')
CHECK
(cd "$OPS_DIR/rollback"; sha256sum -c old-image.sha256)
COMPOSE=(docker --host unix:///var/run/docker.sock compose --project-directory "$FED_REPO" --project-name "$COMPOSE_PROJECT" -f "$OPS_DIR/deployment.private.json")
"${COMPOSE[@]}" config --quiet
EXPECTED_IMAGE_ID=$(docker --host unix:///var/run/docker.sock image inspect "$FED_IMAGE" --format '{{.Id}}')
export EXPECTED_IMAGE_ID
test "$(docker --host unix:///var/run/docker.sock image inspect "$FED_IMAGE" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$REPAIR_REVISION"
python3 "$OPS_DIR/federator_datadog_upgrade.py" --verify "$OPS_DIR/datadog-state"
python3 -c 'import sys,termios;termios.tcflush(sys.stdin.fileno(),termios.TCIFLUSH)'
confirm 'Continue this saved ETH upgrade from original key recovery now?' || exit 0
step '6/7 Restore/check the ORIGINAL federator key and signer'
python3 -c 'import sys,termios;termios.tcflush(sys.stdin.fileno(),termios.TCIFLUSH)'
restore_key
step '7/7 Stage, verify and start the already-downloaded image'
activate
python3 "$OPS_DIR/federator_datadog_upgrade.py" --verify "$OPS_DIR/datadog-state"
run_watcher
'''


def verified_inputs(run, revision, signer):
    c=json.loads(private_bytes(run/'upgrade-context.json'))
    validate_context(c,revision,signer,Path.home().resolve())
    repo=c['FED_REPO']
    def blob(name):
        p=subprocess.run(['git','-C',repo,'show',revision+':tools/'+name],capture_output=True,timeout=15)
        if p.returncode:raise ContinueError('Pinned Git object unavailable; no network fetch attempted')
        return p.stdout
    original=private_bytes(run/'upgrade.sh')
    if original!=blob('upgrade-eth-federator.sh'):
        raise ContinueError('Original upgrader does not match pinned source')
    for name in TOOLS:
        if private_bytes(run/name)!=blob(name):
            raise ContinueError('Saved tool bundle differs from pinned source')
    if hashlib.sha256(private_bytes(run/'deployment.private.json')).hexdigest()!=c['COMPOSE_PLAN_SHA256']:
        raise ContinueError('Saved deployment checksum differs')
    return c,original.decode('utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--revision',required=True)
    p.add_argument('--expected-signer',required=True);p.add_argument('--guard',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args();os.umask(0o077)
    if os.getuid()!=1000 or not sys.platform.startswith('linux'):
        raise ContinueError('Run as Linux deployment user UID1000')
    if not re.fullmatch(r'[0-9a-f]{40}',args.revision) or not re.fullmatch(r'0x[0-9a-fA-F]{40}',args.expected_signer):
        raise ContinueError('Original release revision and public signer required')
    run=args.run.expanduser().absolute()
    base=Path.home().resolve()/'.local/share/bridge-ops'
    if run.parent!=base or run.is_symlink() or not run.name.startswith('eth-upgrade.'):
        raise ContinueError('Use this original private ETH upgrade run')
    info=run.stat()
    if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
        raise ContinueError('Unsafe run directory')
    c,original=verified_inputs(run,args.revision,args.expected_signer)
    if args.guard:
        pre_resume_guard(run,c);print('Original stopped container, completed archives and pinned inputs verified');return 0
    attempt=run/('continue-'+secrets.token_hex(6));attempt.mkdir(mode=0o700)
    script=attempt/'continue.sh';script.write_text(resume_script(original));script.chmod(0o600)
    subprocess.run(['bash','-n',str(script)],check=True)
    env={**os.environ,**c,'RESUME_RUN':str(run),'RESUME_TOOL':str(Path(__file__).resolve()),
         'RESUME_ATTEMPT':str(attempt),'AWS_PAGER':'','COMPOSE_REMOVE_ORPHANS':'false','COMPOSE_IGNORE_ORPHANS':'true'}
    command=['bash',str(script),'--repo',c['FED_REPO'],'--revision',args.revision,'--image',c['FED_IMAGE'],
             '--override',c['RELEASE_OVERRIDE'],'--operator',c['PUBLIC_OPERATOR'],
             '--expected-signer',args.expected_signer,'--watch-seconds',c['WATCH_SECONDS']]
    if c['KEY_SOURCE']=='manual':command.append('--no-aws-secrets')
    print('Continuation evidence:',attempt,flush=True)
    with open('/dev/tty','r+') as tty:
        termios.tcflush(tty.fileno(),termios.TCIFLUSH)
        return subprocess.run(command,env=env,stdin=tty).returncode


if __name__=='__main__':
    try:sys.exit(main())
    except (ContinueError,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,EOFError,KeyboardInterrupt):
        print('Continuation stopped; original evidence retained. Send the last phase/error; do not rerun the full upgrade.',file=sys.stderr)
        sys.exit(1)
