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

VERSION = '1.2.0'
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


def safe_failure(error):
    reasons = {
        'History backup timed out; original container retained': 'LOG_EXPORT_TIMEOUT',
        'Docker history read failed; original container retained': 'LOG_READ_FAILED',
        'Insufficient disk reserve for history backup; original container retained': 'DISK_RESERVE_LOW',
        'Disk reserve reached; original container retained': 'DISK_RESERVE_REACHED',
        'History archive verification failed; original container retained': 'LOG_ARCHIVE_MISMATCH',
        'Database directory depth exceeds backup bound': 'DATABASE_DEPTH_LIMIT',
        'Database exceeds private backup bound': 'DATABASE_SIZE_LIMIT',
        'Database changed during stopped backup': 'DATABASE_CHANGED',
        'Database contains a link or unsupported file; nothing replaced': 'DATABASE_UNSUPPORTED_ENTRY',
        'Saved configuration verification failed; original container retained': 'CONFIG_BACKUP_MISMATCH',
        'Database source or private backup changed; original container retained': 'DATABASE_BACKUP_MISMATCH',
        'Container changed during history backup; nothing replaced': 'SOURCE_CHANGED',
        'History destination already exists; inspect before retrying': 'HISTORY_ALREADY_EXISTS',
    }
    result = {'type': type(error).__name__, 'reason': reasons.get(str(error), 'CHECK_FAILED')}
    number = getattr(error, 'errno', None)
    if type(number) is int: result['errno'] = number
    if isinstance(error, subprocess.TimeoutExpired): result['reason'] = 'CHILD_TIMEOUT'
    return result


def update_private_json(path, value):
    directory = r.open_directory(path.parent)
    temporary = None
    try:
        try: info = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError: info = None
        if info is not None and (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise SafetyError('Unsafe history progress file')
        fd, temporary = r.private_temp_at(directory, '.history-progress.')
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        r.verify_directory(path.parent, directory)
        os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        temporary = None
        os.fsync(directory)
        r.verify_directory(path.parent, directory)
    finally:
        if temporary is not None: os.unlink(temporary, dir_fd=directory)
        os.close(directory)


class HistoryProgress:
    def __init__(self, destination):
        self.destination = destination
        self.started = time.monotonic()
        self.value = {'version': VERSION, 'status': 'RUNNING', 'stage': 'CONFIG_BACKUP',
                      'uncompressed_bytes': 0, 'compressed_bytes': 0}

    def emit(self, stage=None, **fields):
        if stage: self.value['stage'] = stage
        self.value.update(fields, utc=r.utc_now(), elapsed_seconds=round(time.monotonic()-self.started, 1))
        self.value['free_bytes'] = shutil.disk_usage(self.destination).free
        update_private_json(self.destination/'progress.json', self.value)
        message = ('History backup: '+self.value['stage']+'; '+self.value['status']+
                   '; '+str(round(self.value['uncompressed_bytes']/1024**2, 1))+' MiB read; '+
                   str(round(self.value['compressed_bytes']/1024**2, 1))+' MiB saved; '+
                   str(self.value['elapsed_seconds'])+' seconds')
        if 'failure' in self.value: message += '; '+json.dumps(self.value['failure'], sort_keys=True)
        print(message, flush=True)


def stream_logs(command, target, timeout=1800, progress=None, progress_interval=30):
    """Complete retained history, fast gzip, bounded memory and visible progress."""
    if shutil.disk_usage(target.parent).free < RESERVE:
        raise SafetyError('Insufficient disk reserve for history backup; original container retained')
    digest = hashlib.sha256()
    size = 0
    deadline = time.monotonic() + timeout
    next_progress = 0
    progress = progress or (lambda *args, **kwargs: None)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as raw:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
                try:
                    with selectors.DefaultSelector() as selector, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=1) as writer:
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        while True:
                            now = time.monotonic()
                            if now >= deadline:
                                raise SafetyError('History backup timed out; original container retained')
                            if now >= next_progress:
                                progress('LOG_EXPORT', uncompressed_bytes=size, compressed_bytes=raw.tell())
                                next_progress = now + progress_interval
                            if not selector.select(timeout=min(1, max(0, deadline-now))):
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
                        proc.kill(); proc.wait()
            raw.flush(); os.fsync(raw.fileno())
    except BaseException:
        try: progress('LOG_EXPORT', uncompressed_bytes=size, compressed_bytes=target.stat().st_size)
        except Exception: pass
        raise
    progress('LOG_VERIFY', uncompressed_bytes=size, compressed_bytes=target.stat().st_size)
    check = hashlib.sha256(); check_size = 0; next_progress = time.monotonic()+progress_interval
    with gzip.open(target, 'rb') as saved:
        for chunk in iter(lambda: saved.read(1024*1024), b''):
            check.update(chunk); check_size += len(chunk)
            if time.monotonic() >= next_progress:
                progress('LOG_VERIFY', verified_bytes=check_size)
                next_progress = time.monotonic()+progress_interval
    if (check_size, check.hexdigest()) != (size, digest.hexdigest()):
        raise SafetyError('History archive verification failed; original container retained')
    return {'uncompressed_bytes': size, 'uncompressed_sha256': digest.hexdigest(),
            'compression_level': 1, 'export_timeout_seconds': timeout}


