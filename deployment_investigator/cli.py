"""Command-line entry point."""

import argparse
import sys
from pathlib import Path

from .analyzer import RuleBasedAnalyzer, render_report
from .openai_analyzer import OpenAIAnalyzer
from .ollama_analyzer import OllamaAnalyzer


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze deployment logs and suggest likely next steps (read-only).")
    parser.add_argument("--logs", type=Path, help="Path to deployment or GitHub Actions log text")
    parser.add_argument("--k8s", type=Path, help="Path to Kubernetes events/status/log text")
    parser.add_argument("--stdin", action="store_true", help="Read combined evidence from standard input")
    parser.add_argument("--output", type=Path, help="Write Markdown report to this path instead of stdout")
    parser.add_argument("--ai", action="store_true", help="Use OpenAI for analysis instead of local rules")
    parser.add_argument("--ollama", action="store_true", help="Use a local Ollama model for analysis")
    parser.add_argument("--model", help="Model name for --ai or --ollama")
    args = parser.parse_args()

    if not args.stdin and not args.logs and not args.k8s:
        parser.error("provide --logs, --k8s, or --stdin")
    if args.ai and args.ollama:
        parser.error("choose only one of --ai or --ollama")
    chunks: list[str] = []
    for label, path in (("Deployment logs", args.logs), ("Kubernetes diagnostics", args.k8s)):
        if path:
            try:
                chunks.append(f"## {label}\n{path.read_text(encoding='utf-8', errors='replace')}")
            except OSError as exc:
                parser.error(f"cannot read {path}: {exc}")
    if args.stdin:
        chunks.append(f"## Input evidence\n{sys.stdin.read()}")
    if args.ai:
        analyzer = OpenAIAnalyzer(model=args.model)
    elif args.ollama:
        analyzer = OllamaAnalyzer(model=args.model)
    else:
        analyzer = RuleBasedAnalyzer()
    try:
        findings = analyzer.analyze("\n".join(chunks))
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return 2
    report = render_report(findings)
    if args.output:
        try:
            args.output.write_text(report, encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot write {args.output}: {exc}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
