"""Bounded, redacted telemetry; W3C context survives queue and HTTP boundaries."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import json
import os
from time import monotonic

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily

SERVICE = os.environ.get('OTEL_SERVICE_NAME', 'lab-local')
PROVIDER = TracerProvider(resource=Resource.create({'service.name': SERVICE, 'service.namespace': 'agentic-devops'}))
TRACER = PROVIDER.get_tracer('agentic-devops')
PROPAGATOR = TraceContextTextMapPropagator()
FIELDS = ContextVar('lab_telemetry_fields', default={})
REGISTRY = CollectorRegistry()
CALLS = Counter('lab_tool_calls_total', 'Dependency calls by bounded result category.', ['tool', 'status', 'error_code'], registry=REGISTRY)
LATENCY = Histogram('lab_tool_call_duration_seconds', 'Dependency latency.', ['tool'], buckets=(.01, .05, .1, .25, .5, 1, 2, 5), registry=REGISTRY)
RETRIES = Counter('lab_retries_total', 'Retried dependency calls.', ['tool', 'error_code'], registry=REGISTRY)
DENIED = Counter('lab_denied_calls_total', 'Denied HTTP calls.', ['error_code'], registry=REGISTRY)
ERRORS = frozenset(('TOOL_TIMEOUT', 'TOOL_UNAVAILABLE', 'DEADLINE_EXCEEDED', 'STEP_LIMIT', 'LEASE_LOST',
                   'EXECUTION_FAILED', 'UNAUTHENTICATED', 'SCOPE_DENIED', 'APPROVAL_REQUIRED',
                   'APPROVAL_EXPIRED', 'ATTEMPTS_EXHAUSTED', 'DATABASE_UNAVAILABLE', 'INTERNAL_ERROR'))


def error_code(error):
    if isinstance(error, TimeoutError):
        return 'TOOL_TIMEOUT'
    if isinstance(error, OSError):
        return 'TOOL_UNAVAILABLE'
    code = getattr(error, 'code', error if isinstance(error, str) else 'INTERNAL_ERROR')
    return code if code in ERRORS else 'OTHER'


def carrier():
    value = {}
    PROPAGATOR.inject(value)
    return value


def trace_id():
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, '032x') if context.is_valid else None


def enrich(**values):
    safe = {key: value for key, value in values.items() if key in ('run_id', 'step', 'tool', 'status', 'error_code') and value is not None}
    FIELDS.set({**FIELDS.get(), **safe})
    for key, value in safe.items():
        trace.get_current_span().set_attribute('lab.' + key, str(value) if key == 'run_id' else value)


def emit(event, duration_ms=0, **values):
    context = trace.get_current_span().get_span_context()
    record = dict(timestamp=datetime.now(timezone.utc).isoformat(), level='INFO', service=SERVICE,
                  run_id=None, trace_id=trace_id(), span_id=format(context.span_id, '016x'),
                  step=None, tool=None, duration_ms=round(duration_ms, 3), status='ok', error_code=None)
    record.update(FIELDS.get())
    record.update(values)
    record['event'] = event
    if record['error_code']:
        record['level'] = 'ERROR'
    # Only fixed events, validated IDs and categorical fields enter this record.
    # Never serialize payloads, headers, DSNs, exception messages or prompt text.
    print(json.dumps(record), flush=True)


@contextmanager
def span(name, parent=None, kind=SpanKind.INTERNAL, **fields):
    token = FIELDS.set({**FIELDS.get()})
    started = monotonic()
    context = PROPAGATOR.extract(parent) if parent else None
    with TRACER.start_as_current_span(name, context=context, kind=kind,
                                      record_exception=False, set_status_on_exception=False) as current:
        enrich(**fields)
        try:
            yield current
        except Exception as error:
            code = error_code(error)
            enrich(status='failed', error_code=code)
            current.set_status(Status(StatusCode.ERROR, code))
            raise
        finally:
            emit(name, (monotonic() - started) * 1000)
            FIELDS.reset(token)


def traced(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with span(name):
                return function(*args, **kwargs)
        return wrapped
    return decorate


class DurableCollector:
    """Terminal metrics derived from committed jobs survive worker restarts/reclaims."""
    def __init__(self, db):
        self.db = db

    def collect(self):
        with self.db.connect() as conn:
            rows = conn.execute('SELECT status, step_count, data FROM jobs').fetchall()
        counts, pending, correctness = {}, {}, {}
        durations, steps = [], []
        for row in rows:
            status, data = row['status'], row['data']
            if status not in ('completed', 'failed'):
                pending[status] = pending.get(status, 0) + 1
                continue
            outcome = data.get('outcome') or 'unknown'
            key = (status, outcome)
            counts[key] = counts.get(key, 0) + 1
            durations.append(data.get('duration_ms', 0) / 1000)
            steps.append(row['step_count'])
            scenario = data['scenario']
            expected_error = {'tool-timeout': 'TOOL_TIMEOUT', 'step-limit': 'STEP_LIMIT', 'deadline-exceeded': 'DEADLINE_EXCEEDED'}.get(scenario)
            correct = (status == 'failed' and data.get('error') == expected_error) if expected_error else (
                status == 'completed' and outcome == ('degraded' if scenario == 'orders-errors' else 'healthy'))
            key = (scenario, 'expected' if correct else 'unexpected')
            correctness[key] = correctness.get(key, 0) + 1
        runs = CounterMetricFamily('lab_runs', 'Persisted terminal diagnoses, not HTTP availability.', labels=['status', 'outcome'])
        for key, count in counts.items():
            runs.add_metric(list(key), count)
        yield runs
        queue = GaugeMetricFamily('lab_pending_jobs', 'Persisted nonterminal jobs.', labels=['status'])
        for status in ('queued', 'running', 'awaiting_approval'):
            queue.add_metric([status], pending.get(status, 0))
        yield queue
        checks = CounterMetricFamily('lab_scenario_checks', 'Persisted results compared to deterministic expectations.', labels=['scenario', 'result'])
        for key, count in correctness.items():
            checks.add_metric(list(key), count)
        yield checks
        for name, help_text, values, bounds in (
            ('lab_run_duration_seconds', 'Terminal duration including approval wait.', durations, (.1, .5, 1, 2, 5, 10, 30, 60, 300)),
            ('lab_steps_per_run', 'Persisted reserved steps in terminal runs.', steps, (1, 2, 3, 5, 10, 20)),
        ):
            buckets = [(str(b), sum(v <= b for v in values)) for b in bounds]
            buckets.append(('+Inf', len(values)))
            yield HistogramMetricFamily(name, help_text, buckets=buckets, sum_value=sum(values))


def configure(db=None):
    endpoint = os.environ.get('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT')
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        PROVIDER.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=1),
                                                      max_queue_size=512, max_export_batch_size=64,
                                                      schedule_delay_millis=500))
    if db is not None:
        REGISTRY.register(DurableCollector(db))
    return start_http_server(9090, addr='0.0.0.0', registry=REGISTRY)
