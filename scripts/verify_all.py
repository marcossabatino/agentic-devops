"""Run the complete local M1 acceptance suite and retain a consolidated report."""

import json
from pathlib import Path
import re
import subprocess
from time import monotonic

from app.runtime import now
from app.server import revision

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
REPORT = ARTIFACTS / 'm1-verification.json'

STEPS = (
    ('doctor', ['make', 'doctor']),
    ('unit', ['make', 'test']),
    ('static', ['make', 'verify-static']),
    ('bootstrap_first', ['make', 'bootstrap']),
    ('bootstrap_second', ['make', 'bootstrap']),
    ('durable', ['make', 'verify-durable']),
    ('cluster', ['make', 'verify-cluster']),
    ('network', ['make', 'verify-network']),
    ('observability', ['make', 'verify-observability']),
)

REQUIREMENTS = {
    'A01': ('doctor', 'bootstrap_first', 'cluster'),
    'A02': ('bootstrap_second',),
    'A03': ('cluster',),
    'A04': ('durable', 'cluster'),
    'A05': ('durable', 'cluster', 'observability'),
    'A06': ('network',),
    'A07': ('durable', 'network'),
    'A08': ('durable', 'cluster'),
    'A09': ('durable',),
    'A10': ('durable', 'cluster'),
    'A11': ('observability',),
    'A12': ('cluster',),
}


def execute(name, argv):
    log = ARTIFACTS / 'verify' / (name + '.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    print('+ ' + ' '.join(argv), flush=True)
    started = monotonic()
    with log.open('w') as output:
        process = subprocess.Popen(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, bufsize=1)
        for line in process.stdout:
            print(line, end='', flush=True)
            output.write(line)
        return_code = process.wait()
    return {'status': 'PASS' if return_code == 0 else 'FAIL',
            'return_code': return_code, 'duration_seconds': round(monotonic() - started, 3),
            'log': str(log.relative_to(ROOT))}


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    report = {'timestamp': now(), 'revision': revision(),
              'scope': 'M1 local acceptance A01-A13', 'steps': {}, 'criteria': {},
              'result': 'FAIL'}
    try:
        for name, argv in STEPS:
            result = execute(name, argv)
            report['steps'][name] = result
            if result['status'] != 'PASS':
                break
        second_log = ARTIFACTS / 'verify/bootstrap_second.log'
        if report['steps'].get('bootstrap_second', {}).get('status') == 'PASS':
            text = second_log.read_text()
            idempotent = bool(re.search(r'changed=0\s+unreachable=0\s+failed=0', text))
            report['steps']['bootstrap_second']['idempotent_recap'] = idempotent
            if not idempotent:
                report['steps']['bootstrap_second']['status'] = 'FAIL'
        for criterion, required in REQUIREMENTS.items():
            passed = all(report['steps'].get(name, {}).get('status') == 'PASS'
                         for name in required)
            report['criteria'][criterion] = {'status': 'PASS' if passed else 'FAIL',
                                              'evidence': list(required)}
        report['criteria']['A13'] = {'status': 'NOT_RUN',
                                     'evidence': ['make destroy CONFIRM=agentic-devops']}
        first_twelve_pass = all(item['status'] == 'PASS'
                                for key, item in report['criteria'].items() if key != 'A13')
        report['result'] = 'PASS_WITH_CLEANUP_PENDING' if first_twelve_pass else 'FAIL'
    finally:
        REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{report["result"]}: {REPORT.relative_to(ROOT)}', flush=True)
    return 0 if report['result'] == 'PASS_WITH_CLEANUP_PENDING' else 1


if __name__ == '__main__':
    raise SystemExit(main())
