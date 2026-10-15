#!/usr/bin/env python3
"""Prepare a minimal private Docker context from an immutable reviewed Git commit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile

SOURCE_PREFIX = 'sovryn-token-bridge/federator/'
SOURCE_INPUTS = (
    SOURCE_PREFIX + 'src/lib/GasPriceAvg.js',
    SOURCE_PREFIX + 'src/lib/GasPriceFetcher.js',
    SOURCE_PREFIX + 'src/lib/GasServices.js',
    SOURCE_PREFIX + 'src/lib/TransactionSender.js',
    SOURCE_PREFIX + 'src/vendors/RSKKeyedAuth.js',
)
DOCKERFILE = 'sovryn-token-bridge/Dockerfile.repair-overlay'
INPUTS = SOURCE_INPUTS + (DOCKERFILE, DOCKERFILE + '.dockerignore')


class ContextError(Exception):
    pass


def git_read(repo, arguments):
    try:
        result = subprocess.run(['git', '-C', str(repo), 'cat-file'] + arguments,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        raise ContextError('Reviewed Git source unavailable or timed out') from None
    if result.returncode or len(result.stdout) > 1024 * 1024:
        raise ContextError('Reviewed Git source unavailable/oversized; raw output withheld')
    return result.stdout


def prepare(repo, revision, output):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ContextError('A full immutable reviewed commit ID is required')
    repo = Path(repo).expanduser().resolve()
    output = Path(output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ContextError('Context destination already exists; nothing overwritten')
    # Accept OS-wide aliases above the selected parent; refuse a symlinked output parent.
    if output.parent.is_symlink():
        raise ContextError('Context parent must not be a symlink')
    if git_read(repo, ['-t', revision]).strip() != b'commit':
        raise ContextError('Reviewed revision is not a commit')
    # Read only seven literal public Git object paths, never the checkout or private directories.
    blobs = {name: git_read(repo, ['blob', revision + ':' + name]) for name in INPUTS}
    try:
        output.mkdir(mode=0o700)
        os.chmod(output, 0o700)
        for name, body in blobs.items():
            destination = output / name
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as writer:
                writer.write(body)
        actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
        if actual != set(INPUTS):
            raise ContextError('Sanitized context inventory differs from the fixed public allowlist')
    except OSError:
        raise ContextError('Private context creation failed; no Docker action performed') from None
    return {'revision': revision, 'context': str(output), 'dockerfile': DOCKERFILE,
            'files': list(INPUTS),
            'repair_source_sha256': {name[len(SOURCE_PREFIX):]: hashlib.sha256(body).hexdigest()
                                     for name, body in blobs.items() if name in SOURCE_INPUTS}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.home() / 'Bridge-SC')
    parser.add_argument('--revision', required=True, help='full reviewed commit ID; no branch/HEAD')
    parser.add_argument('--output', type=Path, help='new private context directory; existing paths refused')
    args = parser.parse_args(argv)
    output = args.output or Path(tempfile.gettempdir()) / ('federator-repair-context-' + secrets.token_hex(12))
    print(json.dumps(prepare(args.repo, args.revision, output), indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ContextError as error:
        print('Context preparation stopped:', error, file=sys.stderr)
        sys.exit(1)
