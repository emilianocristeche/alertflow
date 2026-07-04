#!/usr/bin/env python3
"""AlertFlow — AI-powered on-call assistant CLI."""
import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from llm import analyze_alert
from webhook import send_discord, send_slack

_SEVERITY_ICONS = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}


def _print_result(result: dict) -> None:
    icon = _SEVERITY_ICONS.get(result["severity"], "⚪")
    print(f"\n{icon}  Severity:   {result['severity']}")
    print(f"    Category:  {result['root_cause_category']}")
    print(f"    Summary:   {result['summary']}\n")
    print("    Runbook:")
    for i, step in enumerate(result["runbook"], 1):
        print(f"      {i}. {step}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="alertflow",
        description="AlertFlow — AI-powered on-call assistant",
    )
    parser.add_argument("alert", nargs="?", help="Alert or incident description")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output raw JSON")
    parser.add_argument("--notify", action="store_true", help="Send to Discord/Slack webhooks")
    args = parser.parse_args()

    if not args.alert:
        parser.print_help()
        sys.exit(1)

    try:
        result = analyze_alert(args.alert)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.notify:
        send_discord(result, args.alert)
        send_slack(result, args.alert)

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_result(result)


if __name__ == "__main__":
    main()
