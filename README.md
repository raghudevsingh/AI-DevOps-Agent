# Deployment Failure Investigator

A read-only starter project that turns GitHub Actions and Kubernetes failure evidence into a concise diagnosis and suggested next steps.

## What it does

- Accepts deployment logs and optional Kubernetes diagnostics as text files.
- Detects common failure patterns (image pull errors, crash loops, failed probes, missing configuration, permission errors, and resource pressure).
- Produces a Markdown report with evidence, likely cause, and suggestions.
- Runs locally or in Docker. A GitHub Actions workflow example shows how to collect evidence after a failed deployment job.

By default it uses explainable local rules and needs no credentials. Pass `--ollama` to use a local Ollama model without sending logs to a cloud API, or `--ai` to use OpenAI's API. All modes are read-only: they never apply fixes or change a cluster.

## Quick start

```bash
python -m deployment_investigator --logs deployment.log --k8s kubernetes.txt --output report.md
```

Either `--logs` or `--k8s` may be omitted, but at least one is required. Use `--stdin` to read combined evidence from standard input.

```bash
cat deployment.log | python -m deployment_investigator --stdin
```

## OpenAI analysis

Install the optional OpenAI dependency:

```cmd
py -m pip install -e ".[openai]"
```

Create an API key in the OpenAI Platform, then set it in the current Windows Command Prompt session (replace the example value; do not share or commit the key):

```cmd
set OPENAI_API_KEY=your_api_key_here
```

Run AI-backed analysis:

```cmd
py -m deployment_investigator --ai --k8s k8s.txt --output report.md
```

The default model is `gpt-6-astra`. Override it with `--model MODEL_NAME` or the `OPENAI_MODEL` environment variable. The model receives the supplied evidence and returns structured findings with supporting evidence, confidence, and suggestions. Logs are treated as untrusted input; the model cannot access Kubernetes or execute commands.

## Local AI with Ollama

Install Ollama for Windows from [ollama.com/download](https://ollama.com/download), then open CMD and download a local model:

```cmd
ollama pull qwen3.5:4b
```

Run analysis with the local model:

```cmd
py -m deployment_investigator --ollama --k8s k8s.txt --output report.md
```

Ollama runs the model locally and serves its API on `http://localhost:11434`. The default model is `qwen3.5:4b`; override with `--model MODEL_NAME` or set `OLLAMA_MODEL`. The first model download requires an internet connection; inference then runs locally. Model performance and speed depend on available memory and hardware.

## Docker

```bash
docker build -t deployment-investigator .
docker run --rm -v "${PWD}:/work" deployment-investigator --logs /work/deployment.log --output /work/report.md
```

## GitHub Actions integration

`.github/workflows/investigate-failure.yml` listens for a failed workflow run named `Deploy`, downloads that run's logs, and uploads `investigation.md` as an artifact. Change `workflows: ["Deploy"]` to the exact `name:` of your deployment workflow before using it. The investigator workflow needs Actions read permission; it already requests only `actions: read` and `contents: read`.

To include Kubernetes diagnostics, add a step to the deployment workflow after the deploy step. It must run even when deployment fails and upload a file named `k8s.txt` in an artifact named `deployment-evidence`. For example, after configuring `kubectl` and setting `K8S_NAMESPACE` in that workflow:

```yaml
- name: Capture Kubernetes diagnostics
  if: failure()
  env:
    K8S_NAMESPACE: ${{ vars.K8S_NAMESPACE }}
  run: |
    mkdir -p evidence
    kubectl get pods -n "$K8S_NAMESPACE" -o wide > evidence/k8s.txt || true
    kubectl get events -n "$K8S_NAMESPACE" --sort-by=.lastTimestamp >> evidence/k8s.txt || true
    kubectl describe pods -n "$K8S_NAMESPACE" >> evidence/k8s.txt || true
- uses: actions/upload-artifact@v4
  if: failure()
  with:
    name: deployment-evidence
    path: evidence/k8s.txt
    if-no-files-found: ignore
```

The investigator downloads this optional artifact and includes it in its report when present. Keep secrets out of diagnostic artifacts. The hosted GitHub runner uses the rules-based analyzer by default; your PC's Ollama model is not available to it. To use local AI in automation, a self-hosted runner with Ollama installed would be needed.

## MCP integration

MCP is not connected yet. The next extension is a read-only MCP tool adapter that gathers workflow logs and Kubernetes events, then passes that evidence to an analyzer. Keep tool access read-only and pass only the minimum log context needed.

## Development

Requires Python 3.11+. Run with `python -m deployment_investigator --help`.
