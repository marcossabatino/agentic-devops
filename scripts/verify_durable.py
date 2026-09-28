"""Run PostgreSQL acceptance contracts and retain a sanitized local report."""

import json
import os
from pathlib import Path
import unittest

from app.runtime import now
from app.server import revision


def main():
    os.environ['LAB_POSTGRES_TESTS'] = '1'
    suite = unittest.defaultTestLoader.discover('tests', pattern='test_durable.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        'timestamp': now(), 'revision': revision(), 'scope': 'T03 local PostgreSQL and HTTP contracts',
        'result': 'PASS' if result.wasSuccessful() and result.testsRun and not result.skipped else 'FAIL',
        'tests_run': result.testsRun,
        'failures': [str(test) for test, _ in result.failures],
        'errors': [str(test) for test, _ in result.errors],
        'skipped': [str(test) for test, _ in result.skipped],
        'criteria': {'A04': 'Local durable execution', 'A05': 'Bounded dependency failure; distributed trace deferred to T06',
                     'A07': 'Application authorization over allowed localhost connections',
                     'A08': 'Approval binding', 'A09': 'Transactional simulated idempotency',
                     'A10': 'Durable step limit'},
        'not_validated': ['Kubernetes', 'NetworkPolicy', 'distributed traces', 'external side effects'],
    }
    path = Path('artifacts/t03-durable.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{report["result"]}: {path}')
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
