#!/usr/bin/env python3
"""Prepare private ETH-only Compose inputs without interpolating Agent settings."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import stat
import sys


class PlanError(Exception):
    pass


def without_version(text):
    return re.sub(r'(?m)^version:[^\r\n]*(?:\r?\n|$)', '', text, count=1)


def federation_only(model):
    if not isinstance(model, dict) or not isinstance(model.get('services'), dict):
        raise PlanError('Expected a Compose services model')
    service = model['services'].get('federation')
    if not isinstance(service, dict):
        raise PlanError('ETH federation service is missing')
    if any(service.get(field) for field in ('depends_on', 'links', 'volumes_from')):
        raise PlanError('Additional service dependencies require a reviewed deployment')
    plan = {'services': {'federation': copy.deepcopy(service)}}
    if 'name' in model:
        plan['name'] = model['name']
    references = {
        'networks': set(service.get('networks') or []),
        'volumes': {v['source'] for v in service.get('volumes', [])
                    if isinstance(v, dict) and v.get('type') == 'volume' and v.get('source')},
    }
    for kind in ('secrets', 'configs'):
        references[kind] = {v if isinstance(v, str) else v['source'] for v in service.get(kind, [])}
    for kind, names in references.items():
        declarations = model.get(kind, {})
        if not isinstance(declarations, dict):
            raise PlanError('Invalid resource declarations')
        selected = {name: copy.deepcopy(declarations[name]) for name in names if name in declarations}
        if selected:
            plan[kind] = selected
    return plan


def write_private(path, body):
    path = Path(path).absolute()
    parent = path.parent
    info = parent.stat()
    if parent.is_symlink() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise PlanError('Output requires an owned private directory')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(body)
        output.flush()
        os.fsync(output.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--base', type=Path, help='write version-free YAML from stdin')
    mode.add_argument('--model', type=Path, help='write federation-only JSON from uninterpolated stdin')
    args = parser.parse_args()
    data = sys.stdin.buffer.read(2*1024*1024+1)
    if len(data) > 2*1024*1024:
        raise PlanError('Compose input exceeds the bound')
    text = data.decode('utf8')
    if args.base:
        write_private(args.base, without_version(text))
    else:
        write_private(args.model, json.dumps(federation_only(json.loads(text))))
    print('Private Compose input prepared')


if __name__ == '__main__':
    try:
        main()
    except (PlanError, OSError, ValueError, TypeError, KeyError):
        print('Compose input preparation failed; raw configuration withheld. No service changed.', file=sys.stderr)
        sys.exit(1)
