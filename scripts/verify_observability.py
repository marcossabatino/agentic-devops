"""Prove T06 with live traces, retained JSON logs and Grafana datasource queries."""

import base64
import json
import time
from urllib.parse import urlencode

from app.runtime import now
from scripts.lab_platform import PRIVATE, ROOT, guard, kubectl
from scripts.verify_cluster import poll, port_forward, request
from scripts.scenario import json_logs

COMPONENTS = [('lab-app', 'api'), ('lab-app', 'worker'), ('lab-tools', 'tools'), ('lab-tools', 'orders')]


def eventually(function, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = function()
        if value:
            return value
        time.sleep(1)
    raise AssertionError('Telemetry did not become available within the bounded wait.')


def spans_from(document):
    result = []
    for batch in document.get('batches', document.get('resourceSpans', [])):
        attributes = {a['key']: a['value'].get('stringValue') for a in batch.get('resource', {}).get('attributes', [])}
        for scope in batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', [])):
            for span in scope.get('spans', []):
                result.append({**span, 'service': attributes.get('service.name')})
    return result


def hex_id(value):
    # Tempo's protobuf JSON encodes byte identifiers as base64; some versions use hex.
    if len(value) in (16, 32) and all(c in '0123456789abcdef' for c in value.lower()):
        return value.lower()
    return base64.b64decode(value).hex()


def verify():
    guard()
    target = ROOT / 'artifacts/t06-observability.json'
    target.parent.mkdir(exist_ok=True)
    checks, runs = {}, {}
    report = {'timestamp': now(), 'scope': 'T06 live Kubernetes observability',
              'checks': checks, 'runs': runs, 'result': 'FAIL'}

    def check(name, condition):
        checks[name] = bool(condition)
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition:
            raise AssertionError(name)

    try:
        config = json.loads((PRIVATE / 'credentials.json').read_text())
        token = config['user_token']
        report['build'] = json.loads((PRIVATE / 'build.json').read_text())
        for name in ('collector', 'prometheus', 'tempo', 'grafana'):
            kubectl('-n', 'lab-observability', 'rollout', 'status', 'deployment/' + name,
                    '--timeout=120s', capture=True, timeout=125)
        check('observability_workloads_ready', True)
        services = json.loads(kubectl('-n', 'lab-observability', 'get', 'services', '-o', 'json', capture=True).stdout)['items']
        check('observability_services_internal', len(services) == 4 and all(s['spec']['type'] == 'ClusterIP' for s in services))
        with port_forward('lab-app', 'service/api') as api, port_forward('lab-observability', 'service/grafana', 3000) as grafana:
            # Use the real Grafana proxy: this also tests Grafana -> Prometheus/Tempo policies.
            def query(expression):
                status, body = request(grafana, '/api/datasources/proxy/uid/prometheus/api/v1/query?' + urlencode({'query': expression}))
                if status != 200 or body.get('status') != 'success':
                    return []
                return body['data']['result']

            eventually(lambda: len([v for v in query('up{job="lab"}') if v['value'][1] == '1']) == 4)
            check('four_live_prometheus_targets_via_grafana', True)
            check('scenario_requires_authentication', request(api, '/api/scenario', payload={'scenario': 'healthy'})[0] == 401)
            try:
                for case in ('healthy', 'orders-errors', 'tool-timeout', 'step-limit', 'deadline-exceeded', 'restart-required'):
                    check(case + '_activated', request(api, '/api/scenario', token, {'scenario': case})[0] == 200)
                    check(case + '_visible_in_ui_info', request(api, '/api/info')[1]['active_scenario'] == case)
                    status, run = request(api, '/api/runs', token, {'scenario': case, 'question': 'Verify T06 telemetry.'})
                    check(case + '_accepted', status == 202)
                    run = poll(api, run['run_id'], token)
                    if case == 'restart-required':
                        check('restart_still_requires_approval', run['status'] == 'awaiting_approval')
                        trace_before = run['trace_id']
                        check('restart_approval_accepted', request(api, '/api/runs/' + run['run_id'] + '/approval', token, run['pending_approval'])[0] == 202)
                        run = poll(api, run['run_id'], token)
                        check('approval_preserves_trace_and_one_effect', run['trace_id'] == trace_before and run['steps'][-1]['result']['restart_count'] == 1)
                    expected_error = {'tool-timeout': 'TOOL_TIMEOUT', 'step-limit': 'STEP_LIMIT', 'deadline-exceeded': 'DEADLINE_EXCEEDED'}.get(case)
                    check(case + '_expected_result', (run['status'] == 'failed' and run['error'] == expected_error) if expected_error else
                          (run['status'] == 'completed' and run['outcome'] == ('degraded' if case == 'orders-errors' else 'healthy')))
                    if case == 'tool-timeout':
                        check('timeout_bounded_to_three_calls', run['step_count'] == 3 and len(run['steps']) == 3 and run['duration_ms'] < 10000)
                    if case == 'step-limit':
                        check('step_limit_bounded_to_five_calls', run['step_count'] == 5 and len(run['steps']) == 5)
                    runs[case] = {key: run.get(key) for key in ('run_id', 'trace_id', 'status', 'outcome', 'error', 'step_count', 'duration_ms')}
            finally:
                check('reset_to_healthy', request(api, '/api/scenario', token, {'scenario': 'healthy'})[0] == 200)

            for case, run in runs.items():
                def trace_ready():
                    status, document = request(grafana, '/api/datasources/proxy/uid/tempo/api/traces/' + run['trace_id'])
                    if status != 200:
                        return None
                    spans = spans_from(document)
                    names = {s['name'] for s in spans}
                    expected = {'job.publish', 'job.expire'} if case == 'deadline-exceeded' else {'job.publish', 'job.execute', 'job.persist', 'tool.execute'}
                    ids = {s['spanId'] for s in spans}
                    complete = all(not s.get('parentSpanId') or s['parentSpanId'] in ids for s in spans)
                    if case == 'restart-required':
                        complete = complete and 'approval.persist' in names and sum(s['name'] == 'job.execute' for s in spans) == 2
                    if case == 'tool-timeout':
                        complete = complete and sum(s['name'] == 'orders.call' for s in spans) == 3
                    return (document, spans) if expected <= names and complete else None
                document, spans = eventually(trace_ready)
                (ROOT / ('artifacts/t06-trace-' + case + '.json')).write_text(json.dumps(document, indent=2) + '\n')
                check(case + '_trace_matches_run', all(hex_id(s['traceId']) == run['trace_id'] for s in spans))
                ids = {s['spanId'] for s in spans}
                check(case + '_trace_parents_present', all(not s.get('parentSpanId') or s['parentSpanId'] in ids for s in spans))
                if case != 'deadline-exceeded':
                    check(case + '_trace_crosses_four_services', {'api', 'worker', 'tools', 'orders'} <= {s['service'] for s in spans})
                if case == 'tool-timeout':
                    failures = [s for s in spans if s['name'] == 'orders.call' and s.get('status', {}).get('code') in (2, 'STATUS_CODE_ERROR')]
                    check('timeout_trace_identifies_orders_dependency', len(failures) == 3 and all(
                        any(a['key'] == 'server.address' and a['value'].get('stringValue') == 'orders.lab-tools.svc.cluster.local' for a in s.get('attributes', [])) for s in failures))
                run['trace_services'] = sorted({s['service'] for s in spans})
                run['span_count'] = len(spans)

            for name, expression in {
                'completed': 'sum(lab_runs_total{status="completed"})',
                'failed': 'sum(lab_runs_total{status="failed"})',
                'latency': 'sum(lab_run_duration_seconds_sum)',
                'steps': 'sum(lab_steps_per_run_count)',
                'retries': 'sum(lab_retries_total{error_code="TOOL_TIMEOUT"})',
                'timeouts': 'sum(lab_tool_calls_total{status="failed",error_code="TOOL_TIMEOUT"})',
                'denied': 'sum(lab_denied_calls_total{error_code="UNAUTHENTICATED"})',
            }.items():
                eventually(lambda: any(float(v['value'][1]) > 0 for v in query(expression)))
                check('metric_' + name, True)
            for case in runs:
                eventually(lambda: any(float(v['value'][1]) > 0 for v in query('lab_scenario_checks_total{scenario="' + case + '",result="expected"}')))
                check(case + '_correctness_metric', True)
            series = query('{__name__=~"lab_.+"}')
            check('metric_labels_have_no_run_or_trace_ids', bool(series) and all(
                not {'run_id', 'trace_id', 'question', 'user'} & set(s['metric']) for s in series))
            status, dashboard = request(grafana, '/api/dashboards/uid/agentic-devops')
            panels = dashboard.get('dashboard', {}).get('panels', [])
            check('dashboard_provisioned', status == 200 and len(panels) >= 9)
            for panel in panels:
                for item in panel.get('targets', []):
                    # Validate every provisioned PromQL expression through its actual datasource.
                    expression = item['expr']
                    eventually(lambda: query(expression))
                    check('dashboard_panel_' + str(panel['id']), True)

        logs = []
        raw_logs = []
        for namespace, component in COMPONENTS:
            raw = kubectl('-n', namespace, 'logs', 'deployment/' + component, '--all-pods=true',
                          '--prefix=false', '--since=15m', '--tail=10000', capture=True, timeout=20).stdout
            raw_logs.append(raw)
            for record in json_logs(raw):
                if record.get('run_id') in {r['run_id'] for r in runs.values()}:
                    logs.append(record)
        (ROOT / 'artifacts/t06-correlated-logs.json').write_text(json.dumps(logs, indent=2) + '\n')
        required = {'timestamp', 'level', 'service', 'run_id', 'trace_id', 'step', 'tool', 'duration_ms', 'status', 'error_code'}
        check('logs_have_required_fields', bool(logs) and all(required <= set(r) for r in logs))
        for case, run in runs.items():
            matching = [r for r in logs if r['run_id'] == run['run_id']]
            check(case + '_logs_match_trace', bool(matching) and all(r['trace_id'] == run['trace_id'] for r in matching))
            if case != 'deadline-exceeded':
                check(case + '_logs_cross_four_services', {'api', 'worker', 'tools', 'orders'} <= {r['service'] for r in matching})
        serialized = '\n'.join(raw_logs) + ''.join((ROOT / ('artifacts/t06-trace-' + case + '.json')).read_text() for case in runs)
        check('telemetry_does_not_expose_credentials_or_prompt', all(value not in serialized for value in config.values()) and 'Verify T06 telemetry.' not in serialized)
        report['result'] = 'PASS'
    finally:
        target.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: ' + str(target), flush=True)
    return report


if __name__ == '__main__':
    verify()
