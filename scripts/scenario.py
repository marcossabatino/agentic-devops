"""Activate a scenario for new UI sessions and execute one bounded diagnosis."""
import argparse
import json
from pathlib import Path
from app.contracts import SCENARIOS, uuid_text
from scripts.lab_platform import PRIVATE, guard, kubectl
from scripts.verify_cluster import port_forward, request, poll


def activate(case):
    guard()
    token = json.loads((PRIVATE / 'credentials.json').read_text())['user_token']
    with port_forward('lab-app', 'service/api') as port:
        status, body = request(port, '/api/scenario', token, {'scenario': case})
        if status != 200:
            raise RuntimeError('Scenario activation failed.')
        status, run = request(port, '/api/runs', token, {'scenario': case, 'question': 'Exercise the selected lab scenario.'})
        if status != 202:
            raise RuntimeError('Scenario diagnosis was not accepted.')
        run = poll(port, run['run_id'], token)
    report = {key: run.get(key) for key in ('run_id', 'trace_id', 'scenario', 'status', 'outcome', 'error', 'step_count', 'attempts')}
    path = Path('artifacts/scenario-latest.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return report


def json_logs(raw):
    """kubectl --all-pods adds a pod prefix even when --prefix=false is passed."""
    for line in raw.splitlines():
        if line.startswith('[pod/'):
            line = line.partition('] ')[2]
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            yield item


def logs(run_id):
    guard()
    run_id = uuid_text(run_id)
    count = 0
    for namespace, name in [('lab-app', 'api'), ('lab-app', 'worker'), ('lab-tools', 'tools'), ('lab-tools', 'orders')]:
        raw = kubectl('-n', namespace, 'logs', 'deployment/' + name, '--all-pods=true', '--since=24h', '--tail=10000',
                      '--prefix=false', capture=True, timeout=20).stdout
        for item in json_logs(raw):
            if item.get('run_id') == run_id:
                print(json.dumps(item))
                count += 1
    if not count:
        print('No retained pod logs match this run. Pod replacement or log rotation may have removed them.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=SCENARIOS, default='healthy')
    parser.add_argument('--logs')
    args = parser.parse_args()
    logs(args.logs) if args.logs else activate(args.case)
