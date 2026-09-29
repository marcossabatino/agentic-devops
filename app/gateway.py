"""Tool authorization gateway; the orders service owns the atomic effect."""

from http.client import HTTPConnection
import json

from app.contracts import RESTART_TOOL, Rejected
from app.tools import DurableTools, validate_call
from app import telemetry as tel


class ToolGateway(DurableTools):
    def __init__(self, db, credentials, orders_host, orders_token, port=8080, timeout=0.4):
        super().__init__(db, credentials)
        self.orders_host, self.orders_token = orders_host, orders_token
        self.port, self.timeout = port, timeout

    def execute(self, authorization, payload):
        run_id, tool, arguments, key = validate_call(self.credentials, authorization, payload)
        if tool == RESTART_TOOL:
            with self.db.connect() as conn:
                existing = conn.execute('SELECT * FROM tool_results WHERE idempotency_key = %s', (key,)).fetchone()
                if existing:
                    if (str(existing['run_id']) != run_id or existing['tool'] != tool
                            or existing['arguments'] != arguments):
                        raise Rejected('IDEMPOTENCY_CONFLICT', 409)
                else:
                    approval = conn.execute('''SELECT *, expires_at > clock_timestamp() AS valid
                        FROM approvals WHERE run_id = %s''', (run_id,)).fetchone()
                    if (not approval or not approval['valid'] or approval['tool'] != tool
                            or approval['arguments'] != arguments):
                        raise Rejected('APPROVAL_REQUIRED')
                    if approval['consumed_key'] is not None:
                        raise Rejected('APPROVAL_ALREADY_USED', 409)
        # The effect owner validates again and atomically consumes approval. This
        # read-only gate cannot replace that transaction or create a valid approval.
        with tel.span('orders.call', kind=tel.SpanKind.CLIENT, run_id=run_id, tool=tool) as current:
            current.set_attribute('server.address', self.orders_host)
            return self.forward(payload)

    def forward(self, payload):
        connection = HTTPConnection(self.orders_host, self.port, timeout=self.timeout)
        try:
            connection.request('POST', '/tools/execute', json.dumps(payload), {
                **tel.carrier(), 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.orders_token})
            response = connection.getresponse()
            body = json.loads(response.read(65536))
            if response.status != 200:
                raise Rejected(body.get('error', 'ORDERS_FAILED'), response.status)
            return body
        except TimeoutError:
            raise Rejected('TOOL_TIMEOUT', 503) from None
        except OSError:
            raise Rejected('TOOL_UNAVAILABLE', 503) from None
        finally:
            connection.close()
