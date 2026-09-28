"""Prevent cluster identity mistakes from becoming platform writes."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import lab_platform


class PlatformGuardTests(unittest.TestCase):
    def test_missing_identity_blocks_platform_actions(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(lab_platform, 'IDENTITY', Path(tmp) / 'identity.json'), \
                patch.object(lab_platform, 'cluster_identity', return_value={'profile': 'agentic-devops', 'kube_system_uid': 'new'}):
            with self.assertRaises(RuntimeError):
                lab_platform.guard()

    def test_replaced_cluster_is_not_silently_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'identity.json'
            path.write_text(json.dumps({'profile': 'agentic-devops', 'kube_system_uid': 'original'}))
            with patch.object(lab_platform, 'IDENTITY', path), \
                    patch.object(lab_platform, 'cluster_identity', return_value={'profile': 'agentic-devops', 'kube_system_uid': 'replacement'}):
                with self.assertRaises(RuntimeError):
                    lab_platform.guard(record=True)
            self.assertEqual(json.loads(path.read_text())['kube_system_uid'], 'original')

    def test_missing_credentials_with_existing_storage_does_not_rotate_passwords(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(lab_platform, 'PRIVATE', Path(tmp)), \
                patch.object(lab_platform, 'kubectl') as kubectl:
            kubectl.return_value.stdout = 'persistentvolumeclaim/data-postgres-0'
            with self.assertRaises(RuntimeError):
                lab_platform.credentials()
            self.assertFalse((Path(tmp) / 'credentials.json').exists())
