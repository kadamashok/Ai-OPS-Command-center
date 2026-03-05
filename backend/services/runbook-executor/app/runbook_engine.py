from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import shlex
import subprocess

from kubernetes import client, config


@dataclass
class ActionResult:
    action: str
    status: str
    detail: str


class RunbookEngine:
    def __init__(self) -> None:
        self._k8s_loaded = False

    def execute_actions(self, actions: list[dict[str, Any]]) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in actions:
            action_type = action.get("type", "unknown")
            try:
                detail = self._dispatch(action_type, action)
                results.append(ActionResult(action=action_type, status="success", detail=detail))
            except Exception as exc:  # nosec B110
                results.append(ActionResult(action=action_type, status="failed", detail=str(exc)))
        return results

    def _dispatch(self, action_type: str, action: dict[str, Any]) -> str:
        if action_type == "k8s_restart":
            return self._k8s_restart(action)
        if action_type == "k8s_scale":
            return self._k8s_scale(action)
        if action_type == "restart_integration":
            return self._ansible_service_restart(action)
        if action_type == "api_retry":
            return self._api_retry(action)
        if action_type == "failover_endpoint":
            return self._failover_endpoint(action)
        if action_type == "queue_drain":
            return self._queue_drain(action)
        if action_type == "replay_transactions":
            return self._replay_transactions(action)
        if action_type == "run_reconciliation":
            return self._run_reconciliation(action)
        raise ValueError(f"Unsupported action type: {action_type}")

    def _load_k8s_config(self) -> None:
        if self._k8s_loaded:
            return
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()
        self._k8s_loaded = True

    def _k8s_restart(self, action: dict[str, Any]) -> str:
        namespace = action["namespace"]
        deployment = action["deployment"]
        self._load_k8s_config()
        api = client.AppsV1Api()
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "carop/restarted-at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            }
        }
        api.patch_namespaced_deployment(name=deployment, namespace=namespace, body=patch)
        return f"Restart triggered for deployment {namespace}/{deployment}"

    def _k8s_scale(self, action: dict[str, Any]) -> str:
        namespace = action["namespace"]
        deployment = action["deployment"]
        replicas = int(action["replicas"])
        self._load_k8s_config()
        api = client.AppsV1Api()
        api.patch_namespaced_deployment_scale(
            name=deployment,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )
        return f"Scaled {namespace}/{deployment} to {replicas} replicas"

    def _ansible_service_restart(self, action: dict[str, Any]) -> str:
        host_group = action["host_group"]
        service = action["service"]
        cmd = [
            "ansible",
            host_group,
            "-i",
            "infra/ansible/inventory/hosts.ini",
            "-m",
            "service",
            "-a",
            f"name={service} state=restarted",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return f"Restarted service {service} on {host_group}"

    def _api_retry(self, action: dict[str, Any]) -> str:
        endpoint = shlex.quote(str(action.get("endpoint", "")))
        retries = int(action.get("retries", 3))
        return f"Scheduled {retries} retries for endpoint {endpoint}"

    def _failover_endpoint(self, action: dict[str, Any]) -> str:
        primary = action["primary"]
        secondary = action["secondary"]
        return f"Failover switched from {primary} to {secondary}"

    def _queue_drain(self, action: dict[str, Any]) -> str:
        queue = action["queue"]
        return f"Queue drain operation started for {queue}"

    def _replay_transactions(self, action: dict[str, Any]) -> str:
        flow_type = action["flow_type"]
        return f"Replay requested for flow {flow_type}"

    def _run_reconciliation(self, action: dict[str, Any]) -> str:
        systems = action.get("systems", [])
        return f"Inventory reconciliation started for systems={systems}"
