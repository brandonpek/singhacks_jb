"""Build a compact, browser-ready JSON model from the hackathon CSV files."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "singhacks-jb-wealth-intelligence" / "data"
OUTPUT = Path(__file__).resolve().parents[1] / "public" / "data" / "dashboard.json"
TODAY = "2026-08-26"


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


clients = read_csv("clients.csv")
portfolios = read_csv("portfolios.csv")
holdings = read_csv("holdings.csv")
instruments = read_csv("instruments.csv")
mandates = read_csv("mandates.csv")
facilities = read_csv("credit_facilities.csv")
cash_needs = read_csv("planned_cash_needs.csv")
commitments = read_csv("commitments.csv")
market = read_csv("market_context.csv")
events = read_csv("event_log.csv")
with (DATA / "rm_notes.json").open(encoding="utf-8") as handle:
    notes = json.load(handle)

portfolio_by_id = {row["portfolio_id"]: row for row in portfolios}
instrument_by_id = {row["instrument_id"]: row for row in instruments}
mandate_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
for row in mandates:
    mandate_rows[row["mandate_code"]].append(row)

current = [row for row in holdings if row["snapshot_date"] == TODAY]
current_by_client: dict[str, list[dict[str, str]]] = defaultdict(list)
for row in current:
    current_by_client[row["client_id"]].append(row)

book_by_date: dict[str, float] = defaultdict(float)
for row in holdings:
    book_by_date[row["snapshot_date"]] += number(row["market_value_usd"])

book_allocation: dict[str, float] = defaultdict(float)
book_liquidity: dict[str, float] = defaultdict(float)
for row in current:
    book_allocation[row["asset_class"]] += number(row["market_value_usd"])
    book_liquidity[row["liquidity_tier"]] += number(row["market_value_usd"])
book_total = sum(book_allocation.values())

client_models = []
for client in clients:
    client_id = client["client_id"]
    client_holdings = current_by_client[client_id]
    client_total = sum(number(row["market_value_usd"]) for row in client_holdings)
    client_portfolios = [row for row in portfolios if row["client_id"] == client_id]

    allocation: dict[str, float] = defaultdict(float)
    liquidity: dict[str, float] = defaultdict(float)
    positions: dict[tuple[str, str], float] = defaultdict(float)
    for row in client_holdings:
        value = number(row["market_value_usd"])
        allocation[row["asset_class"]] += value
        liquidity[row["liquidity_tier"]] += value
        positions[(row["instrument_id"], row["instrument_name"])] += value

    history: dict[str, float] = defaultdict(float)
    for row in holdings:
        if row["client_id"] == client_id:
            history[row["snapshot_date"]] += number(row["market_value_usd"])

    reasons: list[str] = []
    score = 0
    allocation_breaches = []
    concentration_breaches = []
    sustainability_breaches = []

    for portfolio in client_portfolios:
        pid = portfolio["portfolio_id"]
        portfolio_positions = [row for row in client_holdings if row["portfolio_id"] == pid]
        if portfolio["service_model"] != "Custody":
            actual_by_asset: dict[str, float] = defaultdict(float)
            for row in portfolio_positions:
                actual_by_asset[row["asset_class"]] += number(row["weight_pct"])
            for band in mandate_rows[portfolio["mandate_code"]]:
                actual = actual_by_asset[band["asset_class"]]
                minimum, maximum = number(band["min_pct"]), number(band["max_pct"])
                if actual < minimum or actual > maximum:
                    allocation_breaches.append({
                        "portfolioId": pid,
                        "portfolio": portfolio["portfolio_name"],
                        "assetClass": band["asset_class"],
                        "actual": round(actual, 1),
                        "min": minimum,
                        "max": maximum,
                    })
            position_limit = number(mandate_rows[portfolio["mandate_code"]][0]["max_single_position_pct"])
            for row in portfolio_positions:
                instrument = instrument_by_id[row["instrument_id"]]
                if instrument["concentration_limit_applies"] == "Y" and number(row["weight_pct"]) > position_limit:
                    concentration_breaches.append({
                        "instrument": row["instrument_name"],
                        "actual": round(number(row["weight_pct"]), 1),
                        "limit": position_limit,
                    })
                if portfolio["mandate_name"] == "Sustainable Balanced" and instrument["sustainability_excluded"] == "Y":
                    sustainability_breaches.append(row["instrument_name"])

    if allocation_breaches:
        score += min(4, len(allocation_breaches))
        reasons.append(f"{len(allocation_breaches)} allocation band flag{'s' if len(allocation_breaches) != 1 else ''}")
    if concentration_breaches:
        score += min(4, len(concentration_breaches) + 1)
        reasons.append(f"{len(concentration_breaches)} direct concentration flag{'s' if len(concentration_breaches) != 1 else ''}")
    if sustainability_breaches:
        score += 4
        reasons.append(f"{len(sustainability_breaches)} sustainability exclusion{'s' if len(sustainability_breaches) != 1 else ''}")

    client_facilities = [row for row in facilities if row["client_id"] == client_id]
    facility_models = []
    for facility in client_facilities:
        trigger = number(facility["margin_call_ltv_pct"])
        current_ltv = number(facility[f"ltv_pct_{TODAY}"])
        prior_ltvs = [number(facility[f"ltv_pct_{date}"]) for date in sorted(book_by_date)]
        breached = any(value > trigger for value in prior_ltvs)
        if current_ltv > trigger:
            score += 5
            reasons.append("LTV is above its margin-call trigger")
        elif trigger - current_ltv <= 5:
            score += 3
            reasons.append("LTV is within 5 points of its trigger")
        elif breached:
            score += 2
            reasons.append("LTV breached its trigger earlier this year")
        facility_models.append({
            "type": facility["facility_type"],
            "trigger": trigger,
            "current": current_ltv,
            "history": [
                {"date": date, "ltv": number(facility[f"ltv_pct_{date}"])}
                for date in sorted(book_by_date)
            ],
        })

    illiquid_value = sum(value for tier, value in liquidity.items() if tier in {"Illiquid", "Quarterly Gate"})
    illiquid_pct = 100 * illiquid_value / client_total if client_total else 0
    if illiquid_pct > 25:
        score += 3
        reasons.append(f"{illiquid_pct:.0f}% illiquid or gated")
    elif illiquid_pct > 15:
        score += 1
        reasons.append(f"{illiquid_pct:.0f}% illiquid or gated")

    client_cash_needs = [row for row in cash_needs if row["client_id"] == client_id]
    client_commitments = [row for row in commitments if row["client_id"] == client_id]
    if client_commitments:
        score += 2
        reasons.append("Outstanding private-market commitments")

    client_notes = sorted([row for row in notes if row["client_id"] == client_id], key=lambda row: row["note_date"], reverse=True)
    top_positions = sorted(positions.items(), key=lambda item: item[1], reverse=True)[:6]

    client_models.append({
        "id": client_id,
        "name": client["client_name"],
        "bookingCentre": client["booking_centre"],
        "wealthBand": client["wealth_band"],
        "baseCurrency": client["base_currency"],
        "aum": number(client["total_aum_usd"]),
        "lifeStage": client["life_stage"],
        "riskProfile": client["risk_profile"],
        "riskTolerance": number(client["risk_tolerance_score"]),
        "liquidityNeeds": client["liquidity_needs"],
        "objectives": client["objectives"],
        "priorityScore": score,
        "priority": "Critical" if score >= 9 else "High" if score >= 6 else "Watch" if score >= 3 else "Stable",
        "reasons": reasons,
        "allocationBreaches": allocation_breaches,
        "concentrationBreaches": concentration_breaches,
        "sustainabilityBreaches": sustainability_breaches,
        "illiquidPct": round(illiquid_pct, 1),
        "allocation": [
            {"name": key, "value": round(100 * value / client_total, 1)}
            for key, value in sorted(allocation.items(), key=lambda item: item[1], reverse=True)
        ],
        "liquidity": [
            {"name": key, "value": round(100 * value / client_total, 1)}
            for key, value in sorted(liquidity.items(), key=lambda item: item[1], reverse=True)
        ],
        "history": [{"date": date, "value": round(value / 1_000_000, 2)} for date, value in sorted(history.items())],
        "topPositions": [
            {
                "id": instrument_id,
                "name": name,
                "value": round(value / 1_000_000, 2),
                "weight": round(100 * value / client_total, 1),
            }
            for (instrument_id, name), value in top_positions
        ],
        "facilities": facility_models,
        "cashNeeds": [
            {
                "description": row["description"],
                "amount": number(row["amount"]),
                "currency": row["currency"],
                "due": row["due_from"],
                "certainty": row["certainty"],
            }
            for row in client_cash_needs
        ],
        "commitments": [
            {
                "fund": row["fund_name"],
                "uncalled": number(row["uncalled"]),
                "currency": row["currency"],
                "window": row["expected_call_window"],
            }
            for row in client_commitments
        ],
        "latestNote": client_notes[0] if client_notes else None,
    })

client_models.sort(key=lambda row: (row["priorityScore"], row["aum"]), reverse=True)

market_watch = {"SPX", "GOLD_USD_OZ", "BRENT_USD_BBL", "UST_10Y_PCT", "VIX"}
market_by_series: dict[str, list[dict[str, str]]] = defaultdict(list)
for row in market:
    if row["series_id"] in market_watch:
        market_by_series[row["series_id"]].append(row)

market_series = []
for series_id, rows in market_by_series.items():
    rows.sort(key=lambda row: row["snapshot_date"])
    baseline = number(rows[0]["value"])
    market_series.append({
        "id": series_id,
        "name": rows[0]["series_name"],
        "values": [
            {
                "date": row["snapshot_date"],
                "raw": number(row["value"]),
                "index": round(100 * number(row["value"]) / baseline, 1),
            }
            for row in rows
        ],
    })

payload = {
    "asOf": TODAY,
    "summary": {
        "totalAum": round(sum(number(row["total_aum_usd"]) for row in clients), 2),
        "clientCount": len(clients),
        "portfolioCount": len(portfolios),
        "uhnwCount": sum(row["wealth_band"] == "UHNW" for row in clients),
        "allocationFlagPortfolios": len({
            breach["portfolioId"]
            for client in client_models
            for breach in client["allocationBreaches"]
        }),
        "dailyLiquidityPct": round(100 * book_liquidity["Daily"] / book_total, 1),
        "illiquidPct": round(100 * book_liquidity["Illiquid"] / book_total, 1),
    },
    "bookHistory": [{"date": date, "value": round(value / 1_000_000, 2)} for date, value in sorted(book_by_date.items())],
    "bookAllocation": [
        {"name": key, "value": round(100 * value / book_total, 1), "usd": round(value / 1_000_000, 1)}
        for key, value in sorted(book_allocation.items(), key=lambda item: item[1], reverse=True)
    ],
    "bookLiquidity": [
        {"name": key, "value": round(100 * value / book_total, 1)}
        for key, value in sorted(book_liquidity.items(), key=lambda item: item[1], reverse=True)
    ],
    "marketSeries": sorted(market_series, key=lambda row: row["id"]),
    "events": [row for row in events if row["severity"] in {"High", "Severe"}],
    "clients": client_models,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"Wrote {OUTPUT} ({len(client_models)} clients)")
