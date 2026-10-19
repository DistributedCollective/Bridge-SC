#!/usr/bin/env python3
"""Keep ETH application replacement independent from guarded monitoring recovery."""
import argparse
import getpass
import warnings
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import dd_agent_recovery as r
import federator_datadog_upgrade as u
import federator_agent_replacement as fresh

VERSION = '1.0.0'


def private_json(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise r.RepairError('Expected owned private regular evidence')
        body = source.read(r.MAX_BYTES + 1)
    if len(body) > r.MAX_BYTES:
        raise r.RepairError('Evidence exceeds bound')
    return json.loads(body)


def report(output, **fields):
    value = dict(version=VERSION, utc=r.utc(), status='UNRESOLVED', indexed_visibility='UNKNOWN',
                 application_changed_by_monitoring=False)
    value.update(fields)
    r.update_report(output, value)
    return value


def snapshot(docker, output):
    output = r.safe_path(output)
    source = docker.inspect('bridge-sc_federation_1')
    r.ensure_output_outside_source(output, source)
    output.mkdir(mode=0o700)
    value = {'backup': 'UNAVAILABLE', 'source_id': source['id']}
    try:
        agent = docker.inspect('datadog-agent', agent=True)
        value.update(agent=u.stable(agent), backup='PARTIAL')
        raw = docker.call(['inspect', agent['id']])
        full = json.loads(raw)
        if len(full) != 1 or full[0]['Id'] != agent['id'] or full[0]['Image'] != agent['image']:
            raise r.RepairError('Agent changed during private snapshot')
        r.write_private_bytes(output/'agent-container.private.json', raw)
        config_path = r.config_path(docker, agent)
        docker.copy_out(agent['id'], config_path, output/'config.private.yaml')
        integrations=docker.call(['cp',agent['id']+':/etc/datadog-agent/conf.d','-'])
        r.write_private_bytes(output/'integrations.private.tar',integrations)
        env = dict(x.split('=', 1) for x in agent.get('env', []) if '=' in x)
        # Preserve raw old bytes only. Replacement does not parse an old registry or run its image.
        paths = [env.get('DD_LOGS_CONFIG_RUN_PATH','/opt/datadog-agent/run').rstrip('/')+'/registry.json',
                 r.PERSISTENT_PATH+'/registry.json']
        copied = False
        for path in dict.fromkeys(paths):
            if not isinstance(path,str) or not path.startswith('/') or '..' in Path(path).parts:continue
            try:
                docker.copy_out(agent['id'],path,output/'registry.private.json')
                copied = True;break
            except (r.RepairError,OSError):pass
        value['registry_backup_available'] = copied
        if u.stable(docker.inspect('datadog-agent', agent=True)) != value['agent']:
            raise r.RepairError('Agent changed during snapshot')
        value['backup'] = 'COMPLETE'
    except (r.RepairError, OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        value['failure_type'] = type(error).__name__
    r.write_private(output/'snapshot.json', value)
    return report(output, reason='NOT_ATTEMPTED', **value)


def recover(docker, output, request_key=None):
    output = r.safe_path(output, existing=True)
    value = private_json(output/'snapshot.json')
    common = {'backup': value.get('backup', 'UNAVAILABLE')}
    if 'agent' not in value or value.get('backup')!='COMPLETE':
        return report(output, reason='MONITORING_BACKUP_INCOMPLETE', **common)
    if (output/'replacement-started.json').exists():
        return report(output, reason='PREVIOUS_REPLACEMENT_ATTEMPT', **common)
    try:
        agent = docker.inspect('datadog-agent', agent=True)
        if u.stable(agent) != value['agent']:
            return report(output, reason='AGENT_CHANGED', **common)
        rows = private_json(output/'agent-container.private.json')
        if not isinstance(rows,list) or len(rows)!=1:
            raise r.RepairError('Original Agent metadata backup unavailable')
        def progress(stage):
            report(output,reason='REPLACEMENT_IN_PROGRESS',phase=stage,**common)
            print('Monitoring: '+stage.lower().replace('_',' '),flush=True)
        manifest, agent = fresh.replace(docker, output, rows[0], request_key,progress=progress)
        return report(output, status='TRACKING_CONFIGURED', reason='CLEAN_AGENT_STARTED_WITH_FRESH_CUTOFF',
                      agent=u.stable(agent), source_delivery='UNKNOWN',
                      cutover_utc=manifest['utc'], source_cutoff=manifest['source_cutoff'], **common)
    except (r.RepairError, OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        phase='PREPARATION'
        try:phase=private_json(output/'report.json').get('phase',phase)
        except (r.RepairError,OSError,ValueError,KeyError,TypeError):pass
        return report(output, reason='REPLACEMENT_INCOMPLETE', phase=phase, failure_type=type(error).__name__, **common)


def result(docker, run, watcher, rollback=False):
    run = r.safe_path(run, existing=True)
    app = {'status': 'UNKNOWN'}
    try:
        existing = (run/'monitoring-only.json').is_file()
        journal = private_json(run/'monitoring-only.json') if existing else private_json(run/('rollback-startup-key-cleanup.json' if rollback else 'startup-key-cleanup.json'))
        source = docker.inspect('bridge-sc_federation_1')
        identity = (journal.get('id'),journal.get('image_id'),journal.get('started')) if existing else (journal.get('source_id'),journal.get('image_id'),journal.get('started_utc'))
        same = identity == (source['id'],source['image'],source['state']['StartedAt'])
        healthy = source['state'].get('Running') is True and not source['state'].get('Paused') and same
        proof = existing or journal.get('outcome') == 'running_startup_key_removed'
        app['status'] = ('RUNNING_EXISTING_IMAGE' if existing else 'RUNNING_STARTUP_VERIFIED') if healthy and proof else 'FAIL'
    except (r.RepairError, OSError, ValueError, KeyError, TypeError):
        pass
    monitoring = {'status': 'UNRESOLVED', 'reason': 'NO_MONITORING_RESULT'}
    try:
        saved = private_json(run/'monitoring/report.json')
        monitoring = {k: saved[k] for k in ('status', 'reason', 'phase', 'indexed_visibility') if k in saved}
        if saved.get('status') == 'TRACKING_CONFIGURED':
            current = docker.inspect('datadog-agent', agent=True)
            if not current['state'].get('Running') or current['state'].get('Paused') or u.stable(current) != saved.get('agent'):
                monitoring = {'status': 'UNRESOLVED', 'reason': 'AGENT_CHANGED_AFTER_RECOVERY'}
    except (r.RepairError, OSError, ValueError, KeyError, TypeError):
        monitoring = {'status': 'UNRESOLVED', 'reason': 'MONITORING_RESULT_UNAVAILABLE'}
    observation = 'UNAVAILABLE'
    try:
        samples = private_json(Path(watcher)/'report.json').get('samples', [])
        if samples:
            observation = 'RECORDED'
            for sample in samples:
                if sample.get('source', {}).get('running') is False:
                    observation = 'APPLICATION_STOP_OBSERVED'
                    if app['status'] in ('RUNNING_STARTUP_VERIFIED','RUNNING_EXISTING_IMAGE'):
                        app['status'] = 'WARN'
    except (r.RepairError, OSError, ValueError, KeyError, TypeError):
        pass
    value = {'version': VERSION, 'utc': r.utc(), 'application': app, 'monitoring': monitoring,
             'watcher': observation, 'bridge_processing': 'NOT_ESTABLISHED', 'indexed_visibility': 'UNKNOWN'}
    path = run/('rollback-result.json' if rollback else 'upgrade-result.json')
    r.write_private(path, value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--snapshot', type=Path)
    group.add_argument('--recover', type=Path)
    group.add_argument('--result', type=Path)
    parser.add_argument('--watcher', type=Path)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args(argv)
    if args.result is not None:
        if args.watcher is None: parser.error('--result requires --watcher')
        value = result(r.Docker(), args.result, args.watcher, args.rollback)
        print('Application: '+value['application']['status']+'; monitoring: '+value['monitoring']['status'])
        print('Bridge settlement and Datadog indexed visibility require separate evidence.')
        return 0 if value['application']['status'] in ('RUNNING_STARTUP_VERIFIED','RUNNING_EXISTING_IMAGE') else 1
    warnings.simplefilter('error',getpass.GetPassWarning)
    request_key=lambda:getpass.getpass('Datadog API key missing. Paste the logging API key (hidden): ')
    value = snapshot(r.Docker(), args.snapshot) if args.snapshot is not None else recover(r.Docker(), args.recover,request_key)
    print('Monitoring: '+value['status']+' ('+value['reason']+'). Application recovery is independent.')
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (r.RepairError, OSError, ValueError, KeyError, TypeError) as error:
        print('Monitoring evidence unavailable: '+type(error).__name__+'. Keep the private run directory.', file=sys.stderr)
        sys.exit(1)
