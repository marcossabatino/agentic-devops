"""Deployment must never label unvalidated or modified source as CI-validated."""

import json
import unittest

from scripts.ci_provenance import validated_commit

SHA = 'a' * 40


class ProvenanceTests(unittest.TestCase):
    def command(self, *, branch='main', dirty='', remote=SHA, conclusion='success',
                run_sha=SHA, event='push'):
        calls = []

        def run(*argv):
            calls.append(argv)
            if argv[:3] == ('git', 'branch', '--show-current'):
                return branch
            if argv[:3] == ('git', 'rev-parse', 'HEAD'):
                return SHA
            if argv[:3] == ('git', 'status', '--porcelain'):
                return dirty
            if argv[:3] == ('git', 'ls-remote', 'origin'):
                return remote + '\trefs/heads/main'
            if argv[:2] == ('gh', 'api'):
                return json.dumps({'workflow_runs': [{'id': 42, 'head_sha': run_sha,
                    'event': event, 'path': '.github/workflows/ci.yml',
                    'status': 'completed', 'conclusion': conclusion,
                    'html_url': 'https://github.com/example/actions/runs/42'}]})
            raise AssertionError(argv)

        return run, calls

    def test_accepts_only_clean_exact_main_with_successful_push_ci(self):
        run, calls = self.command()
        self.assertEqual(validated_commit(run)['source_revision'], SHA)
        self.assertTrue(any(argv[:2] == ('gh', 'api') for argv in calls))

    def test_rejects_branch_dirty_or_remote_mismatch_before_api(self):
        for change in ({'branch': 'feature'}, {'dirty': ' M app/service.py'},
                       {'remote': 'b' * 40}):
            with self.subTest(change=change):
                run, calls = self.command(**change)
                with self.assertRaises(RuntimeError):
                    validated_commit(run)
                self.assertFalse(any(argv[:2] == ('gh', 'api') for argv in calls))

    def test_rejects_failed_wrong_sha_and_pr_only_ci(self):
        for change in ({'conclusion': 'failure'}, {'run_sha': 'b' * 40},
                       {'event': 'pull_request'}):
            with self.subTest(change=change):
                run, _ = self.command(**change)
                with self.assertRaises(RuntimeError):
                    validated_commit(run)


if __name__ == '__main__':
    unittest.main()
