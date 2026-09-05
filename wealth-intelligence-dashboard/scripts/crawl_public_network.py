#!/usr/bin/env python3
"""Stage source-linked public figures and relationships from Wikidata.

This crawler deliberately writes to a separate review database. It never edits
network/network.db or creates introduction-ready relationship paths.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import socket
import sqlite3
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


APP = Path(__file__).resolve().parents[1]
SCHEMA = APP / "network" / "public_network_schema.sql"
DEFAULT_DATABASE = APP / "network" / "public_network_staging.db"
DEFAULT_BROWSER_OUTPUT = APP / "public" / "data" / "public-network-staging.json"
ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_ITEM = "https://www.wikidata.org/wiki/"
DEFAULT_USER_AGENT = os.environ.get(
    "ACCESS_ALPHA_CRAWLER_USER_AGENT",
    "AccessAlphaPublicNetworkCrawler/0.1 (local review-staging prototype)",
)
OCCUPATIONS = {
    "Q43845": "businessperson",
    "Q131524": "entrepreneur",
    "Q806798": "banker",
    "Q12362622": "philanthropist",
    "Q557880": "investor",
    "Q16023665": "venture capitalist",
}
CAPABILITY_RULES = (
    (("entrepreneur", "businessperson"), "operating_business_experience", 0.55),
    (("banker", "investor", "venture capitalist"), "investment_and_capital_experience", 0.55),
    (("philanthropist",), "philanthropy_experience", 0.60),
)

PROFILES = {
    "elena-luxury-distribution": {
        "description": "Greater China luxury distribution, commerce platforms and brand principals",
        "person_ids": (
            "Q6830156",   # J. Michael Evans — Alibaba
            "Q18165291",  # Joseph Tsai — Alibaba
            "Q8991047",   # Liu Qiangdong — JD.com
            "Q9086912",   # Adrian Cheng — K11 / New World Development
            "Q557256",    # Victor Fung — Li & Fung
            "Q6216224",   # Johann Rupert — Richemont
            "Q1371822",   # Francois-Henri Pinault — Kering
            "Q3264974",   # Luca de Meo — Kering
            "Q32055",     # Bernard Arnault — LVMH
        ),
        "organization_keywords": (
            "alibaba",
            "jd.com",
            "jingdong",
            "k11",
            "new world development",
            "li & fung",
            "li and fung",
            "richemont",
            "kering",
            "lvmh",
        ),
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def value(binding: dict[str, Any], key: str, default: str = "") -> str:
    item = binding.get(key)
    return str(item.get("value", default)) if isinstance(item, dict) else default


def qid(uri: str) -> str:
    candidate = uri.rstrip("/").rsplit("/", 1)[-1]
    if not candidate.startswith("Q") or not candidate[1:].isdigit():
        raise ValueError(f"Unexpected Wikidata entity URI: {uri}")
    return candidate


def content_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def people_query(limit: int, min_sitelinks: int) -> str:
    occupation_values = " ".join(f"wd:{item}" for item in OCCUPATIONS)
    return f"""
SELECT ?person ?personLabel ?description ?sitelinks ?countryLabel ?occupationLabel WHERE {{
  VALUES ?occupation {{ {occupation_values} }}
  ?person wdt:P31 wd:Q5;
          wdt:P106 ?occupation;
          wikibase:sitelinks ?sitelinks;
          rdfs:label ?personLabel.
  FILTER(LANG(?personLabel) = "en")
  FILTER(?sitelinks >= {min_sitelinks})
  OPTIONAL {{ ?person schema:description ?description. FILTER(LANG(?description) = "en") }}
  OPTIONAL {{
    ?person wdt:P27 ?country.
    ?country rdfs:label ?countryLabel.
    FILTER(LANG(?countryLabel) = "en")
  }}
  ?occupation rdfs:label ?occupationLabel.
  FILTER(LANG(?occupationLabel) = "en")
}}
ORDER BY DESC(?sitelinks) ?personLabel
LIMIT {limit * 10}
""".strip()


def seeded_people_query(person_ids: tuple[str, ...]) -> str:
    values_clause = " ".join(f"wd:{item}" for item in person_ids)
    return f"""
