"""Scoped orchestration for the dedicated Minikube profile; no implicit context."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import secrets

from app.server import revision
from scripts.ci_provenance import validated_commit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config/lab.json').read_text())
PROFILE = CONFIG['profile']
PRIVATE = ROOT / 'data/platform'
KUBECONFIG = PRIVATE / 'kubeconfig'
IDENTITY = PRIVATE / 'cluster-identity.json'


def environment():
    return {**os.environ, 'KUBECONFIG': str(KUBECONFIG),
            'ANSIBLE_LOCAL_TEMP': str(ROOT / '.cache/ansible')}


def command(argv, capture=False, **kwargs):
    return subprocess.run(argv, cwd=ROOT, env=environment(), check=True,
                          text=True, capture_output=capture, **kwargs)


def kubectl(*args, **kwargs):
    return command(['kubectl', '--kubeconfig', str(KUBECONFIG), '--context', PROFILE, *args], **kwargs)


def cluster_identity():
    config = json.loads(kubectl('config', 'view', '--minify', '-o', 'json', capture=True).stdout)
    if config['contexts'][0]['context']['cluster'] != PROFILE:
        raise RuntimeError('The dedicated kubeconfig points to an unexpected cluster.')
    nodes = json.loads(kubectl('get', 'nodes', '-o', 'json', capture=True, timeout=15).stdout)['items']
    if len(nodes) != 1 or nodes[0]['metadata']['name'] != PROFILE:
        raise RuntimeError('Expected exactly the dedicated lab node.')
    uid = kubectl('get', 'namespace', 'kube-system', '-o', 'jsonpath={.metadata.uid}', capture=True, timeout=15).stdout
    return {'profile': PROFILE, 'kube_system_uid': uid}


def guard(record=False):
    actual = cluster_identity()
    if IDENTITY.exists():
        if json.loads(IDENTITY.read_text()) != actual:
            raise RuntimeError('Cluster identity changed; inspect before adopting a new lab cluster.')
    elif record:
        IDENTITY.write_text(json.dumps(actual, indent=2) + '\n')
        IDENTITY.chmod(0o600)
        print('CREATED dedicated cluster identity')
    else:
        raise RuntimeError('Run make bootstrap before platform commands.')


def credentials():
    path = PRIVATE / 'credentials.json'
    if not path.exists():
        existing = kubectl('-n', 'lab-data', 'get', 'pvc', 'data-postgres-0',
                           '--ignore-not-found', '-o', 'name', capture=True).stdout
        if existing:
            raise RuntimeError('Database storage exists without the local credential file. Restore the file before deploying.')
        config = {key: secrets.token_urlsafe(32) for key in
                  ('owner', 'api', 'worker', 'tools', 'orders', 'user_token', 'worker_token', 'orders_token')}
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
            json.dump(config, output)
    path.chmod(0o600)
    return json.loads(path.read_text())


def apply_secret(name, namespace, data):
    document = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
                'metadata': {'name': name, 'namespace': namespace,
                             'labels': {'app.kubernetes.io/part-of': 'agentic-devops',
                                        'app.kubernetes.io/managed-by': 'lab-credentials'}},
                'stringData': data}
    kubectl('apply', '-f', '-', input=json.dumps(document), capture=True)
    print(f'Credential Secret ready: {namespace}/{name} (values redacted)', flush=True)


def image_tag(source_revision=None):
    digest = hashlib.sha256()
    files = [ROOT / 'Dockerfile', ROOT / 'requirements.txt', ROOT / 'config/images.json', *sorted((ROOT / 'app').rglob('*'))]
    for path in files:
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return 'v' + (source_revision or revision()).removesuffix('-dirty')[:12] + '-' + digest.hexdigest()[:12]


def deploy():
    provenance = validated_commit()
    config = credentials()
    for role, namespace in [('api', 'lab-app'), ('worker', 'lab-app'), ('tools', 'lab-tools'), ('orders', 'lab-tools')]:
        config_part = {'database_password': config[role]}
        for token in {'api': ['user_token'], 'worker': ['worker_token'],
                      'tools': ['worker_token', 'orders_token'], 'orders': ['orders_token']}[role]:
            config_part[token] = config[token]
        apply_secret(role + '-credentials', namespace, {'credentials.json': json.dumps(config_part)})
    apply_secret('postgres-credentials', 'lab-data', {'password': config['owner']})
    apply_secret('migrate-credentials', 'lab-data', {'credentials.json': json.dumps({
        'database_password': config['owner'], 'roles': {role: config[role] for role in ('api', 'worker', 'tools', 'orders')}})})
    images = json.loads((ROOT / 'config/images.json').read_text())
    tag = image_tag(provenance['source_revision'])
    command(['docker', 'build', '--build-arg', 'PYTHON_IMAGE=' + images['python'],
             '-t', 'agentic-devops:' + tag, '.'])
    command(['minikube', '-p', PROFILE, 'image', 'load', 'agentic-devops:' + tag])
    # Pull the immutable PostgreSQL image in the VM; no mutable tag is deployed.
    command(['helm', 'upgrade', '--install', 'agentic-devops', 'charts/app',
             '--kubeconfig', str(KUBECONFIG), '--kube-context', PROFILE, '-n', 'lab-app',
             '--set-string', 'image.tag=' + tag,
             '--set-string', 'postgres.image=' + images['postgres'],
             '--set-string', 'sourceRevision=' + provenance['source_revision'],
             '--wait', '--wait-for-jobs', '--timeout', '8m', '--history-max', '3'])
    build = {'image': 'agentic-devops:' + tag, **provenance,
             'cluster': json.loads(IDENTITY.read_text()), 'postgres_image': images['postgres'],
             'image_id': command(['docker', 'image', 'inspect', '--format', '{{.Id}}',
                                  'agentic-devops:' + tag], capture=True).stdout.strip()}
    (PRIVATE / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
    print('Deployment ready. Use make ui; user_token is in data/platform/credentials.json.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bootstrap', 'record-identity', 'guard', 'infra-init', 'infra-plan', 'infra-apply', 'deploy', 'ui', 'dashboards'])
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.action == 'bootstrap':
        (ROOT / '.cache/ansible').mkdir(parents=True, exist_ok=True)
        command(['ansible-playbook', '-i', 'ansible/inventory.ini', 'ansible/bootstrap.yml'])
    else:
        guard(record=args.action == 'record-identity')
        if args.action == 'infra-init':
            command(['tofu', '-chdir=infra/local', 'init', '-input=false'])
        elif args.action == 'infra-plan':
            command(['tofu', '-chdir=infra/local', 'init', '-input=false'])
            command(['tofu', '-chdir=infra/local', 'plan', '-input=false', '-out=lab.tfplan'])
        elif args.action == 'infra-apply':
            command(['tofu', '-chdir=infra/local', 'apply', '-input=false', 'lab.tfplan'])
        elif args.action == 'deploy':
            deploy()
        elif args.action == 'dashboards':
            kubectl('-n', 'lab-observability', 'port-forward', '--address=127.0.0.1', 'service/grafana', f'{args.port}:3000')
        elif args.action == 'ui':
            kubectl('-n', 'lab-app', 'port-forward', '--address=127.0.0.1', 'service/api', f'{args.port}:8080')


if __name__ == '__main__':
    main()
