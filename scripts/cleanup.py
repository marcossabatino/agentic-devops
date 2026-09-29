"""Delete only the dedicated lab profile after identity and preservation checks."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from app.runtime import now
from scripts import lab_platform

ROOT = lab_platform.ROOT
PROFILE = lab_platform.PROFILE
ARTIFACTS = ROOT / 'artifacts'
REPORT = ARTIFACTS / 'a13-cleanup.json'


def host_output(*argv, allow_empty=False):
    env = dict(os.environ)
    env.pop('KUBECONFIG', None)
    result = subprocess.run(argv, cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode and not allow_empty:
        raise RuntimeError('Unable to inspect host configuration with ' + ' '.join(argv) + '.')
    return result.stdout.strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def profiles():
    document = json.loads(lab_platform.command(
        ['minikube', 'profile', 'list', '-o', 'json'], capture=True).stdout)
    return {item['Name']: item for group in ('valid', 'invalid') for item in document.get(group, [])}


def host_contexts():
    config_text = host_output('kubectl', 'config', 'view', '--raw', '-o', 'json')
    config = json.loads(config_text or '{}')
    return {'names': sorted(item['name'] for item in config.get('contexts', [])),
            'current': config.get('current-context', ''), 'config_sha256': digest(config)}


def validate_target(inventory):
    if not lab_platform.IDENTITY.exists():
        raise RuntimeError('The recorded cluster identity is missing; refusing cleanup.')
    identity = json.loads(lab_platform.IDENTITY.read_text())
    if identity.get('profile') != PROFILE:
        raise RuntimeError('The recorded identity does not name the dedicated profile.')
    target = inventory.get(PROFILE)
    if not target:
        raise RuntimeError('The dedicated lab profile does not exist.')
    config = target.get('Config', {})
    expected = {'Name': PROFILE, 'Driver': lab_platform.CONFIG['driver'],
                'CPUs': lab_platform.CONFIG['cpus'], 'Memory': lab_platform.CONFIG['memory_mib'],
                'Network': lab_platform.CONFIG['network']}
    if any(config.get(key) != value for key, value in expected.items()):
        raise RuntimeError('The profile configuration differs from the dedicated lab contract.')
    kubernetes = config.get('KubernetesConfig', {}).get('KubernetesVersion', '').removeprefix('v')
    if kubernetes != lab_platform.CONFIG['kubernetes']:
        raise RuntimeError('The profile Kubernetes version differs from the lab contract.')
    if target.get('Status') == 'Running':
        lab_platform.guard()
    elif target.get('Status') != 'Stopped':
        raise RuntimeError('The dedicated profile must be running or stopped before cleanup.')
    return identity, target


def unrelated_profiles(inventory):
    return {name: {'Name': item.get('Name'), 'Status': item.get('Status'),
                   'Config': item.get('Config', {})}
            for name, item in inventory.items() if name != PROFILE}


def remove_local_runtime():
    allowed_directories = (lab_platform.PRIVATE, ROOT / 'infra/local/.terraform',
                           ROOT / '.cache/ansible')
    allowed_files = [ROOT / 'infra/local/lab.tfplan']
    allowed_files.extend((ROOT / 'infra/local').glob('terraform.tfstate*'))
    removed = []
    for path in allowed_directories:
        if path.exists():
            shutil.rmtree(path)
            removed.append(str(path.relative_to(ROOT)))
    for path in allowed_files:
        if path.exists() and path.parent.resolve() == (ROOT / 'infra/local').resolve():
            path.unlink()
            removed.append(str(path.relative_to(ROOT)))
    return sorted(set(removed))


def update_verification():
    target = ARTIFACTS / 'm1-verification.json'
    if not target.exists():
        return None
    report = json.loads(target.read_text())
    report.setdefault('criteria', {})['A13'] = {
        'status': 'PASS', 'evidence': [str(REPORT.relative_to(ROOT))]}
    report['result'] = ('PASS' if all(item.get('status') == 'PASS'
                                     for item in report['criteria'].values()) else 'FAIL')
    report['cleanup_timestamp'] = now()
    target.write_text(json.dumps(report, indent=2) + '\n')
    return report['result']


def destroy(confirm):
    if confirm != PROFILE:
        raise RuntimeError(f'Re-run with --confirm {PROFILE} after reviewing the target profile.')
    before_profiles = profiles()
    identity, target = validate_target(before_profiles)
    before_contexts = host_contexts()
    unrelated = unrelated_profiles(before_profiles)
    lab_platform.command(['minikube', 'delete', '-p', PROFILE])
    after_profiles = profiles()
    after_contexts = host_contexts()
    if PROFILE in after_profiles:
        raise RuntimeError('The dedicated profile still exists after deletion.')
    after_unrelated = unrelated_profiles(after_profiles)
    if digest(unrelated) != digest(after_unrelated):
        raise RuntimeError('An unrelated Minikube profile changed during cleanup.')
    if before_contexts != after_contexts:
        raise RuntimeError('The host Kubernetes contexts changed during cleanup.')
    removed = remove_local_runtime()
    report = {'timestamp': now(), 'scope': 'A13 dedicated local lab cleanup', 'result': 'PASS',
              'removed_profile': PROFILE, 'removed_profile_status': target.get('Status'),
              'identity_sha256': digest(identity), 'preserved_profiles': sorted(unrelated),
              'preserved_profile_state_sha256': digest(unrelated),
              'preserved_host_contexts': before_contexts, 'removed_local_paths': removed}
    ARTIFACTS.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    report['consolidated_result'] = update_verification()
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: removed only Minikube profile {PROFILE}; preserved '
          f'{len(unrelated)} unrelated profile(s) and {len(before_contexts["names"])} host context(s).')
    print('Evidence: ' + str(REPORT.relative_to(ROOT)))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', required=True)
    args = parser.parse_args()
    destroy(args.confirm)


if __name__ == '__main__':
    main()
