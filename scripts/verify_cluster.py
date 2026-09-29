"""Bounded verification of the deployed local platform, through real port-forwards."""

from contextlib import contextmanager
from http.client import HTTPConnection
import json
import re
import subprocess
import tempfile
import time

from app.runtime import now
from scripts.lab_platform import CONFIG, KUBECONFIG, PRIVATE, PROFILE, ROOT, environment, guard, kubectl


@contextmanager
def port_forward(namespace, resource, remote_port=8080):
    with tempfile.TemporaryFile(mode='w+') as log:
        process = subprocess.Popen(['kubectl', '--kubeconfig', str(KUBECONFIG), '--context', PROFILE,
                                    '-n', namespace, 'port-forward', '--address=127.0.0.1', resource,
                                    ':' + str(remote_port)], env=environment(), stdout=log, stderr=log, text=True)
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('The scoped port-forward exited before readiness.')
                log.seek(0)
                match = re.search(r'Forwarding from 127\.0\.0\.1:(\d+)', log.read())
                if match:
                    yield int(match[1])
                    break
                time.sleep(0.1)
            else:
                raise TimeoutError('The scoped port-forward did not become ready.')
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def request(port, path, token=None, payload=None):
    connection = HTTPConnection('127.0.0.1', port, timeout=5)
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        connection.request('POST' if payload is not None else 'GET', path,
                           json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if raw else None
    finally:
        connection.close()


def poll(port, run_id, token):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        status, run = request(port, '/api/runs/' + run_id, token)
        if status != 200:
            raise RuntimeError('Unable to retrieve the deployed run.')
        if run['status'] not in ('queued', 'running'):
            return run
        time.sleep(0.2)
    raise TimeoutError('The deployed run did not reach a terminal or approval state.')


def verify():
    guard()
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    checks, runs = {}, {}

    def check(name, condition):
        checks[name] = bool(condition)
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition:
            raise AssertionError(name)

    report = {'timestamp': now(), 'scope': 'T04 deployed Kubernetes platform', 'checks': checks, 'run_ids': runs}
    try:
        config = json.loads((PRIVATE / 'credentials.json').read_text())
        build = json.loads((PRIVATE / 'build.json').read_text())
        report['build'] = build
        for namespace, component in [('lab-app', 'api'), ('lab-app', 'worker'),
                                     ('lab-tools', 'tools'), ('lab-tools', 'orders')]:
            kubectl('-n', namespace, 'rollout', 'status', 'deployment/' + component, '--timeout=120s', capture=True)
            deployment = json.loads(kubectl('-n', namespace, 'get', 'deployment', component,
                                            '-o', 'json', capture=True).stdout)
            container = deployment['spec']['template']['spec']['containers'][0]
            env_values = {item['name']: item.get('value') for item in container['env']}
            check(component + '_matches_validated_commit',
                  container['image'] == build['image']
                  and env_values['SOURCE_REVISION'] == build['source_revision']
                  and len(build['source_revision']) == 40
                  and bool(build.get('ci_run_id')))
        kubectl('-n', 'lab-data', 'rollout', 'status', 'statefulset/postgres', '--timeout=120s', capture=True)
        check('all_application_workloads_ready', True)
        nodes = json.loads(kubectl('get', 'nodes', '-o', 'json', capture=True).stdout)['items']
        check('pinned_kubernetes_version', nodes[0]['status']['nodeInfo']['kubeletVersion'] == 'v' + CONFIG['kubernetes'])
        calico = json.loads(kubectl('-n', 'kube-system', 'get', 'daemonset', 'calico-node', '-o', 'json', capture=True).stdout)
        report['calico_images'] = [c['image'] for c in calico['spec']['template']['spec']['containers']]
        check('calico_ready', calico['status'].get('numberReady') == 1)
        pvc = json.loads(kubectl('-n', 'lab-data', 'get', 'pvc', 'data-postgres-0', '-o', 'json', capture=True).stdout)
        check('database_persistent_volume_bound', pvc['status']['phase'] == 'Bound')
        for namespace in ('lab-app', 'lab-tools', 'lab-data'):
            services = json.loads(kubectl('-n', namespace, 'get', 'services', '-o', 'json', capture=True).stdout)['items']
            check(namespace + '_services_internal_only', all(s['spec']['type'] == 'ClusterIP' for s in services))
        with port_forward('lab-app', 'service/api') as port:
            check('api_through_loopback_port_forward', request(port, '/healthz')[0] == 200)
            check('api_info_identifies_validated_commit',
                  request(port, '/api/info')[1]['revision'] == build['source_revision'])
            check('api_requires_authentication', request(port, '/api/runs', payload={'question': 'Health?', 'scenario': 'healthy'})[0] == 401)
            for scenario in ('healthy', 'orders-errors', 'restart-required', 'tool-timeout', 'step-limit'):
                status, run = request(port, '/api/runs', config['user_token'], {'question': 'Verify cluster behavior', 'scenario': scenario})
                check(scenario + '_accepted', status == 202)
                runs[scenario] = run['run_id']
                run = poll(port, run['run_id'], config['user_token'])
                check(scenario + '_history_identifies_validated_commit',
                      run['revision'] == build['source_revision'])
                if scenario == 'restart-required':
                    check('restart_waits_for_approval', run['status'] == 'awaiting_approval')
                    status, _ = request(port, '/api/runs/' + run['run_id'] + '/approval', config['user_token'], run['pending_approval'])
                    check('approval_accepted', status == 202)
                    run = poll(port, run['run_id'], config['user_token'])
                    check('separate_orders_service_effect', run['status'] == 'completed' and run['steps'][-1]['result']['restart_count'] == 1)
                elif scenario in ('healthy', 'orders-errors'):
                    check(scenario + '_outcome', run['status'] == 'completed' and run['outcome'] == ('healthy' if scenario == 'healthy' else 'degraded'))
                else:
                    expected = 'TOOL_TIMEOUT' if scenario == 'tool-timeout' else 'STEP_LIMIT'
                    check(scenario + '_bounded_failure', run['status'] == 'failed' and run['error'] == expected)
        # Controlled application restart demonstrates mounted storage and durable history.
        kubectl('-n', 'lab-data', 'rollout', 'restart', 'statefulset/postgres', capture=True)
        kubectl('-n', 'lab-data', 'rollout', 'status', 'statefulset/postgres', '--timeout=120s', capture=True)
        with port_forward('lab-app', 'service/api') as port:
            status, run = request(port, '/api/runs/' + runs['restart-required'], config['user_token'])
            check('history_survives_postgres_pod_restart', status == 200 and run['status'] == 'completed'
                  and run['steps'][-1]['result']['restart_count'] == 1)
        plan = subprocess.run(['tofu', '-chdir=infra/local', 'plan', '-input=false', '-detailed-exitcode', '-no-color'],
                              cwd=ROOT, env=environment(), capture_output=True, text=True, timeout=120)
        (ROOT / 'artifacts/t04-post-apply-plan.log').write_text(plan.stdout + plan.stderr)
        check('post_apply_plan_has_no_changes', plan.returncode == 0)
        report['result'] = 'PASS'
    except Exception as error:
        report.update(result='FAIL', error_type=type(error).__name__)
        raise
    finally:
        path = ROOT / 'artifacts/t04-cluster.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
