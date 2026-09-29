"""Guardrails for deleting only the dedicated Minikube profile."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import cleanup


class CleanupGuardTests(unittest.TestCase):
    def profile(self, status='Stopped'):
        return {'Name': cleanup.PROFILE, 'Status': status,
                'Config': {'Name': cleanup.PROFILE,
                           'Driver': cleanup.lab_platform.CONFIG['driver'],
                           'CPUs': cleanup.lab_platform.CONFIG['cpus'],
                           'Memory': cleanup.lab_platform.CONFIG['memory_mib'],
                           'Network': cleanup.lab_platform.CONFIG['network'],
                           'KubernetesConfig': {'KubernetesVersion':
                                                'v' + cleanup.lab_platform.CONFIG['kubernetes']}}}

    def test_confirmation_must_equal_exact_profile_before_inspection(self):
        with patch.object(cleanup, 'profiles') as profiles:
            with self.assertRaises(RuntimeError):
                cleanup.destroy('minikube')
            profiles.assert_not_called()

    def test_stopped_profile_requires_recorded_matching_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = Path(directory) / 'cluster-identity.json'
            identity.write_text(json.dumps({'profile': cleanup.PROFILE,
                                             'kube_system_uid': 'known'}))
            with patch.object(cleanup.lab_platform, 'IDENTITY', identity), \
                    patch.object(cleanup.lab_platform, 'guard') as guard:
                actual_identity, target = cleanup.validate_target(
                    {cleanup.PROFILE: self.profile()})
            self.assertEqual(actual_identity['kube_system_uid'], 'known')
            self.assertEqual(target['Name'], cleanup.PROFILE)
            guard.assert_not_called()

    def test_running_profile_also_requires_live_identity_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = Path(directory) / 'cluster-identity.json'
            identity.write_text(json.dumps({'profile': cleanup.PROFILE,
                                             'kube_system_uid': 'known'}))
            with patch.object(cleanup.lab_platform, 'IDENTITY', identity), \
                    patch.object(cleanup.lab_platform, 'guard') as guard:
                cleanup.validate_target({cleanup.PROFILE: self.profile('Running')})
            guard.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
