"""Print ranked collaboration routes for one client or need."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "public" / "data" / "network-matches.json"

parser = argparse.ArgumentParser()
parser.add_argument("--client", help="Client ID, for example CL-0014")
parser.add_argument("--need", help="Need ID, for example CN-013")
args = parser.parse_args()

payload = json.loads(DATA.read_text(encoding="utf-8"))
needs = payload["needs"]
if args.client:
    needs = [need for need in needs if need["clientId"] == args.client]
if args.need:
    needs = [need for need in needs if need["needId"] == args.need]

if not needs:
    raise SystemExit("No matching open need.")

for need in needs:
    amount = f"{need['currency']} {need['amount']:,.0f}" if need["amount"] and need["currency"] else "Amount not specified"
    print(f"\n{need['needId']}  {need['clientName']}  |  {need['title']}")
    print(f"{amount}  |  urgency: {need['urgency']}  |  route tiers used: {need['usedTiers']}")
    for candidate in [item for item in need["candidates"] if item["recommended"]]:
        path = " -> ".join(candidate["path"])
        print(f"  [{candidate['routeLabel']}] {candidate['providerName']} ({candidate['score']:.1f})")
        print(f"    {candidate['rationale']}")
        print(f"    Path: {path}")
        print(f"    Next: {candidate['nextAction']}")
