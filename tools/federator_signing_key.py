#!/usr/bin/env python3
"""Reuse the original signing file, discover its EC2 secret, or ask privately."""
import argparse
import getpass
import os
from pathlib import Path
import stat
import warnings

import federator_recovery as r


def restore(node, mode='auto', request_key=None):
    if mode not in ('auto','aws','manual'):
        raise r.RecoveryError('Unsupported original-key recovery mode')
    if node.inspect()['running']:
        raise r.RecoveryError('The federator must be stopped before restoring its startup key')
    key=node.cfg/'federator.key'
    if key.is_symlink():raise r.RecoveryError('Unexpected signing-key symlink')
    if key.exists():
        info=key.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=node.expected_uid:
            raise r.RecoveryError('Unexpected signing-key owner or file type')
        if info.st_size==0:key.unlink()
        else:
            node.key_ready();print('Existing original signing file reused; contents withheld.')
            return 'existing'
    if mode!='manual':
        print('Checking this instance for its original AWS signing secret; contents withheld.',flush=True)
        def discovered(question):
            print(question+' — using the discovered instance secret; contents withheld.',flush=True)
            return True
        try:
            if r.restore_original_key(node,discovered):
                node.key_ready();return 'aws'
        except r.RecoveryError:
            if key.exists() or key.is_symlink():
                raise r.RecoveryError('Automatic key recovery was interrupted after a file appeared; retain it for review') from None
            print('AWS recovery is unavailable or access could not be verified. Using private manual entry.',flush=True)
    if request_key is None:
        warnings.simplefilter('error',getpass.GetPassWarning)
        request_key=lambda:getpass.getpass('Paste ORIGINAL federator private key (hidden): ')
    value=request_key()
    if node.inspect()['running']:
        raise r.RecoveryError('Federator started independently; signing file left unchanged')
    r.install_key(node.cfg,value,node.expected_uid);del value
    node.key_ready()
    print('Original signing file restored privately. Public signer verification is required before startup.')
    return 'manual'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--mode',choices=('auto','aws','manual'),default='auto')
    args=parser.parse_args()
    node=r.Node(args.repo,'eth-rsk','bridge-sc_federation_1',allow_created=True)
    restore(node,args.mode)


if __name__=='__main__':
    try:main()
    except (r.RecoveryError,OSError,ValueError,EOFError,KeyboardInterrupt,getpass.GetPassWarning) as error:
        print('Original-key recovery stopped: '+(str(error) if isinstance(error,r.RecoveryError) else type(error).__name__)+'. Contents withheld.')
        raise SystemExit(1)
