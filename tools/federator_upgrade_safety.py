#!/usr/bin/env python3
"""Private history backup and guarded startup-key cleanup for the ETH upgrader."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import stat
import subprocess
import sys
import time

import federator_recovery as r

VERSION = '1.0.0'
RESERVE = 2 * 1024**3


class SafetyError(Exception):
    pass


def write_json(path, value):
    with r.open_report(path) as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_uid, stat.S_IMODE(info.st_mode))


def stopped(node):
    snap = node.inspect()
    if snap['running']:
        raise SafetyError('History backup requires the stopped ETH container; nothing replaced')
    return snap


def stream_logs(command, target, timeout=600):
    """Bounded-memory compression; stderr includes the application's stderr stream."""
    if shutil.disk_usage(target.parent).free < RESERVE:
        raise SafetyError('Insufficient disk reserve for history backup; original container retained')
    digest = hashlib.sha256()
    size = 0
    deadline = time.monotonic() + timeout
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as raw:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
            try:
                with selectors.DefaultSelector() as selector, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as writer:
                    selector.register(proc.stdout, selectors.EVENT_READ)
                    while True:
                        if time.monotonic() >= deadline:
                            raise SafetyError('History backup timed out; original container retained')
                        if not selector.select(timeout=min(1, max(0, deadline-time.monotonic()))):
                            continue
                        chunk = os.read(proc.stdout.fileno(), 1024*1024)
                        if not chunk:
                            break
                        if shutil.disk_usage(target.parent).free < RESERVE + 2*1024**2:
                            raise SafetyError('Disk reserve reached; original container retained')
                        writer.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    if proc.wait(timeout=max(.1, deadline-time.monotonic())):
                        raise SafetyError('Docker history read failed; original container retained')
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        raw.flush()
        os.fsync(raw.fileno())
    # Read back every byte through gzip/CRC before declaring the archive complete.
    check = hashlib.sha256()
    check_size = 0
    with gzip.open(target, 'rb') as saved:
        for chunk in iter(lambda: saved.read(1024*1024), b''):
            check.update(chunk)
            check_size += len(chunk)
    if (check_size, check.hexdigest()) != (size, digest.hexdigest()):
        raise SafetyError('History archive verification failed; original container retained')
    return {'uncompressed_bytes': size, 'uncompressed_sha256': digest.hexdigest()}


