"""Launch the persistent localhost lab and stop all owned processes on exit."""

import argparse
from pathlib import Path
import signal
from threading import Event, Thread

from app.api import durable_server
from app.contracts import Credentials, Policy
from app.database import Database
from app.server import revision
from app.tools import DurableTools
from app.worker import ToolClient, Worker
from scripts.local_database import local_database


def credentials(config):
    return Credentials({
        'lab-user': {'token': config['user_token'], 'scopes': ['runs:create', 'runs:read', 'runs:approve']},
        'agent-worker': {'token': config['worker_token'], 'scopes': ['tools:read', 'tools:restart']},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--data', type=Path, default=Path('data/t03'))
    parser.add_argument('--max-steps', type=int, default=5)
    parser.add_argument('--max-attempts', type=int, default=3)
    parser.add_argument('--deadline', type=float, default=30)
    parser.add_argument('--lease', type=float, default=3)
    parser.add_argument('--dependency-timeout', type=float, default=0.5)
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--approval-window', type=float, default=300)
    args = parser.parse_args()
    policy = Policy(args.max_steps, args.max_attempts, args.deadline, args.lease,
                    args.dependency_timeout, args.retries, args.approval_window)
    stop = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    with local_database(args.data) as (dsns, config):
        auth = credentials(config)
        tools = DurableTools(Database(dsns['tools'], policy), auth).server()
        try:
            api = durable_server(Database(dsns['api'], policy), auth, revision(), args.port)
        except Exception:
            tools.server_close()
            raise
        worker = Worker(Database(dsns['worker'], policy), ToolClient(tools.server_port, config['worker_token']))
        threads = [Thread(target=server.serve_forever, daemon=True) for server in (tools, api)]
        threads.append(Thread(target=worker.run, args=(stop,), daemon=True))
        for thread in threads:
            thread.start()
        print(f'SIMULATED durable lab: http://127.0.0.1:{api.server_port}', flush=True)
        print(f'User credential: user_token in {args.data.resolve() / "settings.json"} (never paste it in chat).', flush=True)
        try:
            stop.wait()
        finally:
            stop.set()
            threads[-1].join(timeout=5)
            for server in (api, tools):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=5)


if __name__ == '__main__':
    main()