def database_records(root, copy_to=None):
    """Read a bounded stopped database tree without following links."""
    root = Path(root)
    if not root.exists() and not root.is_symlink():
        return None
    records = {}; total = 0
    def walk(path, relative, depth):
        nonlocal total
        if depth > 32:
            raise SafetyError('Database directory depth exceeds backup bound')
        directory = r.open_directory(path)
        try:
            for name in sorted(os.listdir(directory)):
                entry = os.stat(name, dir_fd=directory, follow_symlinks=False)
                rel = relative/name
                if stat.S_ISDIR(entry.st_mode):
                    if copy_to is not None: (copy_to/rel).mkdir(mode=0o700)
                    walk(path/name, rel, depth+1)
                elif stat.S_ISREG(entry.st_mode):
                    body, before = r.read_regular_at(directory, name, 16*1024*1024)
                    total += len(body)
                    if len(records) >= 10000 or total > 64*1024*1024:
                        raise SafetyError('Database exceeds private backup bound')
                    after = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if identity(before) != identity(after):
                        raise SafetyError('Database changed during stopped backup')
                    records[str(rel)] = hashlib.sha256(body).hexdigest()
                    if copy_to is not None:
                        fd = os.open(copy_to/rel, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                        with os.fdopen(fd, 'wb') as out:
                            out.write(body); out.flush(); os.fsync(out.fileno())
                else:
                    raise SafetyError('Database contains a link or unsupported file; nothing replaced')
            r.verify_directory(path, directory)
        finally:
            os.close(directory)
    if copy_to is not None: copy_to.mkdir(mode=0o700)
    walk(root, Path(), 0)
    return records


def archive_history(node, destination, command=None, timeout=1800, progress_interval=30):
    before = stopped(node)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise SafetyError('History destination already exists; inspect before retrying')
    destination.mkdir(mode=0o700)
    progress = HistoryProgress(destination)
    try:
        progress.emit('CONFIG_BACKUP')
        configs = {}
        for name in ('config.js', 'mainnet.json', 'rskmainnet.json', 'peers.config.js'):
            progress.emit('CONFIG_BACKUP', file_role=name)
            path = r.safe_path(node.cfg/name, node.cfg)
            directory = r.open_directory(node.cfg)
            try:
                body, _ = r.read_regular_at(directory, name, 1024*1024)
                r.verify_directory(node.cfg, directory)
            finally:
                os.close(directory)
            fd = os.open(destination/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as out:
                out.write(body); out.flush(); os.fsync(out.fileno())
            configs[name] = hashlib.sha256(body).hexdigest()
        progress.emit('DATABASE_BACKUP')
        database = database_records(node.cfg/'db', destination/'database')
        progress.emit('LOG_EXPORT')
        command = command or ['docker', '--host', 'unix:///var/run/docker.sock', 'logs', '--timestamps', before['id']]
        partial = destination/'docker.log.gz.partial'
        result = stream_logs(command, partial, timeout=timeout, progress=progress.emit, progress_interval=progress_interval)
        progress.emit('SOURCE_AND_BACKUP_VERIFY')
        after = stopped(node)
        if (after['id'], after['image_id'], after['started']) != (before['id'], before['image_id'], before['started']):
            raise SafetyError('Container changed during history backup; nothing replaced')
        for name, expected in configs.items():
            saved=r.safe_path(destination/name,destination)
            if not saved.is_file() or hashlib.sha256(saved.read_bytes()).hexdigest()!=expected:
                raise SafetyError('Saved configuration verification failed; original container retained')
        if database_records(node.cfg/'db') != database or (database is not None and database_records(destination/'database') != database):
            raise SafetyError('Database source or private backup changed; original container retained')
        partial.rename(destination/'docker.log.gz')
        result.update(version=VERSION, utc=r.utc_now(), source_id=before['id'],
                      image_id=before['image_id'], config_sha256=configs,
                      scope='All retained Docker stdout/stderr with timestamps; original rotated-away logs are unavailable',
                      database_copied=database is not None, database_sha256=database, signing_key_copied=False)
        write_json(destination/'manifest.json', result)
        progress.emit('COMPLETE', status='COMPLETE')
        return result
    except BaseException as error:
        try: progress.emit(status='FAILED', failure=safe_failure(error))
        except Exception: pass
        raise


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
                    'image_id': expected_image, 'outcome': 'startup_key_cleanup_pending',
                    'key_identity': list(identity(initial)), 'expected_signer': expected_signer}
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
                evidence['started_utc'] = running['started']
                journal.seek(0); json.dump(evidence, journal); journal.truncate(); journal.flush(); os.fsync(journal.fileno())
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


def finish_key_cleanup(node, report):
    """Remove only the unchanged startup copy for the journalled running process."""
    report = Path(report).expanduser().absolute()
    parent = r.open_directory(report.parent)
    try:
        fd = os.open(report.name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'r+') as journal:
            info = os.fstat(journal.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 65536:
                raise SafetyError('Unsafe startup cleanup report')
            evidence = json.load(journal)
            current = node.inspect()
            def verify():
                value = node.inspect()
                if not value['running'] or any(value.get(k) != evidence.get(saved) for k, saved in
                      (('id', 'source_id'), ('image_id', 'image_id'), ('started', 'started_utc'))):
                    raise SafetyError('Cleanup report does not match the current running process')
            verify()
            key = node.cfg / 'federator.key'
            if evidence.get('outcome') == 'running_startup_key_removed':
                if key.exists() or key.is_symlink(): raise SafetyError('Key reappeared after completed cleanup')
                return evidence
            if evidence.get('outcome') != 'startup_key_cleanup_pending' or not isinstance(evidence.get('key_identity'), list):
                raise SafetyError('Report lacks guarded cleanup metadata; coordinator review required')
            started = r.parse_time(evidence.get('started_utc'))
            if started is None or (r.parse_time(r.utc_now()) - started).total_seconds() < 90:
                raise SafetyError('Wait until at least90 seconds after this process started')
            raw = node.runner.run(['docker', 'logs', '--timestamps', '--since', current['started'], '--tail', '2000', current['id']], timeout=15)
            if not loaded_in_current_run(raw, current['started']):
                raise SafetyError('Fresh configuration-load proof still unavailable; key retained')
            directory = r.open_directory(node.cfg)
            try:
                r.verify_directory(node.cfg, directory); verify()
                try: initial = os.stat(key.name, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError: initial = None
                if initial is not None:
                    if not stat.S_ISREG(initial.st_mode) or list(identity(initial)) != evidence['key_identity']:
                        raise SafetyError('Startup key changed; cleanup refused')
                    os.unlink(key.name, dir_fd=directory); os.fsync(directory)
                evidence.update(outcome='running_startup_key_removed', removed_utc=r.utc_now(), cleanup_resumed=True)
                r.verify_directory(report.parent, parent)
                linked = os.stat(report.name, dir_fd=parent, follow_symlinks=False)
                if (linked.st_dev, linked.st_ino) != (info.st_dev, info.st_ino):
                    raise SafetyError('Cleanup report path changed')
                journal.seek(0); json.dump(evidence, journal, indent=2); journal.write('\n')
                journal.truncate(); journal.flush(); os.fsync(journal.fileno())
            finally:
                os.close(directory)
    finally:
        os.close(parent)
    print('Temporary startup signing key removed; existing process was not restarted.', flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-signer')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--archive-history', action='store_true')
    action.add_argument('--start-cleanup', metavar='EXPECTED_IMAGE_ID')
    action.add_argument('--finish-key-cleanup', action='store_true', help='finish a pending journalled key cleanup without starting/restarting the node')
    args = parser.parse_args()
    os.umask(0o077)
    if os.getuid() != 1000:
        raise SafetyError('Use deployment user UID1000')
    node = r.Node(args.repo, 'eth-rsk', 'bridge-sc_federation_1', allow_created=True)
    if args.archive_history:
        archive_history(node, args.output)
        print('Verified private Docker log/config archive:', args.output)
    elif args.finish_key_cleanup:
        finish_key_cleanup(node, args.output)
    else:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.start_cleanup):
            raise SafetyError('Expected immutable image ID required')
        start_and_clean(node, args.start_cleanup, args.output, args.expected_signer or "")


if __name__ == '__main__':
    try:
        main()
    except (SafetyError, r.RecoveryError, OSError, subprocess.SubprocessError, KeyboardInterrupt, ValueError, TypeError, KeyError) as error:
        operation='History backup incomplete; no replacement/start was attempted by this command' if '--archive-history' in sys.argv else 'Startup/key-cleanup check incomplete; temporary cleanup may be pending'
        print(operation+': '+json.dumps(safe_failure(error),sort_keys=True)+'. Keep the private run directory and the printed phase.',file=sys.stderr)
        sys.exit(1)
