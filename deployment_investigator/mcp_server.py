"""Read-only MCP tools for deployment failure investigation."""

from __future__ import annotations

import re
import subprocess

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .analyzer import RuleBasedAnalyzer, render_report


mcp = FastMCP("Deployment Failure Investigator")
_MAX_EVIDENCE_CHARS = 200_000
_MAX_OUTPUT_CHARS = 40_000


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def analyze_deployment_evidence(
    deployment_logs: str = "",
    kubernetes_diagnostics: str = "",
) -> str:
    """Analyze supplied deployment logs and Kubernetes diagnostics; never changes infrastructure."""
    evidence_parts = []
    if deployment_logs.strip():
        evidence_parts.append("## Deployment logs\n" + deployment_logs)
    if kubernetes_diagnostics.strip():
        evidence_parts.append("## Kubernetes diagnostics\n" + kubernetes_diagnostics)
    evidence = "\n\n".join(evidence_parts)
    if not evidence:
        return "Provide deployment_logs or kubernetes_diagnostics to analyze."
    if len(evidence) > _MAX_EVIDENCE_CHARS:
        return f"Evidence is too large ({len(evidence)} characters). Limit it to {_MAX_EVIDENCE_CHARS} characters."
    return render_report(RuleBasedAnalyzer().analyze(evidence))


def _valid_name(value: str, *, allow_dots: bool = False) -> bool:
    if not value or len(value) > (253 if allow_dots else 63):
        return False
    interior = r"[a-z0-9.-]*" if allow_dots else r"[a-z0-9-]*"
    return re.fullmatch(rf"[a-z0-9](?:{interior}[a-z0-9])?", value) is not None


def _kubectl(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["kubectl", *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=25,
            check=False,
        )
    except FileNotFoundError:
        return "kubectl was not found. Install kubectl and ensure it is on PATH."
    except subprocess.TimeoutExpired:
        return f"kubectl {' '.join(args)} timed out after 25 seconds."
    output = result.stdout.strip()
    error = result.stderr.strip()
    if result.returncode:
        return f"Command failed (exit {result.returncode}).\n{error or output}"
    return output or (error if error else "(no output)")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
def collect_kubernetes_diagnostics(namespace: str = "default", pod_name: str = "") -> str:
    """Collect read-only pod status and events; optionally include one pod's description and recent logs."""
    if not _valid_name(namespace):
        return "Invalid namespace. Use a Kubernetes namespace name (lowercase letters, digits, and hyphens)."
    if pod_name and not _valid_name(pod_name, allow_dots=True):
        return "Invalid pod name. Use a Kubernetes pod name (lowercase letters, digits, hyphens, and dots)."

    sections = [
        "## Pods\n" + _kubectl(["get", "pods", "-n", namespace, "-o", "wide"]),
        "## Recent namespace events\n" + _kubectl(["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"]),
    ]
    if pod_name:
        sections.extend(
            [
                f"## Pod description: {pod_name}\n" + _kubectl(["describe", "pod", pod_name, "-n", namespace]),
                f"## Previous container logs: {pod_name}\n" + _kubectl(["logs", pod_name, "-n", namespace, "--all-containers=true", "--previous", "--tail=200"]),
                f"## Current container logs: {pod_name}\n" + _kubectl(["logs", pod_name, "-n", namespace, "--all-containers=true", "--tail=200"]),
            ]
        )
    result = "\n\n".join(sections)
    if len(result) > _MAX_OUTPUT_CHARS:
        result = result[:_MAX_OUTPUT_CHARS] + "\n\n[Output truncated to protect the MCP client from oversized diagnostics.]"
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
def investigate_kubernetes_failure(namespace: str = "default", pod_name: str = "") -> str:
    """Collect Kubernetes diagnostics and immediately produce an advisory failure report."""
    diagnostics = collect_kubernetes_diagnostics(namespace=namespace, pod_name=pod_name)
    if (
        "kubectl was not found" in diagnostics
        or "Command failed (exit" in diagnostics
        or "timed out after 25 seconds" in diagnostics
    ):
        return "Could not complete Kubernetes diagnostics collection. Check the kubectl output below.\n\n" + diagnostics
    if "## Pods\nNo resources found" in diagnostics:
        return (
            "No workload pods were found in this namespace, so there is no pod failure to diagnose.\n\n"
            + diagnostics
        )
    return render_report(RuleBasedAnalyzer().analyze("## Kubernetes diagnostics\n" + diagnostics))


def main() -> None:
    """Run the MCP server over stdio for a local MCP host."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