def archive_history(node, destination, command=None):
    before = stopped(node)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise SafetyError('History destination already exists; inspect before retrying')
    destination.mkdir(mode=0o700)
    configs = {}
    for name in ('config.js', 'mainnet.json', 'rskmainnet.json', 'peers.config.js'):
        path = r.safe_path(node.cfg/name, node.cfg)
        directory = r.open_directory(node.cfg)
        try:
            body, _ = r.read_regular_at(directory, name, 1024*1024)
            r.verify_directory(node.cfg, directory)
        finally:
            os.close(directory)
        fd = os.open(destination/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(body)
            out.flush()
            os.fsync(out.fileno())
        configs[name] = hashlib.sha256(body).hexdigest()
    command = command or ['docker', '--host', 'unix:///var/run/docker.sock', 'logs', '--timestamps', before['id']]
    partial = destination/'docker.log.gz.partial'
    result = stream_logs(command, partial)
    after = stopped(node)
    if (after['id'], after['image_id'], after['started']) != (before['id'], before['image_id'], before['started']):
        raise SafetyError('Container changed during history backup; nothing replaced')
    for name, expected in configs.items():
        saved=r.safe_path(destination/name,destination)
        if not saved.is_file() or hashlib.sha256(saved.read_bytes()).hexdigest()!=expected:
            raise SafetyError('Saved configuration verification failed; original container retained')
    partial.rename(destination/'docker.log.gz')
    result.update(version=VERSION, utc=r.utc_now(), source_id=before['id'],
                  image_id=before['image_id'], config_sha256=configs,
                  scope='All retained Docker stdout/stderr with timestamps; original rotated-away logs are unavailable',
                  database_copied=False, signing_key_copied=False)
    write_json(destination/'manifest.json', result)
    return result


def loaded_in_current_run(raw, started):
    boundary = r.parse_time(started)
    if boundary is None:
        return False
    for line in re.sub(r'\x1b\[[0-9;]*m', '', raw).splitlines():
        parts = line.split(' ', 1)
        instant = r.parse_time(parts[0])
        if instant is not None and instant >= boundary and re.search(r'Federators\s*-\s*(?:RSK|ETH) Host\b', line):
            return True
    return False


def start_and_clean(node, expected_image, report, expected_signer, sleep=time.sleep):
    if not re.fullmatch(r'0x[0-9a-fA-F]{40}',expected_signer):
        raise SafetyError('Expected public federator signer required')
    before = node.inspect()
    if before['running'] or before['image_id'] != expected_image:
        raise SafetyError('Unexpected staged image/state; nothing started')
    node.key_ready()
    key = node.cfg/'federator.key'
    directory = r.open_directory(node.cfg)
    try:
        initial = os.stat(key.name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(initial.st_mode) or initial.st_uid != node.expected_uid or stat.S_IMODE(initial.st_mode) != 0o600:
            raise SafetyError('Unexpected startup key ownership/type/mode')
        evidence = {'version': VERSION, 'utc': r.utc_now(), 'source_id': before['id'],
                    'image_id': expected_image, 'outcome': 'startup_key_cleanup_pending'}
        with r.open_report(report) as journal:
            json.dump(evidence, journal)
            journal.flush()
            os.fsync(journal.fileno())
            try:
                node.runner.run(['docker','run','--rm','--network','none','--read-only','--log-driver','none',
                    '--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000',
                    '--entrypoint','node','--workdir','/app/federator','-e','EXPECTED_SIGNER='+expected_signer,
                    '--mount','type=bind,source='+str(key)+',target=/run/federator.key,readonly', expected_image,
                    '-e', '''try {
const fs=require("fs"),ethers=require("ethers").ethers;
const key=fs.readFileSync("/run/federator.key","utf8").trim();
const address=new ethers.Wallet(key.startsWith("0x")?key:"0x"+key).address;
if(address.toLowerCase()!==process.env.EXPECTED_SIGNER.toLowerCase())throw Error();
console.log("Verified original FEDERATOR signer: "+address);
} catch (_) {console.error("Signer verification failed; key contents withheld");process.exit(1);}'''], timeout=30)
                r.verify_directory(node.cfg,directory)
                if identity(os.stat(key.name,dir_fd=directory,follow_symlinks=False))!=identity(initial):
                    raise SafetyError('Key changed during public signer verification; nothing started')
                check=node.inspect()
                if check['running'] or (check['id'],check['image_id'])!=(before['id'],expected_image):
                    raise SafetyError('Staged container changed during signer verification; nothing started')
                node.runner.run(['docker', 'start', before['id']], timeout=30)
                running = node.inspect()
                if not running['running'] or running['id'] != before['id'] or running['image_id'] != expected_image:
                    raise SafetyError('Started container identity/state not confirmed')
                print('ETH node started. Waiting 90 seconds to verify startup and remove its temporary signing key.', flush=True)
                sleep(90)
                def verify_process():
                    current = node.inspect()
                    if not current['running'] or (current['id'], current['image_id'], current['started']) != (running['id'], expected_image, running['started']):
                        raise SafetyError('ETH process changed; startup key cleanup pending')
                verify_process()
                raw = node.runner.run(['docker', 'logs', '--timestamps', '--since', running['started'], '--tail', '2000', before['id']], timeout=15)
                if not loaded_in_current_run(raw, running['started']):
                    raise SafetyError('Fresh configuration-load message unavailable; startup key cleanup pending')
                verify_process()
                r.verify_directory(node.cfg, directory)
                current = os.stat(key.name, dir_fd=directory, follow_symlinks=False)
                if identity(current) != identity(initial):
                    raise SafetyError('Startup key file changed; cleanup pending')
                os.unlink(key.name, dir_fd=directory)
                os.fsync(directory)
                evidence.update(outcome='running_startup_key_removed', started_utc=running['started'], removed_utc=r.utc_now())
            finally:
                journal.seek(0)
                json.dump(evidence, journal, indent=2)
                journal.write('\n')
                journal.truncate()
                journal.flush()
                os.fsync(journal.fileno())
    finally:
        os.close(directory)
    print('Current ETH process verified; temporary startup signing key removed. Original custody is unchanged.', flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-signer')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--archive-history', action='store_true')
    action.add_argument('--start-cleanup', metavar='EXPECTED_IMAGE_ID')
    args = parser.parse_args()
    os.umask(0o077)
    if os.getuid() != 1000:
        raise SafetyError('Use deployment user UID1000')
    node = r.Node(args.repo, 'eth-rsk', 'bridge-sc_federation_1', allow_created=True)
    if args.archive_history:
        archive_history(node, args.output)
        print('Verified private Docker log/config archive:', args.output)
    else:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.start_cleanup):
            raise SafetyError('Expected immutable image ID required')
        start_and_clean(node, args.start_cleanup, args.output, args.expected_signer or "")


if __name__ == '__main__':
    try:
        main()
    except (SafetyError, r.RecoveryError, OSError, subprocess.SubprocessError, KeyboardInterrupt):
        print('Upgrade backup/startup check incomplete. Keep the private run directory; inspect the printed phase before retrying. If a start was attempted, temporary key cleanup may be pending.', file=sys.stderr)
        sys.exit(1)
