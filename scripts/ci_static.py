"""Cluster-free infrastructure and manifest checks shared by local runs and CI."""

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*argv):
    print('+ ' + ' '.join(str(part) for part in argv), flush=True)
    subprocess.run(argv, cwd=ROOT, check=True)


def main():
    run('ansible-lint', 'ansible/bootstrap.yml')
    run('tofu', 'fmt', '-check', '-recursive', 'infra/local')
    run('tofu', '-chdir=infra/local', 'init', '-backend=false', '-input=false', '-lockfile=readonly')
    run('tofu', '-chdir=infra/local', 'validate')
    images = json.loads((ROOT / 'config/images.json').read_text())
    run('helm', 'lint', 'charts/app', '--set-string', 'postgres.image=' + images['postgres'])
    values = {
        'images': json.loads((ROOT / 'config/observability-images.json').read_text()),
        'configs': {name: (ROOT / f'observability/{name}.yaml').read_text()
                    for name in ('collector', 'prometheus', 'tempo', 'grafana')},
        'dashboard': (ROOT / 'observability/dashboard.json').read_text(),
    }
    with tempfile.TemporaryDirectory(prefix='lab-ci-static-') as directory:
        path = Path(directory) / 'values.json'
        path.write_text(json.dumps(values))
        run('helm', 'lint', 'charts/observability', '-f', str(path))
        run('helm', 'template', 'lab-observability', 'charts/observability', '-n',
            'lab-observability', '-f', str(path), '--output-dir', str(Path(directory) / 'rendered'))
    print('PASS cluster-free infrastructure and manifest validation', flush=True)


if __name__ == '__main__':
    main()
