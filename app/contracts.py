"""Validated boundaries shared by the durable API, worker and tool service."""

from dataclasses import dataclass
import hmac
from uuid import UUID

SCENARIOS = ('healthy', 'orders-errors', 'restart-required', 'tool-timeout', 'step-limit', 'deadline-exceeded')
READ_TOOL = 'read_orders_health'
RESTART_TOOL = 'restart_orders'
ARGUMENTS = {'service': 'orders'}


class Rejected(Exception):
    def __init__(self, code, status=403):
        self.code, self.status = code, status
        super().__init__(code)


def uuid_text(value):
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise Rejected('INVALID_ID', 400) from None


def request(payload):
    if not isinstance(payload, dict) or set(payload) != {'question', 'scenario'}:
        raise Rejected('INVALID_REQUEST', 400)
    question, scenario = payload['question'], payload['scenario']
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
        raise Rejected('INVALID_QUESTION', 400)
    if not isinstance(scenario, str) or scenario not in SCENARIOS:
        raise Rejected('INVALID_SCENARIO', 400)
    return question.strip(), scenario


@dataclass(frozen=True)
class Policy:
    max_steps: int = 5
    max_attempts: int = 3
    deadline_seconds: float = 30
    lease_seconds: float = 3
    dependency_timeout: float = 0.5
    retries: int = 2
    approval_seconds: float = 300

    def __post_init__(self):
        if not (1 <= self.max_steps <= 20 and 1 <= self.max_attempts <= 10
                and 0 <= self.retries <= 5 and 0 < self.dependency_timeout
                < self.lease_seconds <= self.deadline_seconds
                and self.approval_seconds > 0):
            raise ValueError('Invalid execution limits.')


class Credentials:
    """Static local credentials: identity and scopes come from server configuration."""

    def __init__(self, entries):
        self.entries = entries
        tokens = [entry['token'] for entry in entries.values()]
        if any(not isinstance(token, str) or len(token) < 32 for token in tokens):
            raise ValueError('Credentials must contain at least 32 characters.')
        if len(tokens) != len(set(tokens)):
            raise ValueError('Credentials must be distinct.')

    def authorize(self, authorization, scope):
        if not isinstance(authorization, str) or not authorization.startswith('Bearer '):
            raise Rejected('UNAUTHENTICATED', 401)
        token = authorization.removeprefix('Bearer ')
        for identity, entry in self.entries.items():
            if hmac.compare_digest(token.encode(), entry['token'].encode()):
                if scope not in entry['scopes']:
                    raise Rejected('SCOPE_DENIED')
                return identity
        raise Rejected('UNAUTHENTICATED', 401)
