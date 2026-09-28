"""Check that missing prerequisites and conflicting profiles cannot pass silently."""

import json
import subprocess
import unittest
from unittest.mock import patch

from scripts import doctor


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((doctor.ROOT / "config/lab.json").read_text())

    def test_missing_tool_fails_without_execution(self):
        with patch.object(doctor.shutil, "which", return_value=None), \
             patch.object(doctor, "run_command") as run:
            self.assertEqual(doctor.tool_check("tofu", "1.10.6", {})[0], "FAIL")
            run.assert_not_called()

    def test_version_mismatch_fails(self):
        with patch.object(doctor.shutil, "which", return_value="/bin/minikube"), \
             patch.object(doctor, "run_command", return_value=(0, "v1.36.0", "")):
            self.assertEqual(doctor.tool_check("minikube", "1.37.0", {})[0], "FAIL")

    def test_pinned_cli_version_formats(self):
        samples = {
            "minikube": "v1.37.0\n",
            "kubectl": '{"clientVersion": {"gitVersion": "v1.34.12"}}',
            "helm": "v3.19.0+g3d8990f\n",
            "tofu": '{"terraform_version": "1.10.6"}',
        }
        for tool, output in samples.items():
            with self.subTest(tool=tool), \
                 patch.object(doctor.shutil, "which", return_value="/bin/tool"), \
                 patch.object(doctor, "run_command", return_value=(0, output, "")):
                self.assertEqual(doctor.tool_check(tool, self.config["tools"][tool], {})[0], "PASS")

    def test_tool_timeout_fails(self):
        with patch.object(doctor.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("minikube", 15)):
            self.assertEqual(doctor.run_command(["minikube", "version"])[0], 1)

    def test_unrelated_profile_is_not_a_conflict(self):
        inventory = {"valid": [{"Name": "minikube", "Config": {"Driver": "docker"}}]}
        self.assertEqual(doctor.profile_check(json.dumps(inventory), self.config)[0], "INFO")

    def test_conflicting_lab_profile_fails(self):
        inventory = {"valid": [{"Name": "agentic-devops", "Config": {"Driver": "docker"}}]}
        self.assertEqual(doctor.profile_check(json.dumps(inventory), self.config)[0], "FAIL")

    def test_invalid_inventory_fails(self):
        for output in ("not JSON", "{}", "[]", '{"valid": "unexpected"}'):
            with self.subTest(output=output):
                self.assertEqual(doctor.profile_check(output, self.config)[0], "FAIL")

    def test_matching_stopped_profile_is_configuration_only(self):
        inventory = {"valid": [{"Name": "agentic-devops", "Status": "Stopped", "Config": {
            "Driver": "qemu2", "Network": "builtin", "CPUs": 4, "Memory": 8192,
            "KubernetesConfig": {"KubernetesVersion": "v1.34.12", "CNI": "calico"},
        }}]}
        status, message = doctor.profile_check(json.dumps(inventory), self.config)
        self.assertEqual(status, "PASS")
        self.assertIn("Stopped", message)

    def test_running_matching_vm_does_not_reserve_memory_twice(self):
        inventory = {"valid": [{"Name": "agentic-devops", "Status": "OK", "Config": {
            "Driver": "qemu2", "Network": "builtin", "CPUs": 4, "Memory": 8192,
            "KubernetesConfig": {"KubernetesVersion": "v1.34.12", "CNI": "calico"},
        }}]}
        self.assertEqual(doctor.available_memory_check(7000, self.config, json.dumps(inventory))[0], 'INFO')
        inventory['valid'][0]['Status'] = 'Stopped'
        self.assertEqual(doctor.available_memory_check(7000, self.config, json.dumps(inventory))[0], 'FAIL')
        inventory['valid'][0]['Status'] = 'OK'
        inventory['valid'][0]['Config']['Memory'] = 4096
        self.assertEqual(doctor.available_memory_check(7000, self.config, json.dumps(inventory))[0], 'FAIL')


if __name__ == "__main__":
    unittest.main()
