"""Deterministic, read-only execution for the T02 local learning increment."""

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from uuid import uuid4

MODE = "SIMULATED"
SCENARIOS = ("healthy", "orders-errors")
MAX_QUESTION_LENGTH = 1000


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != {"question", "scenario"}:
        raise ValueError("Provide only question and scenario.")
    question = payload["question"]
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must be nonempty text.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Question must contain at most {MAX_QUESTION_LENGTH} characters.")
    if not isinstance(payload["scenario"], str) or payload["scenario"] not in SCENARIOS:
        raise ValueError("Choose healthy or orders-errors.")
    return question.strip(), payload["scenario"]


class OrdersSimulator:
    """Return a per-run snapshot; scenarios never change an external service."""

    def health(self, scenario):
        if scenario not in SCENARIOS:
            raise ValueError("Unknown orders scenario.")
        failing = scenario == "orders-errors"
        return {
            "service": "orders",
            "status": "degraded" if failing else "healthy",
            "http_status": 503 if failing else 200,
            "error_rate": 0.35 if failing else 0.0,
            "latency_ms": 420 if failing else 24,
            "simulated": True,
        }


class ToolService:
    """Allow one read-only tool with explicit arguments; no shell or network access."""

    def __init__(self, orders=None):
        self.orders = orders or OrdersSimulator()

    def execute(self, name, arguments, scenario):
        if name != "read_orders_health" or arguments != {"service": "orders"}:
            raise ValueError("Unknown tool or invalid arguments.")
        return self.orders.health(scenario)


class SimulatedAdapter:
    """Scripted tool selection and summaries, with no LLM or prompt interpretation."""

    def tool_call(self):
        return "read_orders_health", {"service": "orders"}

    def summarize(self, observation):
        if observation["status"] == "healthy":
            return "healthy", "The simulated orders service is healthy; no errors were observed."
        return "degraded", (
            "The simulated orders service is returning HTTP 503 with a 35% error rate. "
            "This is the selected failure scenario; no restart was performed."
        )


class RunStore:
    """Bounded process-local history; no durability or background job queue."""

    def __init__(self, capacity=100):
        if capacity < 1:
            raise ValueError("Run capacity must be positive.")
        self.capacity = capacity
        self._runs = OrderedDict()
        self._lock = Lock()

    def save(self, run):
        with self._lock:
            self._runs[run["run_id"]] = deepcopy(run)
            while len(self._runs) > self.capacity:
                self._runs.popitem(last=False)

    def get(self, run_id):
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None


class Runner:
    """Execute one tool call synchronously and store its terminal result."""

    def __init__(self, tools=None, adapter=None, store=None, revision="unknown"):
        self.tools = tools or ToolService()
        self.adapter = adapter or SimulatedAdapter()
        self.store = store or RunStore()
        self.revision = revision

    def run(self, payload):
        question, scenario = validate_request(payload)
        started = perf_counter()
        run = {
            "run_id": str(uuid4()), "mode": MODE, "revision": self.revision,
            "question": question, "scenario": scenario, "status": "running",
            "started_at": now(), "steps": [], "outcome": None, "error": None,
        }
        step_started = perf_counter()
        try:
            name, arguments = self.adapter.tool_call()
            step = {
                "step": 1, "tool": name, "arguments": arguments,
                "started_at": now(), "status": "running", "result": None,
            }
            run["steps"].append(step)
            observation = self.tools.execute(name, arguments, scenario)
            step.update(status="completed", result=observation,
                        duration_ms=round((perf_counter() - step_started) * 1000, 3))
            outcome, summary = self.adapter.summarize(observation)
            run.update(status="completed", outcome=outcome, summary=summary)
        except Exception:
            # Return an operational error, never exception contents or credentials.
            if run["steps"]:
                run["steps"][-1].update(
                    status="failed", duration_ms=round((perf_counter() - step_started) * 1000, 3))
            run.update(status="failed", error="EXECUTION_FAILED",
                       summary="The simulated diagnosis could not complete.")
        run.update(finished_at=now(), duration_ms=round((perf_counter() - started) * 1000, 3))
        self.store.save(run)
        return run
