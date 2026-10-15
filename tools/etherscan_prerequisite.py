#!/usr/bin/env python3
"""Validate the existing ETH node's Etherscan key before an operator upgrade."""
import getpass
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import warnings
import federator_recovery as recovery
import federator_dependencies as dependencies


class PrerequisiteError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def validate_text(value):
    if not isinstance(value, str):
        raise PrerequisiteError('Etherscan API key is invalid; key contents withheld')
    value = value.strip()
    if (not re.fullmatch(r'[A-Za-z0-9_-]{1,1024}', value) or
            re.fullmatch(r'(?:0x)?[0-9a-fA-F]{64}', value)):
        raise PrerequisiteError('Expected an Etherscan API key, never a signing key; contents withheld')
    return value


def validate_remote(value):
    validate_text(value)
    url = 'https://api.etherscan.io/v2/api?' + urllib.parse.urlencode({
        'chainid': '1', 'module': 'gastracker', 'action': 'gasoracle', 'apikey': value})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(urllib.request.Request(url), timeout=5) as response:
            raw = response.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError('response bound')
        data = json.loads(raw)
        quote = data['result']['SafeGasPrice']
        if (data['status'] != '1' or not isinstance(quote, str) or
                not re.fullmatch(r'\d+(?:\.\d+)?', quote) or
                not math.isfinite(float(quote)) or float(quote) <= 0):
            raise ValueError('quote')
    except (OSError, ValueError, KeyError, TypeError):
        raise PrerequisiteError('Etherscan V2 gas-oracle check failed; check key access/network/quota. Node not stopped.') from None


def hidden_prompt(message):
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            return getpass.getpass(message)
        except getpass.GetPassWarning:
            raise PrerequisiteError('Hidden terminal input unavailable; key was not read') from None


def ensure(cfg, prompt=hidden_prompt):
    cfg = Path(cfg)
    temporary = None
    directory = None
    try:
        config_path = recovery.safe_path(cfg / 'config.js', cfg)
        text = dependencies.strip_comments(dependencies.read_public(config_path, cfg))
        if 'etherscan.key' not in text or not re.search(r'\betherscanApiKey\s*:', text):
            raise PrerequisiteError('Local config must load etherscan.key as etherscanApiKey; request the compatible config before upgrading')
        recovery.safe_path(cfg / 'etherscan.key', cfg)
        directory = recovery.open_directory(cfg)
        original = recovery.read_regular_at(directory, 'etherscan.key', 2048, allow_missing=True)
        if original:
            raw, metadata = original
            if metadata.st_uid != os.getuid():
                raise PrerequisiteError('Existing Etherscan key must belong to the deployment user')
            value = validate_text(raw.decode('ascii'))
        else:
            value = validate_text(prompt('Etherscan API key missing. Paste YOUR API key (hidden): '))
        validate_remote(value)
        recovery.verify_directory(cfg, directory)
        if original:
            fd = os.open('etherscan.key', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            try:
                now = os.fstat(fd)
                if (now.st_dev, now.st_ino) != (metadata.st_dev, metadata.st_ino) or not stat.S_ISREG(now.st_mode):
                    raise PrerequisiteError('Etherscan key changed during validation; node not stopped')
                if os.read(fd, 2049) != raw:
                    raise PrerequisiteError('Etherscan key changed during validation; node not stopped')
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
        else:
            fd, temporary = recovery.private_temp_at(directory, '.etherscan.key.')
            with os.fdopen(fd, 'w') as out:
                out.write(value + '\n'); out.flush(); os.fsync(out.fileno())
            recovery.verify_directory(cfg, directory)
            os.link(temporary, 'etherscan.key', src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            os.fsync(directory)
        print('Etherscan key ready: existing/new file validated with one V2 request; contents withheld.')
    except (recovery.RecoveryError, dependencies.DiagnosticError, OSError, UnicodeError):
        raise PrerequisiteError('Etherscan key file is unavailable/unsafe or changed; node not stopped') from None
    finally:
        if temporary is not None:
            os.unlink(temporary, dir_fd=directory)
        if directory is not None:
            os.close(directory)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('Usage: etherscan_prerequisite.py CONFIG_DIRECTORY', file=sys.stderr)
        return 2
    try:
        ensure(Path(argv[0]))
        return 0
    except PrerequisiteError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
