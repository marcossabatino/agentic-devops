"""Inspect local prerequisites without installing tools or changing clusters."""

import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION_ARGS = {
    "minikube": ["version", "--short"],
    "kubectl": ["version", "--client", "-o", "json"],
    "qemu-system-x86_64": ["--version"],
    "qemu-img": ["--version"],
    "ansible-playbook": ["--version"],
    "helm": ["version", "--short"],
    "tofu": ["version", "-json"],
}


def run_command(argv, env=None):
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=15, env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout, result.stderr


def tool_check(name, expected, env):
    if shutil.which(name) is None:
        return "FAIL", f"{name}: missing from PATH (required {expected})"
    code, output, _ = run_command([name, *VERSION_ARGS[name]], env)
    if code:
        return "FAIL", f"{name}: version check failed or timed out"
    try:
        if name == "kubectl":
            output = json.loads(output)["clientVersion"]["gitVersion"]
        elif name == "tofu":
            output = json.loads(output)["terraform_version"]
        match = re.search(r"\bv?(\d+\.\d+\.\d+)\b", output)
        actual = match.group(1) if match else "unknown"
    except (ValueError, KeyError, TypeError):
        return "FAIL", f"{name}: invalid version output"
    status = "PASS" if actual == expected else "FAIL"
    return status, f"{name}: {actual} (required {expected})"


def profile_check(output, config):
    """Inspect only the selected lab profile, leaving unrelated profiles alone."""
    try:
        profiles = json.loads(output)
        if not isinstance(profiles, dict) or "valid" not in profiles:
            return "FAIL", "Minikube inventory is missing the valid-profile list"
        if any(profiles.get(key) is not None and not isinstance(profiles[key], list)
               for key in ("valid", "invalid")):
            return "FAIL", "Minikube inventory contains an invalid profile list"
        for item in profiles.get("invalid") or []:
            if item.get("Name") == config["profile"]:
                return "FAIL", "lab profile exists but Minikube reports it invalid"
        for item in profiles.get("valid") or []:
            if item["Name"] != config["profile"]:
                continue
            current = item["Config"]
            checks = {
                "Driver": config["driver"],
                "Network": config["network"],
                "CPUs": config["cpus"],
                "Memory": config["memory_mib"],
            }
            mismatches = [key for key, value in checks.items()
                          if current.get(key) != value]
            cluster = current.get("KubernetesConfig", {})
            if cluster.get("KubernetesVersion") != "v" + config["kubernetes"]:
                mismatches.append("KubernetesVersion")
            if cluster.get("CNI") != config["cni"]:
                mismatches.append("CNI")
            if mismatches:
                return "FAIL", "lab profile differs: " + ", ".join(mismatches)
            return "PASS", f"lab profile configuration matches; status={item.get('Status')}"
        return "INFO", "lab profile not created yet; expected before bootstrap"
    except (ValueError, KeyError, TypeError, AttributeError):
        return "FAIL", "unable to parse Minikube profile inventory"


def available_memory_check(available_mib, config, inventory):
    """A matching running VM already owns its RAM; do not reserve it twice."""
    try:
        matching = profile_check(inventory, config)[0] == 'PASS'
        running = any(item.get('Name') == config['profile'] and item.get('Status') == 'OK'
                      for item in json.loads(inventory).get('valid', []))
        if matching and running:
            return 'INFO', f'available RAM: {available_mib:.0f} MiB; matching lab VM already running'
    except (ValueError, TypeError, AttributeError):
        pass
    status = 'PASS' if available_mib >= config['memory_mib'] else 'FAIL'
    return status, f'available RAM: {available_mib:.0f} MiB; VM startup requires {config["memory_mib"]}'


def main():
    config = json.loads((ROOT / "config/lab.json").read_text())
    inventory_code, inventory, _ = run_command(['minikube', 'profile', 'list', '-o', 'json']) if shutil.which('minikube') else (1, '', '')
    failures = 0

    def report(status, message):
        nonlocal failures
        failures += status == "FAIL"
        print(f"{status:4} {message}")

    def require(condition, message):
        report("PASS" if condition else "FAIL", message)

    print(f"Local preflight: {config['profile']} / {config['driver']} / {config['network']}")
    require(platform.system() == "Linux" and platform.machine() == "x86_64",
            "this baseline targets Linux x86_64")
    cpus = os.cpu_count() or 0
    require(cpus >= config["cpus"], f"host CPUs: {cpus}; VM requires {config['cpus']}")
    try:
        memory = dict(re.findall(r"^(MemTotal|MemAvailable):\s+(\d+)",
                                 Path('/proc/meminfo').read_text(), re.MULTILINE))
        total_gib = int(memory["MemTotal"]) / 1024**2
        available_mib = int(memory["MemAvailable"]) / 1024
        require(total_gib >= config["minimum_host_memory_gib"],
                f"host RAM: {total_gib:.1f} GiB; minimum {config['minimum_host_memory_gib']}")
        report(*available_memory_check(available_mib, config, inventory))
    except (OSError, KeyError, ValueError):
        report("FAIL", "cannot inspect host memory")
    free_gib = shutil.disk_usage(Path.home()).free / 1024**3
    require(free_gib >= config["minimum_free_disk_gib"],
            f"free disk on home filesystem: {free_gib:.1f} GiB")
    require(os.access('/dev/kvm', os.R_OK | os.W_OK),
            "KVM device readable/writable (a sandbox may hide /dev/kvm)")
    # Ansible creates a temporary directory even for --version. Remove it on exit.
    with tempfile.TemporaryDirectory(prefix="agentic-devops-doctor-") as tmp:
        env = dict(os.environ, ANSIBLE_LOCAL_TEMP=tmp)
        for tool, expected in config["tools"].items():
            report(*tool_check(tool, expected, env))
    if shutil.which("minikube"):
        # Minikube also returns a nonzero exit code for an empty profile inventory.
        if inventory.strip():
            report(*profile_check(inventory, config))
        else:
            report("FAIL", f"cannot inspect Minikube profiles (exit {inventory_code})")
    if shutil.which("kubectl"):
        code, context, _ = run_command(["kubectl", "config", "current-context"])
        if not code and context.strip() == config["profile"]:
            report("INFO", "current kubectl context is the lab")
        else:
            report("INFO", "current context is unset or outside the lab; use an explicit lab context")
    print(f"\n{failures} prerequisite failure(s). No cluster readiness or acceptance tests were run.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