SELECT ?person ?personLabel ?description ?sitelinks ?countryLabel ?occupationLabel WHERE {{
  VALUES ?person {{ {values_clause} }}
  ?person wdt:P31 wd:Q5;
          wikibase:sitelinks ?sitelinks;
          rdfs:label ?personLabel.
  FILTER(LANG(?personLabel) = "en")
  OPTIONAL {{ ?person schema:description ?description. FILTER(LANG(?description) = "en") }}
  OPTIONAL {{
    ?person wdt:P27 ?country.
    ?country rdfs:label ?countryLabel.
    FILTER(LANG(?countryLabel) = "en")
  }}
  OPTIONAL {{
    ?person wdt:P106 ?occupation.
    ?occupation rdfs:label ?occupationLabel.
    FILTER(LANG(?occupationLabel) = "en")
  }}
}}
ORDER BY ?personLabel
""".strip()


def relationships_query(person_ids: list[str]) -> str:
    values_clause = " ".join(f"wd:{item}" for item in person_ids)
    return f"""
SELECT ?person ?related ?relatedLabel ?relatedDescription ?relationshipType WHERE {{
  VALUES ?person {{ {values_clause} }}
  {{
    VALUES (?relationshipProperty ?relationshipType) {{
      (wdt:P108 "employed_by")
      (wdt:P463 "member_of")
      (wdt:P1416 "affiliated_with")
    }}
    ?person ?relationshipProperty ?related.
  }} UNION {{
    VALUES (?inverseProperty ?relationshipType) {{
      (wdt:P112 "founded")
      (wdt:P169 "leads")
      (wdt:P488 "chairs")
    }}
    ?related ?inverseProperty ?person.
  }}
  ?related rdfs:label ?relatedLabel.
  FILTER(LANG(?relatedLabel) = "en")
  OPTIONAL {{ ?related schema:description ?relatedDescription. FILTER(LANG(?relatedDescription) = "en") }}
}}
ORDER BY ?person ?relationshipType ?relatedLabel
""".strip()


def fetch_bindings(query: str, user_agent: str, timeout: int, retries: int) -> list[dict[str, Any]]:
    url = f"{ENDPOINT}?{urlencode({'query': query, 'format': 'json'})}"
    headers = {
        "Accept": "application/sparql-results+json",
        "Accept-Encoding": "gzip,deflate",
        "User-Agent": user_agent,
    }
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(20_000_001)
                if len(raw) > 20_000_000:
                    raise RuntimeError("Wikidata response exceeded the 20 MB safety limit")
                content_encoding = response.headers.get("Content-Encoding")
                if content_encoding == "gzip":
                    raw = gzip.decompress(raw)
                elif content_encoding == "deflate":
                    raw = zlib.decompress(raw)
                payload = json.loads(raw.decode("utf-8"))
                return list(payload.get("results", {}).get("bindings", []))
        except HTTPError as error:
            if error.code == 429 and attempt < retries:
                retry_after = min(60, int(error.headers.get("Retry-After", "5")))
                time.sleep(retry_after)
                continue
            if 500 <= error.code < 600 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Wikidata returned HTTP {error.code}") from error
        except (socket.timeout, TimeoutError, URLError) as error:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Could not reach Wikidata: {error}") from error
    return []


def transform_people(bindings: list[dict[str, Any]], limit: int) -> dict[str, dict[str, Any]]:
    people: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        person_id = qid(value(binding, "person"))
        record = people.setdefault(person_id, {
            "source_id": person_id,
            "actor_type": "individual",
            "display_name": value(binding, "personLabel"),
            "description": value(binding, "description") or None,
            "countries": set(),
            "prominence_score": 0,
            "source_url": f"{WIKIDATA_ITEM}{person_id}",
            "occupations": set(),
        })
        country = value(binding, "countryLabel")
        occupation = value(binding, "occupationLabel")
        if country:
            record["countries"].add(country)
        if occupation:
            record["occupations"].add(occupation.lower())
        try:
            record["prominence_score"] = max(record["prominence_score"], int(value(binding, "sitelinks", "0")))
        except ValueError:
            pass
    ranked = sorted(people.values(), key=lambda item: (-item["prominence_score"], item["display_name"]))[:limit]
    return {item["source_id"]: item for item in ranked}


def transform_relationships(
    bindings: list[dict[str, Any]],
    people: dict[str, dict[str, Any]],
    organization_keywords: tuple[str, ...] = (),
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    organizations: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        person_id = qid(value(binding, "person"))
        if person_id not in people:
            continue
        organization_id = qid(value(binding, "related"))
        relationship_type = value(binding, "relationshipType")
        if relationship_type not in {"employed_by", "member_of", "affiliated_with", "founded", "leads", "chairs"}:
            continue
        organization_name = value(binding, "relatedLabel")
        if organization_keywords and not any(keyword in organization_name.lower() for keyword in organization_keywords):
            continue
        organizations.setdefault(organization_id, {
            "source_id": organization_id,
            "actor_type": "organization",
            "display_name": organization_name,
            "description": value(binding, "relatedDescription") or None,
            "countries": set(),
            "prominence_score": None,
            "source_url": f"{WIKIDATA_ITEM}{organization_id}",
            "occupations": set(),
        })
        stable_key = f"{person_id}:{relationship_type}:{organization_id}"
        relationship_id = f"WDREL-{hashlib.sha256(stable_key.encode('utf-8')).hexdigest()[:16]}"
        relationships[relationship_id] = {
            "relationship_id": relationship_id,
            "from_source_id": person_id,
            "to_source_id": organization_id,
            "relationship_type": relationship_type,
            "source_url": f"{WIKIDATA_ITEM}{person_id}",
        }
    return organizations, list(relationships.values())


def capability_tags(person: dict[str, Any]) -> list[dict[str, Any]]:
    haystack = " ".join(sorted(person["occupations"]))
    tags = []
    for keywords, tag, confidence in CAPABILITY_RULES:
        matches = [keyword for keyword in keywords if keyword in haystack]
        if matches:
            tags.append({
                "capability_tag": tag,
                "basis": f"Wikidata occupation: {', '.join(matches)}",
                "confidence": confidence,
            })
    return tags


def upsert_actor(connection: sqlite3.Connection, actor: dict[str, Any], run_id: str, retrieved_at: str) -> None:
    country = " | ".join(sorted(actor["countries"])) or None
    canonical = {
        "actor_type": actor["actor_type"],
        "display_name": actor["display_name"],
        "description": actor["description"],
        "country": country,
        "prominence_score": actor["prominence_score"],
        "source_url": actor["source_url"],
    }
    connection.execute(
        """
        INSERT INTO public_actors (
          source_id, actor_type, display_name, description, country, prominence_score,
          source_url, retrieved_at, first_seen_run_id, last_seen_run_id, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
          actor_type = excluded.actor_type,
          display_name = excluded.display_name,
          description = excluded.description,
          country = excluded.country,
          prominence_score = excluded.prominence_score,
          source_url = excluded.source_url,
          retrieved_at = excluded.retrieved_at,
          last_seen_run_id = excluded.last_seen_run_id,
          content_hash = excluded.content_hash
        """,
        (
            actor["source_id"], actor["actor_type"], actor["display_name"], actor["description"],
            country, actor["prominence_score"], actor["source_url"], retrieved_at,
            run_id, run_id, content_hash(canonical),
        ),
    )


def save(
    database: Path,
    run_id: str,
    retrieved_at: str,
    people: dict[str, dict[str, Any]],
    organizations: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    replace_existing: bool = False,
) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        if replace_existing:
            connection.executescript(
                """
                DROP TABLE IF EXISTS public_capability_tags;
                DROP TABLE IF EXISTS public_relationships;
                DROP TABLE IF EXISTS public_actors;
                DROP TABLE IF EXISTS crawl_runs;
                """
            )
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO crawl_runs (run_id, source_name, source_url, started_at, status) VALUES (?, 'Wikidata', ?, ?, 'running')",
            (run_id, ENDPOINT, retrieved_at),
        )
        for actor in [*people.values(), *organizations.values()]:
            upsert_actor(connection, actor, run_id, retrieved_at)
        for item in relationships:
            connection.execute(
                """
                INSERT INTO public_relationships (
                  relationship_id, from_source_id, to_source_id, relationship_type,
                  source_url, retrieved_at, first_seen_run_id, last_seen_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relationship_id) DO UPDATE SET
                  source_url = excluded.source_url,
                  retrieved_at = excluded.retrieved_at,
                  last_seen_run_id = excluded.last_seen_run_id
                """,
                (
                    item["relationship_id"], item["from_source_id"], item["to_source_id"],
                    item["relationship_type"], item["source_url"], retrieved_at, run_id, run_id,
                ),
            )
        for person in people.values():
            for tag in capability_tags(person):
                connection.execute(
                    """
                    INSERT INTO public_capability_tags (source_id, capability_tag, basis, confidence)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_id, capability_tag) DO UPDATE SET
                      basis = excluded.basis,
                      confidence = excluded.confidence
                    """,
                    (person["source_id"], tag["capability_tag"], tag["basis"], tag["confidence"]),
                )
        connection.execute(
            """
            UPDATE crawl_runs
            SET completed_at = ?, status = 'completed', actor_count = ?, relationship_count = ?
            WHERE run_id = ?
            """,
            (utc_now(), len(people) + len(organizations), len(relationships), run_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def export_browser_snapshot(database: Path, output: Path, retrieved_at: str) -> None:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        tags: dict[str, list[dict[str, Any]]] = {}
        for item in connection.execute(
            "SELECT * FROM public_capability_tags WHERE review_status != 'rejected' ORDER BY source_id, capability_tag"
        ):
            tags.setdefault(item["source_id"], []).append({
                "id": item["capability_tag"],
                "label": item["capability_tag"].replace("_", " ").title(),
                "basis": item["basis"],
                "confidence": item["confidence"],
                "reviewStatus": item["review_status"],
            })
        actors = [{
            "sourceId": item["source_id"],
            "actorType": item["actor_type"],
            "name": item["display_name"],
            "description": item["description"],
            "country": item["country"],
            "prominenceScore": item["prominence_score"],
            "sourceUrl": item["source_url"],
            "reviewStatus": item["review_status"],
            "capabilities": tags.get(item["source_id"], []),
        } for item in connection.execute(
            "SELECT * FROM public_actors WHERE review_status != 'rejected' ORDER BY actor_type, prominence_score DESC, display_name"
        )]
        relationships = [{
            "relationshipId": item["relationship_id"],
            "source": item["from_source_id"],
            "target": item["to_source_id"],
            "relationshipType": item["relationship_type"],
            "reviewStatus": item["review_status"],
            "sourceUrl": item["source_url"],
        } for item in connection.execute(
            "SELECT * FROM public_relationships WHERE review_status != 'rejected' ORDER BY relationship_type, relationship_id"
        )]
    finally:
        connection.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "asOf": retrieved_at,
        "status": "review_staging",
        "actors": actors,
        "relationships": relationships,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage prominent public figures and source-linked relationships from Wikidata.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum public figures to stage (default: 50, max: 200).")
    parser.add_argument("--min-sitelinks", type=int, default=40, help="Minimum Wikidata sitelinks used as a prominence threshold.")
    parser.add_argument("--profile", choices=sorted(PROFILES), help="Use a curated, need-specific public-network seed profile.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Separate staging SQLite database.")
    parser.add_argument("--browser-output", type=Path, default=DEFAULT_BROWSER_OUTPUT, help="Review-only JSON used by the local network map.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="Descriptive User-Agent; include a contact for regular use.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries for rate limits and temporary failures.")
    parser.add_argument("--delay-seconds", type=float, default=1.0, help="Delay between Wikidata requests.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and summarize without writing the staging database.")
    parser.add_argument("--replace", action="store_true", help="Replace existing review-staging records with this crawl.")
    parser.add_argument("--print-queries", action="store_true", help="Print SPARQL and exit without making a request.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.limit <= 200:
        raise SystemExit("--limit must be between 1 and 200")
    if args.min_sitelinks < 1:
        raise SystemExit("--min-sitelinks must be positive")

    profile = PROFILES.get(args.profile) if args.profile else None
    identity_query = seeded_people_query(profile["person_ids"]) if profile else people_query(args.limit, args.min_sitelinks)
    if args.print_queries:
        print(identity_query)
        print("\n# Relationship query is generated after public figure IDs are selected.")
        return

    person_bindings = fetch_bindings(identity_query, args.user_agent, args.timeout, args.retries)
    people = transform_people(person_bindings, len(profile["person_ids"]) if profile else args.limit)
    if not people:
        raise SystemExit("Wikidata returned no figures for the configured threshold.")
    time.sleep(max(0, args.delay_seconds))
    relation_bindings = fetch_bindings(relationships_query(list(people)), args.user_agent, args.timeout, args.retries)
    organizations, relationships = transform_relationships(
        relation_bindings,
        people,
        profile["organization_keywords"] if profile else (),
    )

    tagged = sum(bool(capability_tags(person)) for person in people.values())
    print(f"Selected {len(people)} public figures, {len(organizations)} organizations and {len(relationships)} relationships.")
    if profile:
        print(f"Profile: {args.profile} — {profile['description']}")
    print(f"Generated review-only capability candidates for {tagged} figures.")
    if args.dry_run:
        print("Dry run complete; no database was written.")
        return

    retrieved_at = utc_now()
    run_id = f"WD-{retrieved_at.replace(':', '').replace('+00:00', 'Z').replace('-', '')}"
    save(
        args.database.resolve(),
        run_id,
        retrieved_at,
        people,
        organizations,
        relationships,
        replace_existing=args.replace,
    )
    export_browser_snapshot(args.database.resolve(), args.browser_output.resolve(), retrieved_at)
    print(f"Staged results in {args.database.resolve()}")
    print(f"Wrote review snapshot to {args.browser_output.resolve()}")
    print("All new records are pending review and are not part of the trusted client network.")


if __name__ == "__main__":
    main()
