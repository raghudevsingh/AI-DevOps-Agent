"""Explainable baseline analyzer; replace or extend behind this interface."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    title: str
    cause: str
    evidence: tuple[str, ...]
    suggestions: tuple[str, ...]
    confidence: str = "medium"


class Analyzer(Protocol):
    def analyze(self, evidence: str) -> list[Finding]: ...


_RULES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "Image pull failure",
        "Kubernetes could not retrieve the requested container image.",
        ("ImagePullBackOff", "ErrImagePull", "manifest unknown", "pull access denied"),
        ("Verify the image name and tag exist in the registry.", "Check the image pull secret and its access to the registry."),
    ),
    (
        "Container crash loop",
        "The container starts and exits repeatedly, or Kubernetes cannot keep it running.",
        ("CrashLoopBackOff", "Back-off restarting failed container"),
        ("Inspect the container's previous logs and exit code.", "Check startup configuration, dependencies, and the container entrypoint."),
    ),
    (
        "Health probe failure",
        "A readiness or liveness probe is failing, so Kubernetes considers the application unhealthy.",
        ("Readiness probe failed", "Liveness probe failed", "Startup probe failed", "HTTP probe failed"),
        ("Confirm the probe path, port, and protocol match the application.", "Check startup timeouts and whether the application binds to the expected interface."),
    ),
    (
        "Missing or invalid configuration",
        "The deployment appears to be missing a required setting or secret, or a supplied value is invalid.",
        ("CreateContainerConfigError", "secret .* not found", "configmap .* not found", "environment variable .* not set", "Missing required configuration"),
        ("Verify referenced Secret and ConfigMap names exist in the target namespace.", "Check required environment variables and secret key names without exposing secret values."),
    ),
    (
        "Insufficient permissions",
        "An operation was rejected because the workflow, service account, or identity may lack permission.",
        ("permission denied", "forbidden:", "unauthorized", "AccessDenied", " not authorized"),
        ("Identify the principal and denied operation in the surrounding log context.", "Grant only the specific missing permission, then rerun the deployment."),
    ),
    (
        "Resource pressure",
        "The workload may be exceeding its memory or CPU limits, or the cluster may not have capacity.",
        ("OOMKilled", "OutOfMemory", "memory cgroup out of memory", "Insufficient cpu", "Insufficient memory"),
        ("Check pod resource requests, limits, and recent usage.", "Confirm the cluster has capacity before changing resource settings."),
    ),
    (
        "Deployment did not become available",
        "The rollout timed out or did not reach its desired available replica count.",
        ("ProgressDeadlineExceeded", "timed out waiting for the condition", "deployment exceeded its progress deadline"),
        ("Inspect rollout status, pod events, and the ReplicaSet for the first underlying failure.", "Check whether the rollout deadline is appropriate after addressing the root cause."),
    ),
)


class RuleBasedAnalyzer:
    """Find known failure signatures while retaining the matching log evidence."""

    def analyze(self, evidence: str) -> list[Finding]:
        import re

        lines = evidence.splitlines()
        findings: list[Finding] = []
        normalized_rules = [(title, cause, patterns, suggestions) for title, cause, patterns, suggestions in _RULES]
        for title, cause, patterns, suggestions in normalized_rules:
            matches = [
                line.strip()
                for line in lines
                if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns)
            ]
            if matches:
                findings.append(Finding(title, cause, tuple(dict.fromkeys(matches[:5])), suggestions))
        if not findings:
            findings.append(
                Finding(
                    "No known failure signature found",
                    "The supplied evidence does not match the investigator's current rule set.",
                    tuple(line.strip() for line in lines if line.strip())[:5],
                    ("Inspect the earliest error above the final deployment failure.", "Add relevant pod events and container logs, then investigate again."),
                    confidence="low",
                )
            )
        return findings


def render_report(findings: list[Finding], evidence: str = "") -> str:
    sections = ["# Deployment Failure Investigation", "", "This report is advisory. No deployment or cluster changes were made."]
    if "Demo only: no cluster or deployment was changed." in evidence:
        sections.extend(["", "**Evidence source:** Simulated demo logs. This report does not describe a real cluster incident."])
    for finding in findings:
        sections.extend(["", f"## {finding.title}", "", f"**Likely cause:** {finding.cause}", f"**Confidence:** {finding.confidence}", "", "**Evidence:**"])
        sections.extend(f"- `{line.replace('`', chr(39))}`" for line in finding.evidence)
        sections.extend(["", "**Suggested checks:**"])
        sections.extend(f"- {suggestion}" for suggestion in finding.suggestions)
    return "\n".join(sections) + "\n"
