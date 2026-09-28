"""Separate bounded NetworkPolicy connectivity evidence from HTTP authorization."""

import json
import subprocess
from uuid import uuid4

from app.runtime import now
from scripts.lab_platform import PRIVATE, ROOT, guard, kubectl
from scripts.verify_cluster import port_forward, request, poll


def pod_exec(namespace, pod, code):
    return kubectl('-n', namespace, 'exec', pod, '--', 'python', '-B', '-c', code,
                   capture=True, timeout=15).stdout


def tcp(namespace, pod, address, port):
    # Use literal Service IPs: a negative result cannot accidentally be a DNS failure.
    code = '''import json, socket, time
started = time.monotonic()
try:
    with socket.create_connection((ADDRESS, PORT), timeout=2):
        result = 'connected'
except TimeoutError:
    result = 'timeout'
except OSError as error:
    result = type(error).__name__
print(json.dumps({'result': result, 'seconds': round(time.monotonic()-started, 3)}))
'''.replace('ADDRESS', repr(address)).replace('PORT', str(port))
    return json.loads(pod_exec(namespace, pod, code))


def verify():
    guard()
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    config = json.loads((PRIVATE / 'credentials.json').read_text())
    build = json.loads((PRIVATE / 'build.json').read_text())
    suffix = uuid4().hex[:8]
    unauthorized = 'network-check-' + suffix
    report = {'timestamp': now(), 'scope': 'T05 Calico NetworkPolicy and independent HTTP authorization',
              'connectivity': [], 'authorization': [], 'result': 'FAIL'}
    created = False
    try:
        endpoints = {}
        for namespace, component in [('lab-app', 'api'), ('lab-app', 'worker'),
                                     ('lab-tools', 'tools'), ('lab-tools', 'orders'), ('lab-data', 'postgres')]:
            svc = json.loads(kubectl('-n', namespace, 'get', 'service', component, '-o', 'json', capture=True).stdout)
            pods = json.loads(kubectl('-n', namespace, 'get', 'pods', '-l', 'app.kubernetes.io/name=' + component,
                                     '-o', 'json', capture=True).stdout)['items']
            pods = [p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status']['phase'] == 'Running']
            endpoints[component] = {'namespace': namespace, 'pod': pods[0]['metadata']['name'], 'ip': svc['spec']['clusterIP']}
        manifest = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {
            'name': unauthorized, 'namespace': 'lab-app',
            'labels': {'app.kubernetes.io/name': 'unauthorized-check', 'app.kubernetes.io/part-of': 'agentic-devops'}},
            'spec': {'automountServiceAccountToken': False, 'activeDeadlineSeconds': 180,
                     'terminationGracePeriodSeconds': 1,
                     'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001, 'runAsGroup': 10001,
                                         'seccompProfile': {'type': 'RuntimeDefault'}},
                     'containers': [{'name': 'check', 'image': build['image'], 'imagePullPolicy': 'Never',
                                     'command': ['python', '-c', 'import time; time.sleep(180)'],
                                     'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                                         'capabilities': {'drop': ['ALL']}},
                                     'resources': {'requests': {'cpu': '50m', 'memory': '32Mi'},
                                                   'limits': {'cpu': '100m', 'memory': '64Mi'}}}], 'restartPolicy': 'Never'}}
        kubectl('create', '-f', '-', input=json.dumps(manifest), capture=True)
        created = True
        kubectl('-n', 'lab-app', 'wait', 'pod/' + unauthorized, '--for=condition=Ready', '--timeout=60s', capture=True)
        endpoints['unauthorized'] = {'namespace': 'lab-app', 'pod': unauthorized}
        # Positive control to each protected destination, followed by prohibited equivalents.
        cases = [('api', 'postgres', 5432, True), ('worker', 'postgres', 5432, True),
                 ('tools', 'postgres', 5432, True), ('orders', 'postgres', 5432, True),
                 ('worker', 'tools', 8080, True), ('tools', 'orders', 8080, True),
                 ('api', 'orders', 8080, False), ('worker', 'orders', 8080, False),
                 ('api', 'tools', 8080, False), ('unauthorized', 'postgres', 5432, False),
                 ('unauthorized', 'tools', 8080, False), ('unauthorized', 'api', 8080, False)]
        for source, target, port, allowed in cases:
            origin = endpoints[source]
            result = tcp(origin['namespace'], origin['pod'], endpoints[target]['ip'], port)
            expected = 'connected' if allowed else 'timeout'
            result.update(source=source, destination=target, port=port, expected=expected)
            report['connectivity'].append(result)
            print(f'{source} -> {target}:{port}: {result["result"]} (expected {expected})', flush=True)
            if result['result'] != expected:
                raise AssertionError('Connectivity did not match the policy contract.')
        # DNS is independently checked; permission is only to cluster DNS pods.
        dns = pod_exec('lab-app', endpoints['worker']['pod'],
                       "import socket; print(socket.gethostbyname('tools.lab-tools.svc.cluster.local'))").strip()
        report['dns'] = {'resolved_expected_service': dns == endpoints['tools']['ip']}
        if not report['dns']['resolved_expected_service']:
            raise AssertionError('Cluster DNS failed.')
        # The host positive control avoids mistaking an unavailable destination for policy enforcement.
        import socket
        with socket.create_connection(('1.1.1.1', 443), timeout=3):
            report['internet_control'] = 'host_connected_to_1.1.1.1:443'
        for source in ('api', 'worker', 'tools', 'orders'):
            origin = endpoints[source]
            result = tcp(origin['namespace'], origin['pod'], '1.1.1.1', 443)
            result.update(source=source, destination='1.1.1.1', port=443, expected='timeout')
            report['connectivity'].append(result)
            if result['result'] != 'timeout':
                raise AssertionError('Unexpected workload internet access.')
        with port_forward('lab-app', 'service/api') as port:
            status, run = request(port, '/api/runs', config['user_token'], {'question': 'Verify network boundary', 'scenario': 'healthy'})
            if status != 202:
                raise AssertionError('API creation failed through localhost.')
            run = poll(port, run['run_id'], config['user_token'])
            report['run_id'] = run['run_id']
            if run['status'] != 'completed':
                raise AssertionError('Allowed application flow no longer completes.')
        # Execute on the allowed worker->tool path. Read only its mounted worker token;
        # never pass credentials in argv or return them in the report.
        code = '''import json
from http.client import HTTPConnection
from pathlib import Path
config = json.loads(Path('/var/run/lab/credentials.json').read_text())
payload = {'run_id': RUN_ID, 'tool': 'read_orders_health', 'arguments': {'service': 'orders'}, 'idempotency_key': None}
results=[]
for name, token in [('missing', None), ('invalid', 'not-a-credential'), ('valid', config['worker_token'])]:
    conn=HTTPConnection('tools.lab-tools.svc.cluster.local', 8080, timeout=3)
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    conn.request('POST','/tools/execute',json.dumps(payload),headers)
    response=conn.getresponse()
    results.append({'credential':name,'http_status':response.status})
    response.read()
    conn.close()
conn=HTTPConnection('tools.lab-tools.svc.cluster.local', 8080, timeout=3)
payload['tool']='restart_orders'
payload['idempotency_key']='unapproved-network-check'
conn.request('POST','/tools/execute',json.dumps(payload),
             {'Content-Type':'application/json','Authorization':'Bearer '+config['worker_token']})
response=conn.getresponse()
results.append({'credential':'valid_but_no_approval','http_status':response.status})
response.read()
conn.close()
print(json.dumps(results))
'''.replace('RUN_ID', repr(run['run_id']))
        report['authorization'] = json.loads(pod_exec('lab-app', endpoints['worker']['pod'], code))
        if [r['http_status'] for r in report['authorization']] != [401, 401, 200, 403]:
            raise AssertionError('HTTP authorization failed independently of connectivity.')
        report['result'] = 'PASS'
    finally:
        try:
            if created:
                kubectl('-n', 'lab-app', 'delete', 'pod', unauthorized, '--wait=true',
                        '--ignore-not-found=true', '--grace-period=1', '--timeout=15s', capture=True, timeout=20)
        except subprocess.SubprocessError:
            report.update(result='FAIL', cleanup_error='TEST_POD_CLEANUP_FAILED')
            raise
        finally:
            (ROOT / 'artifacts/t05-network.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
