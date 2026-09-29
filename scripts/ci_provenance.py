"""Require this exact clean main commit to have a successful GitHub CI push run."""

import json
import re
import subprocess

REPOSITORY = 'marcossabatino/agentic-devops'
WORKFLOW = '.github/workflows/ci.yml'


def output(*argv):
    return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=20).stdout.strip()


def validated_commit(run=output):
    branch = run('git', 'branch', '--show-current')
    if branch != 'main':
        raise RuntimeError('Deploy the validated main branch, not a feature branch.')
    sha = run('git', 'rev-parse', 'HEAD')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise RuntimeError('Unable to identify the full source commit.')
    if run('git', 'status', '--porcelain', '--untracked-files=normal'):
        raise RuntimeError('Commit or discard local changes before a validated deployment.')
    remote = run('git', 'ls-remote', 'origin', 'refs/heads/main').split()
    if len(remote) != 2 or remote[0] != sha or remote[1] != 'refs/heads/main':
        raise RuntimeError('Local HEAD must match origin/main exactly.')
    data = json.loads(run('gh', 'api', '-X', 'GET',
                          f'repos/{REPOSITORY}/actions/workflows/ci.yml/runs',
                          '-f', 'head_sha=' + sha, '-f', 'event=push', '-f', 'per_page=30'))
    accepted = [item for item in data.get('workflow_runs', [])
                if item.get('head_sha') == sha and item.get('event') == 'push'
                and item.get('path') == WORKFLOW and item.get('status') == 'completed'
                and item.get('conclusion') == 'success']
    if not accepted:
        raise RuntimeError('The exact origin/main commit has no successful completed CI push run.')
    selected = max(accepted, key=lambda item: item['id'])
    return {'source_revision': sha, 'ci_run_id': selected['id'], 'ci_run_url': selected['html_url']}
