#!/usr/bin/env python3
"""Keep ETH application replacement independent from guarded monitoring recovery."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

import dd_agent_recovery as r
import federator_datadog_upgrade as u

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
        code = 'import json,yaml;print(json.dumps(yaml.safe_load(open("/input.yaml"))))'
        config = json.loads(docker.helper(agent['image'], code, [(str(output/'config.private.yaml'), '/input.yaml')]))
        env = dict(x.split('=', 1) for x in agent.get('env', []) if '=' in x)
        run_path = env.get('DD_LOGS_CONFIG_RUN_PATH') or (config.get('logs_config') or {}).get('run_path') or '/opt/datadog-agent/run'
        if not isinstance(run_path, str) or not run_path.startswith('/') or '..' in Path(run_path).parts:
            raise r.RepairError('Unsupported Agent checkpoint path')
        data = docker.copy_out(agent['id'], run_path.rstrip('/')+'/registry.json', output/'registry.private.json')
        value['registry'] = u.registry_sample_metadata(data)
        if u.stable(docker.inspect('datadog-agent', agent=True)) != value['agent']:
            raise r.RepairError('Agent changed during snapshot')
        value['backup'] = 'COMPLETE'
    except (r.RepairError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        value['failure_type'] = type(error).__name__
    r.write_private(output/'snapshot.json', value)
    return report(output, reason='NOT_ATTEMPTED', **value)


def recover(docker, output):
    output = r.safe_path(output, existing=True)
    value = private_json(output/'snapshot.json')
    common = {'backup': value.get('backup', 'UNAVAILABLE')}
    if value.get('backup') != 'COMPLETE':
        return report(output, reason='MONITORING_BACKUP_INCOMPLETE', **common)
    registry = value.get('registry', {})
    if not registry.get('valid_json'):
        return report(output, reason='INVALID_REGISTRY', **common)
    if registry.get('schema') != 2 or registry.get('entries') is None:
        return report(output, reason='UNSUPPORTED_REGISTRY', **common)
    if (output/'recovery-started.json').exists():
        return report(output, reason='PREVIOUS_RECOVERY_ATTEMPT', **common)
    try:
        agent = docker.inspect('datadog-agent', agent=True)
        if u.stable(agent) != value['agent']:
            return report(output, reason='AGENT_CHANGED', **common)
        r.write_private(output/'recovery-started.json', {'utc': r.utc()})
        # Existing cutover/ACK guards preserve every other collected source.
        # A malformed/unknown shared registry is never reconstructed or reset.
        u.capture(docker, output/'state')
        u.verify(docker, output/'state')
        agent = docker.inspect('datadog-agent', agent=True)
        return report(output, status='TRACKING_CONFIGURED', reason='GUARDED_RECOVERY_VERIFIED',
                      agent=u.stable(agent), source_delivery='UNKNOWN', **common)
    except (r.RepairError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return report(output, reason='RECOVERY_INCOMPLETE', failure_type=type(error).__name__, **common)


def result(docker, run, watcher, rollback=False):
    run = r.safe_path(run, existing=True)
    app = {'status': 'UNKNOWN'}
    try:
        journal = private_json(run/('rollback-startup-key-cleanup.json' if rollback else 'startup-key-cleanup.json'))
        source = docker.inspect('bridge-sc_federation_1')
        same = (journal.get('source_id'), journal.get('image_id'), journal.get('started_utc')) == (
            source['id'], source['image'], source['state']['StartedAt'])
        healthy = source['state'].get('Running') is True and not source['state'].get('Paused') and same
        app['status'] = 'RUNNING_STARTUP_VERIFIED' if healthy and journal.get('outcome') == 'running_startup_key_removed' else 'FAIL'
    except (r.RepairError, OSError, ValueError, KeyError, TypeError):
        pass
    monitoring = {'status': 'UNRESOLVED', 'reason': 'NO_MONITORING_RESULT'}
    try:
        saved = private_json(run/'monitoring/report.json')
        monitoring = {k: saved[k] for k in ('status', 'reason', 'indexed_visibility') if k in saved}
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
                    if app['status'] == 'RUNNING_STARTUP_VERIFIED':
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
        return 0 if value['application']['status'] == 'RUNNING_STARTUP_VERIFIED' else 1
    value = snapshot(r.Docker(), args.snapshot) if args.snapshot is not None else recover(r.Docker(), args.recover)
    print('Monitoring: '+value['status']+' ('+value['reason']+'). Application recovery is independent.')
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (r.RepairError, OSError, ValueError, KeyError, TypeError) as error:
        print('Monitoring evidence unavailable: '+type(error).__name__+'. Keep the private run directory.', file=sys.stderr)
        sys.exit(1)
