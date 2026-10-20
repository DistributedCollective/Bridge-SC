#!/usr/bin/env python3
"""Build the disposable bridge lab from a public-code-only context."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen

BASELINE = 'c5a6f607481277a69dd86364976b078501e10c4e'
DIGESTS = {
    'arm64': '01228ac84a30ec65c49b9f0da38183f4665c196245a3f9156a54bc98c7e94ab0',
    'amd64': '9746c51f76c57ee2b099aa67d8b6fb8a93c82175671b654b1b8fd8ddba8e3b42',
}
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']

def populate(repo, context):
    """Copy tracked runtime source/ABIs, never host config, databases or keys."""
    repo = repo.resolve()
    allowed = ('sovryn-token-bridge/federator/src/', 'sovryn-token-bridge/abis/')
    files = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z', *allowed]).decode().split('\0')
    for relative in filter(None, files):
        source = repo / relative
        if source.is_symlink() or not source.is_file() or repo not in source.resolve().parents:
            raise ValueError('Unexpected runtime source path')
        destination = context / 'app' / Path(relative).relative_to('sovryn-token-bridge')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    config = context / 'app/federator/config/config.js'
    config.parent.mkdir(parents=True)
    config.write_text('module.exports={gasApiRunEvery:1,avgGasRunEvery:1,periodAvgGas:1};\n')
    baseline = subprocess.check_output(['git', '-C', str(repo), 'show', BASELINE + ':sovryn-token-bridge/federator/src/lib/TransactionSender.js'])
    (context / 'app/federator/src/lib/TransactionSender.baseline.js').write_bytes(baseline)
    for name in ('Dockerfile', 'package.json', 'package-lock.json'):
        shutil.copyfile(repo / 'tools/fork-lab' / name, context / name)
    shutil.copyfile(repo / 'tools/fork_lab_worker.cjs', context / 'worker.cjs')
    shutil.copyfile(repo / 'tools/fork_lab.py', context / 'fork_lab.py')
    (context / '.dockerignore').write_text('*\n!Dockerfile\n!package*.json\n!app/\n!app/**\n!worker.cjs\n!fork_lab.py\n!anvil\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='bridge-fork-lab:local')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    architecture = subprocess.check_output(DOCKER + ['info', '--format', '{{.Architecture}}']).decode().strip()
    arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64', 'amd64': 'amd64'}.get(architecture)
    if arch is None:
        raise ValueError('Unsupported Linux Docker architecture')
    with tempfile.TemporaryDirectory(prefix='bridge-fork-build-') as directory:
        context = Path(directory)
        context.chmod(0o700)
        populate(repo, context)
        url = f'https://github.com/foundry-rs/foundry/releases/download/v1.3.5/foundry_v1.3.5_linux_{arch}.tar.gz'
        with urlopen(url, timeout=60) as response:
            archive = response.read(256 * 1024 * 1024 + 1)
        if len(archive) > 256 * 1024 * 1024 or hashlib.sha256(archive).hexdigest() != DIGESTS[arch]:
            raise ValueError('Foundry binary checksum mismatch')
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as bundle:
            member = bundle.getmember('anvil')
            if not member.isfile() or member.size > 256 * 1024 * 1024:
                raise ValueError('Unexpected Anvil archive member')
            (context / 'anvil').write_bytes(bundle.extractfile(member).read())
        (context / 'anvil').chmod(0o755)
        subprocess.run(DOCKER + ['build', '--label', 'bridge.lab.build=three-federator-reproduction', '-t', args.image, str(context)], check=True)
        print(json.dumps({'image': args.image, 'architecture': arch, 'anvilArchiveSHA256': DIGESTS[arch], 'packageLockSHA256': hashlib.sha256((context / 'package-lock.json').read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
