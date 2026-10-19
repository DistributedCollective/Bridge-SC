#!/usr/bin/env python3
"""Integrate the verified Datadog repair and state retention into ETH upgrades."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import dd_agent_recovery as r

VERSION = '1.1.1'


def stable(agent):
    return {'id': agent['id'], 'image': agent['image'], 'started': agent['state']['StartedAt'],
            'env_fingerprint': agent.get('env_fingerprint'),
            'running': agent['state'].get('Running'), 'paused': agent['state'].get('Paused', False),
            'mounts': sorted(json.dumps(m, sort_keys=True) for m in agent['mounts'])}


def require_same_source(before, after):
    for field in ('id','image','log_path','log_config','labels','mounts'):
        left,right=before.get(field),after.get(field)
        if field=='mounts':
            left=sorted(json.dumps(x,sort_keys=True) for x in left or [])
            right=sorted(json.dumps(x,sort_keys=True) for x in right or [])
        if left != right:raise r.RepairError('ETH source identity/layout changed during Agent operation')
    if any(before['state'].get(k)!=after['state'].get(k) for k in ('StartedAt','Running','Paused','Status')):
        raise r.RepairError('ETH source process changed during Agent operation')


def read_state(docker, work, require_cursor=True, layout_source=None, allow_stopped=False):
    work = r.safe_path(work)
    agent = docker.inspect('datadog-agent', agent=True)
    source = docker.inspect('bridge-sc_federation_1')
    reference = layout_source or source
    mapped, volume = r.validate_layout(agent, reference)
    if source.get('log_path'):
        r.validate_layout(agent, source)
    if layout_source is None and source['state'].get('Paused'):
        raise r.RepairError('ETH source is paused; no service stopped')
    log_root = str(Path(reference['log_path']).parent.parent)
    covering = [m for m in agent['mounts'] if mapped == m['Destination'].rstrip('/') or mapped.startswith(m['Destination'].rstrip('/') + '/')]
    backing = max(covering, key=lambda m: len(m['Destination']))
    prefix = backing.get('Source', '').rstrip('/')
    if backing.get('Type') != 'bind' or not (log_root == prefix or log_root.startswith(prefix + '/')):
        raise r.RepairError('Agent log mount does not cover future container directories; no service stopped')
    service = (agent.get('labels') or {}).get('com.docker.compose.service', 'datadog')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', service):
        raise r.RepairError('Unsupported Agent Compose service name; no service stopped')
    if agent['state'].get('Paused') or (not agent['state'].get('Running') and not (allow_stopped and agent['state'].get('Status') == 'exited')):
        raise r.RepairError('Datadog must be running or a supported stopped Agent; recover any saved Agent attempt first')
    r.ensure_output_outside_source(work, source)
    r.ensure_output_outside_source(work, reference)
    work.mkdir(mode=0o700)
    path = r.config_path(docker, agent)
    raw = docker.copy_out(agent['id'], path, work / 'config.private.yaml')
    code = 'import json,yaml,subprocess;print(json.dumps({"config":yaml.safe_load(open("/input.yaml")),"version":subprocess.check_output(["agent","version"]).decode()}))'
    parsed = json.loads(docker.helper(agent['image'], code, [(str(work / 'config.private.yaml'), '/input.yaml')]))
    version=r.validate_agent_version(parsed.get('version'), agent['image'])
    config = parsed['config']
    env = dict(x.split('=', 1) for x in agent.get('env', []) if '=' in x)
    run_path = env.get('DD_LOGS_CONFIG_RUN_PATH') or (config.get('logs_config') or {}).get('run_path') or '/opt/datadog-agent/run'
    if not isinstance(run_path, str) or not run_path.startswith('/') or '..' in Path(run_path).parts:
        raise r.RepairError('Unsupported Agent registry path; no service stopped')
    persistent = run_path.rstrip('/') == r.PERSISTENT_PATH
    file_env=env.get('DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE')
    file_enabled=file_env.lower()=='true' if file_env is not None else (config.get('logs_config') or {}).get('docker_container_use_file') is True
    if persistent and version=='7.32.4' and not file_enabled:
        raise r.RepairError('Persistent legacy Agent has not enabled file collection; no Agent started')
    validation_env = dict(env)
    if persistent:
        validation_env.pop('DD_LOGS_CONFIG_RUN_PATH', None)
    r.persistent_config(config, validation_env)
    enabled = env.get('DD_LOGS_ENABLED')
    if enabled is not None and enabled.lower() not in ('true', 'false'):
        raise r.RepairError('Unsupported Datadog log-enabled setting; no service stopped')
    if not (enabled.lower() == 'true' if enabled is not None else config.get('logs_enabled') is True):
        raise r.RepairError('Datadog log collection is disabled; no service stopped')
    discovery = r.check_discovery(docker, agent, reference, config, env, work / 'discovery.private.tar')
    if layout_source is not None and source['id'] != reference['id']:
        actual_discovery = r.check_discovery(docker, agent, source, config, env, work / 'replacement-discovery.private.tar')
        if actual_discovery['sha256'] != discovery['sha256']:
            raise r.RepairError('Agent integrations changed during replacement discovery check')
    registry = None
    for attempt in range(3):
        data = docker.copy_out(agent['id'], run_path.rstrip('/') + '/registry.json', work / 'registry.private.json')
        try:
            registry = json.loads(data); break
        except ValueError:
            if attempt == 2: raise r.RepairError('Live Agent registry could not be sampled consistently') from None
            time.sleep(.2)
    if type(registry.get('Version')) is not int or registry['Version'] != 2 or not isinstance(registry.get('Registry'), dict):
        raise r.RepairError('Unsupported Agent registry schema; no service stopped')
    initialization=r.initialization_state(docker,agent,volume) if persistent else None
    if persistent:
        r.ensure_file_collection(registry, source['id'], config, env)
        r.require_initialization_ack(initialization,registry)
    key = 'file:' + mapped
    entry = registry['Registry'].get(key)
    offset = entry.get('Offset') if isinstance(entry, dict) else None
    if persistent and require_cursor and (not isinstance(offset, str) or not re.fullmatch(r'[0-9]{1,19}', offset)):
        raise r.RepairError('Current source has no verified file checkpoint; no service stopped')
    if not persistent:
        existing = json.loads(docker.helper(agent['image'],
            'import json,os;print(json.dumps({"exists":os.path.lexists("/agent-logs/bridge-log-state")}))',
            [(volume, '/agent-logs', 'volume')], user='0:0', read_search=True))
        if existing != {'exists': False}:
            raise r.RepairError('Existing persistent destination needs saved-packet recovery; no service stopped')
        if not source['state'].get('Running') or source['state'].get('Paused'):
            raise r.RepairError('Start/recover the existing ETH node before its Datadog cutover; no service stopped')
        snapshot = r.file_snapshot(docker, agent, source)
        migrated = r.recovery_registry(registry, mapped, source['id'], snapshot['offset'], r.utc(), allow_unregistered=r.configured_collect_all(config,env))
        r.ensure_file_collection(migrated, source['id'], r.persistent_config(config, validation_env), env)
    if r.sha(docker.copy_out(agent['id'], path, work / 'config-rechecked.private.yaml')) != r.sha(raw):
        raise r.RepairError('Agent main configuration changed during preflight; no service stopped')
    again = r.check_discovery(docker, agent, reference, config, env, work / 'discovery-rechecked.private.tar')
    if again['sha256'] != discovery['sha256']:
        raise r.RepairError('Agent integrations changed during preflight; no service stopped')
    if stable(docker.inspect('datadog-agent', agent=True)) != stable(agent):
        raise r.RepairError('Agent changed during preflight; no service stopped')
    require_same_source(source,docker.inspect('bridge-sc_federation_1'))
    return {'agent': stable(agent), 'agent_version': parsed['version'].strip(), 'source_id': source['id'],
            'persistent': persistent, 'volume': volume, 'config_sha256': r.sha(raw),
            'service': service, 'discovery_sha256': discovery['sha256'], 'source_layout': reference,
            'source_started': source['state'].get('StartedAt'),
            'cursor_key': key, 'cursor_offset': int(offset) if isinstance(offset, str) and offset.isdecimal() else None,
            'registry': registry, 'observed_source': source, 'initialization':initialization}


def inspect(docker, output):
    state = read_state(docker, output, allow_stopped=True)
    result = {'utc': r.utc(), 'agent_repair_needed': not state['persistent'], 'agent_version': state['agent_version'], 'agent_running': state['agent']['running']}
    r.write_private(Path(output) / 'report.json', result)
    print('Datadog preflight passed; repair needed:', result['agent_repair_needed'])
    return result


def capture(docker, output):
    output = r.safe_path(output)
    # read_state validates containment before creating this directory.
    state = read_state(docker, output, allow_stopped=True)
    repaired = False
    if not state['persistent']:
        fresh = docker.inspect('datadog-agent', agent=True)
        current_source = docker.inspect('bridge-sc_federation_1')
        if current_source['id'] != state['source_id'] or current_source['state'].get('StartedAt') != state['source_started'] or not current_source['state'].get('Running') or current_source['state'].get('Paused'):
            raise r.RepairError('ETH source changed before cutover; no service stopped')
        if stable(fresh) != state['agent']:
            raise r.RepairError('Agent changed before cutover; no service stopped')
        if fresh['state'].get('Running'):docker.call(['stop', fresh['id']], timeout=35)
        repair = output / 'repair'
        print('Repairing Datadog before the federator is stopped.')
        try:
            r.prepare(docker, repair)
            r.apply(docker, repair)
        except Exception:
            print('Datadog repair evidence:', repair, file=sys.stderr)
            print('Federator upgrade has not stopped the node. Send the error/report before retrying.', file=sys.stderr)
            raise
        state = read_state(docker, output / 'after-repair')
        repaired = True
    if not state['agent']['running']:
        # An already-persistent stopped Agent resumes its retained cursor unchanged.
        original = docker.inspect('datadog-agent', agent=True)
        if stable(original) != state['agent']:
            raise r.RepairError('Agent changed before retained-checkpoint restart')
        source = docker.inspect('bridge-sc_federation_1')
        if source['id'] != state['source_id'] or source['state'].get('StartedAt') != state['source_started'] or not source['state'].get('Running') or source['state'].get('Paused'):
            raise r.RepairError('ETH source changed before retained-checkpoint restart')
        r.write_private(output / 'retained-start.private.json', {'agent':state['agent'], 'cursor_key':state['cursor_key'], 'cursor_offset':state['cursor_offset']})
        try:
            docker.call(['start', original['id']])
            resumed = read_state(docker, output / 'after-retained-start')
            expected = dict(state['agent'])
            expected.update(started=resumed['agent']['started'], running=True)
            if (resumed['agent'] != expected or resumed['config_sha256'] != state['config_sha256'] or
                    resumed['discovery_sha256'] != state['discovery_sha256'] or
                    resumed['cursor_offset'] < state['cursor_offset'] or resumed['volume'] != state['volume']):
                raise r.RepairError('Retained Agent restart changed identity/configuration or regressed its cursor')
            require_same_source(state['observed_source'],resumed['observed_source'])
            if resumed['cursor_key'] != state['cursor_key']:
                raise r.RepairError('Retained Agent source checkpoint changed during restart')
            state = resumed
        except Exception:
            docker.call(['stop', original['id']], timeout=35, optional=True)
            raise
    initialization=state.get('initialization')
    if initialization is not None and initialization['Acknowledged'] is None:
        agent=docker.inspect('datadog-agent',agent=True)
        if stable(agent)!=state['agent']:raise r.RepairError('Agent changed before initialization acknowledgement')
        if initialization['SourceId']!=state['source_id'] or initialization['Path']!=state['cursor_key'][5:]:
            raise r.RepairError('Pending initialization belongs to a different source')
        snapshot=r.file_snapshot(docker,agent,state['observed_source'])
        r.cutover_registry(state['registry'],initialization['Path'],snapshot['offset'],r.utc())
        state['initialization']=r.complete_initialization(docker,agent,state['volume'],initialization,state['cursor_offset'],output)
        require_same_source(state['observed_source'],docker.inspect('bridge-sc_federation_1'))
    if stable(docker.inspect('datadog-agent',agent=True)) != state['agent']:
        raise r.RepairError('Agent changed before its recovery state could be captured')
    service = state['service']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', service):
        raise r.RepairError('Unsupported Agent Compose service name')
    override = {'services': {service: {'environment': {'DD_LOGS_CONFIG_RUN_PATH': r.PERSISTENT_PATH, 'DD_LOGS_CONFIG_DOCKER_CONTAINER_USE_FILE': 'true'},
                'volumes': [{'type': 'volume', 'source': 'bridge_dd_state', 'target': '/var/log/datadog'}]}},
                'volumes': {'bridge_dd_state': {'external': True, 'name': state['volume']}}}
    state.pop('registry')
    state.update(version=VERSION, utc=r.utc(), agent_repaired_now=repaired)
    r.write_private(output / 'manifest.json', state)
    r.write_private(output / 'agent-state.override.private.json', override)
    r.write_private(output / 'report.json', {'utc': r.utc(), 'agent_repaired_now': repaired, 'agent_state_captured': True})
    print('Datadog checkpoint and existing-volume override saved privately:', output)
    return state


def verify(docker, output, allow_handoff=False):
    output = r.safe_path(output, existing=True)
    path = output / 'manifest.json'
    if path.is_symlink(): raise r.RepairError('Unsafe Datadog state manifest')
    old = r.read_json(path)
    work = output / ('verify-' + r.secrets.token_hex(6))
    current = read_state(docker, work, require_cursor=False, layout_source=old['source_layout'])
    if current['agent'] != old['agent'] or current['volume'] != old['volume'] or not current['persistent'] or current['config_sha256'] != old['config_sha256'] or current['discovery_sha256'] != old['discovery_sha256']:
        raise r.RepairError('Datadog identity/process/config/state volume changed during the application operation')
    entry = current['registry']['Registry'].get(old['cursor_key'])
    handoff = False
    if entry is not None:
        value = entry.get('Offset') if isinstance(entry, dict) else None
        if not isinstance(value, str) or not value.isdecimal() or int(value) < old['cursor_offset']:
            raise r.RepairError('Datadog previous source checkpoint regressed')
    else:
        source = current['observed_source']
        if not allow_handoff or source['id'] == old['source_id'] or not source['state'].get('Running') or source['state'].get('Paused'):
            raise r.RepairError('Datadog captured source checkpoint absent; explicit replacement handoff required')
        mounts = lambda value: sorted(json.dumps(m, sort_keys=True) for m in value['mounts'])
        if mounts(source) != mounts(old['source_layout']):
            raise r.RepairError('Datadog replacement source mounts changed')
        agent = docker.inspect('datadog-agent', agent=True)
        mapped, volume = r.validate_layout(agent, source)
        selected = current['registry']['Registry'].get('file:' + mapped)
        offset = selected.get('Offset') if isinstance(selected, dict) else None
        if not isinstance(offset, str) or not re.fullmatch(r'[0-9]{1,19}', offset) or int(offset) <= 0:
            raise r.RepairError('Datadog replacement source checkpoint unavailable')
        snapshot = r.file_snapshot(docker, agent, source)
        r.cutover_registry(current['registry'], mapped, snapshot['offset'], r.utc())
        if stable(docker.inspect('datadog-agent', agent=True)) != current['agent']:
            raise r.RepairError('Datadog Agent changed during replacement verification')
        again = docker.inspect('bridge-sc_federation_1')
        if any(again.get(k) != source.get(k) for k in ('id', 'image', 'log_path', 'labels')) or mounts(again) != mounts(source) or again['state'].get('StartedAt') != source['state'].get('StartedAt') or not again['state'].get('Running') or again['state'].get('Paused'):
            raise r.RepairError('Datadog replacement source changed during verification')
        handoff = True
    r.write_private(work / 'report.json', {'utc': r.utc(), 'agent_unchanged': True, 'state_retained': entry is not None,
                                         'previous_source_cursor_present': entry is not None,
                                         'source_handoff_verified': handoff, 'prior_source_delivery': 'not verified'})
    print('Datadog replacement checkpoint verified; previous source cursor retired, prior delivery not verified.'
          if handoff else 'Datadog Agent and retained source checkpoint are unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect', type=Path)
    group.add_argument('--capture', type=Path)
    group.add_argument('--verify', type=Path)
    parser.add_argument('--allow-source-handoff', action='store_true', help='verify an intentional running replacement when the previous cursor has retired')
    args = parser.parse_args()
    if args.allow_source_handoff and not args.verify: parser.error('--allow-source-handoff requires --verify')
    try:
        if os.getuid() != 1000 or not sys.platform.startswith('linux'):
            raise r.RepairError('Run as Linux deployment user UID1000')
        action, path = next((name, getattr(args, name)) for name in ('inspect', 'capture', 'verify') if getattr(args, name))
        if action == 'verify': verify(r.Docker(), path, allow_handoff=args.allow_source_handoff)
        else: globals()[action](r.Docker(), path)
        return 0
    except (r.RepairError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print('Datadog upgrade check failed: ' + (str(exc) if isinstance(exc, r.RepairError) else type(exc).__name__), file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())
