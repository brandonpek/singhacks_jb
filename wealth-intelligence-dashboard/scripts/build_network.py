"""Create the synthetic relationship graph and precompute governed opportunity routes."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
SOURCE = ROOT / "singhacks-jb-wealth-intelligence" / "data"
SCHEMA = APP / "network" / "schema.sql"
DATABASE = APP / "network" / "network.db"
OUTPUT = APP / "public" / "data" / "network-matches.json"
GRAPH_OUTPUT = APP / "public" / "data" / "network-graph.json"
AS_OF = "2026-08-26"
RM_ID = "RM-SG-014"


def rows(name: str) -> list[dict[str, str]]:
    with (SOURCE / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def amount(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def urgency(due_from: str | None, certainty: str | None) -> str:
    if due_from and due_from <= "2026-12-31":
        return "critical" if certainty == "Confirmed" else "high"
    if due_from and due_from <= "2027-06-30":
        return "high"
    return "medium"


def classify_need(description: str) -> str:
    text = description.lower()
    if "redevelopment" in text or "property purchase" in text:
        return "property_financing"
    if "healthcare foundation" in text:
        return "healthcare_foundation"
    if "foundation" in text or "endowment" in text:
        return "philanthropy_setup"
    if "family office" in text:
        return "family_office_setup"
    if "tax" in text:
        return "tax_planning"
    if "trust" in text or "estate" in text or "succession" in text:
        return "succession_planning"
    if "capital call" in text or "private markets" in text:
        return "private_market_liquidity"
    if "university" in text or "education" in text:
        return "education_funding"
    if "retirement" in text or "living expenses" in text or "medical" in text or "elderly parents" in text:
        return "wealth_planning"
    return "liquidity_planning"


DATABASE.parent.mkdir(parents=True, exist_ok=True)
temporary = DATABASE.with_suffix(".tmp.db")
if temporary.exists():
    temporary.unlink()

connection = sqlite3.connect(temporary)
connection.row_factory = sqlite3.Row
connection.executescript(SCHEMA.read_text(encoding="utf-8"))


def evidence(evidence_id: str, system: str, record: str, field: str, level: str = "declared") -> str:
    connection.execute(
        "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
        (evidence_id, system, record, field, AS_OF, level, "confidential"),
    )
    return evidence_id


def actor(actor_id: str, actor_type: str, name: str, organization: str | None, jurisdiction: str, source: str, level: str = "declared") -> None:
    evidence_id = evidence(f"EV-A-{actor_id}", source, actor_id, "identity", level)
    connection.execute(
        "INSERT INTO actors VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
        (actor_id, actor_type, name, organization, jurisdiction, evidence_id, AS_OF),
    )


client_rows = rows("clients.csv")
actor(RM_ID, "rm", "Priscilla Ong", "Julius Baer", "Singapore / Hong Kong", "clients.csv")
for client in client_rows:
    actor(client["client_id"], "client", client["client_name"], None, client["country_of_residence"], "clients.csv")

bank_teams = [
    ("BANK-LENDING", "JB Lending Solutions", "Singapore / Hong Kong"),
    ("BANK-FAMILY-OFFICE", "JB Family Office Advisory", "Asia"),
    ("BANK-PHILANTHROPY", "JB Philanthropy Advisory", "Global"),
    ("BANK-SUSTAINABILITY", "JB Sustainable Investment Advisory", "Global"),
    ("BANK-WEALTH-PLANNING", "JB Wealth Planning", "Asia / Europe"),
    ("BANK-ALTERNATIVES", "JB Alternatives Advisory", "Global"),
    ("BANK-TAX", "JB Tax and Wealth Planning", "Asia / Europe"),
]
for actor_id, name, jurisdiction in bank_teams:
    actor(actor_id, "bank_team", name, "Julius Baer", jurisdiction, "synthetic-network-seed")

external_actors = [
    ("EXT-HK-PROPERTY-CREDIT", "HarbourBridge Property Credit", "Hong Kong SAR"),
    ("EXT-HEALTH-IMPACT", "Global Health Access Network", "Global"),
    ("EXT-LUXURY-COMMERCE", "Asia Luxury Commerce Council", "Asia"),
]
for actor_id, name, jurisdiction in external_actors:
    actor(actor_id, "external_organization", name, name, jurisdiction, "synthetic-network-seed")


def relationship(rel_id: str, source_id: str, target_id: str, rel_type: str, tier: int, strength: int, owner: str = RM_ID) -> None:
    evidence_id = evidence(f"EV-R-{rel_id}", "synthetic-network-seed", rel_id, "relationship", "observed")
    connection.execute(
        "INSERT INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
        (rel_id, source_id, target_id, rel_type, owner, tier, strength, evidence_id, AS_OF),
    )


for client in client_rows:
    relationship(f"REL-RM-{client['client_id']}", RM_ID, client["client_id"], "relationship_manager", 1, 82)
for team_id, _, _ in bank_teams:
    relationship(f"REL-RM-{team_id}", RM_ID, team_id, "internal_specialist", 2, 90)

external_routes = [
    ("BANK-LENDING", "EXT-HK-PROPERTY-CREDIT", "institutional_partner"),
    ("BANK-PHILANTHROPY", "EXT-HEALTH-IMPACT", "institutional_partner"),
    ("BANK-FAMILY-OFFICE", "EXT-LUXURY-COMMERCE", "industry_network"),
]
for source_id, target_id, rel_type in external_routes:
    relationship(f"REL-{source_id}-{target_id}", source_id, target_id, rel_type, 3, 72, source_id)


def path(path_id: str, target_id: str, tier: int, strength: int, relationship_ids: list[str]) -> None:
    connection.execute(
        "INSERT INTO connection_paths VALUES (?, ?, ?, ?, ?, ?, ?)",
        (path_id, RM_ID, target_id, tier, len(relationship_ids), strength, AS_OF),
    )
    for index, relationship_id in enumerate(relationship_ids, start=1):
        connection.execute("INSERT INTO connection_path_hops VALUES (?, ?, ?)", (path_id, index, relationship_id))


for client in client_rows:
    path(f"PATH-{client['client_id']}", client["client_id"], 1, 82, [f"REL-RM-{client['client_id']}"])
for team_id, _, _ in bank_teams:
    path(f"PATH-{team_id}", team_id, 2, 90, [f"REL-RM-{team_id}"])
for source_id, target_id, _ in external_routes:
    path(f"PATH-{target_id}", target_id, 3, 72, [f"REL-RM-{source_id}", f"REL-{source_id}-{target_id}"])

need_types = {
    "business_exit_transition": "Business-exit transition",
    "cross_border_distribution": "Cross-border distribution",
    "education_funding": "Education funding",
    "family_office_setup": "Family-office setup",
    "healthcare_foundation": "Healthcare foundation",
    "liquidity_planning": "Liquidity planning",
    "philanthropy_setup": "Philanthropy setup",
    "private_market_liquidity": "Private-market liquidity",
    "property_financing": "Property financing",
    "succession_planning": "Succession planning",
    "sustainability_policy": "Sustainability policy",
    "tax_planning": "Tax planning",
    "wealth_planning": "Wealth planning",
}
for need_id, label in need_types.items():
    connection.execute("INSERT INTO need_types VALUES (?, ?, ?)", (need_id, label, f"Support related to {label.lower()}."))

capability_types = {
    "business_exit_experience": "Business-exit experience",
    "cross_border_ecommerce": "Cross-border e-commerce",
    "family_office_governance": "Family-office governance",
    "foundation_experience": "Foundation experience",
    "healthcare_operations": "Healthcare operations",
    "healthcare_sector_expertise": "Healthcare-sector expertise",
    "impact_policy_experience": "Impact-policy experience",
    "liquidity_advisory": "Liquidity advisory",
    "luxury_distribution": "Luxury distribution",
    "philanthropy_advisory": "Philanthropy advisory",
    "private_markets_advisory": "Private-markets advisory",
    "property_development_expertise": "Property-development expertise",
    "property_financing": "Property financing",
    "succession_advisory": "Succession advisory",
    "sustainability_advisory": "Sustainability advisory",
    "tax_advisory": "Tax advisory",
    "wealth_planning": "Wealth planning",
}
for capability_id, label in capability_types.items():
    connection.execute("INSERT INTO capability_types VALUES (?, ?, ?)", (capability_id, label, f"Can contribute {label.lower()}."))

rules = [
    ("business_exit_transition", "business_exit_experience", 1.0, "Has relevant experience moving from an operating business into a post-sale wealth structure."),
    ("business_exit_transition", "family_office_governance", 0.65, "Can share governance considerations that become relevant after a liquidity event."),
    ("cross_border_distribution", "cross_border_ecommerce", 0.90, "Brings a complementary cross-border commerce platform perspective."),
    ("cross_border_distribution", "luxury_distribution", 0.90, "Brings relevant luxury distribution experience in Greater China."),
    ("family_office_setup", "family_office_governance", 1.0, "Has relevant family-office operating or advisory experience."),
    ("healthcare_foundation", "healthcare_operations", 0.90, "Brings direct healthcare operating experience relevant to the proposed foundation."),
    ("healthcare_foundation", "healthcare_sector_expertise", 0.78, "Brings healthcare-sector knowledge that may strengthen planning and partnerships."),
    ("healthcare_foundation", "philanthropy_advisory", 1.0, "Can structure the foundation and its impact model."),
    ("healthcare_foundation", "foundation_experience", 0.65, "May provide peer perspective on creating a foundation."),
    ("philanthropy_setup", "philanthropy_advisory", 1.0, "Can structure the foundation, governance and grant-making approach."),
    ("philanthropy_setup", "foundation_experience", 0.70, "May provide relevant peer experience with foundation planning."),
    ("property_financing", "property_development_expertise", 0.58, "May provide market context or a warm route to relevant property-finance contacts; lending capacity is not established."),
    ("property_financing", "property_financing", 1.0, "Provides a direct route to assess property-financing options."),
    ("succession_planning", "family_office_governance", 0.78, "Can share multi-generational governance experience."),
    ("succession_planning", "succession_advisory", 1.0, "Can structure succession, trust and governance options."),
    ("sustainability_policy", "impact_policy_experience", 0.82, "May share practical experience reviewing sustainability screens and policy alignment."),
    ("sustainability_policy", "sustainability_advisory", 1.0, "Can review exclusions, mandate alignment and implementation choices."),
    ("tax_planning", "tax_advisory", 1.0, "Can coordinate tax-aware planning with qualified external counsel where required."),
    ("private_market_liquidity", "private_markets_advisory", 1.0, "Can map commitments, call schedules and secondary-market options."),
    ("private_market_liquidity", "liquidity_advisory", 0.90, "Can develop a liquidity plan around expected capital calls."),
    ("education_funding", "liquidity_advisory", 0.72, "Can ring-fence liquid assets against scheduled education payments."),
    ("wealth_planning", "wealth_planning", 1.0, "Can translate recurring obligations into a sustainable funding plan."),
    ("liquidity_planning", "liquidity_advisory", 1.0, "Can structure a funding plan around the stated obligation."),
]
connection.executemany("INSERT INTO compatibility_rules VALUES (?, ?, ?, ?)", rules)

for source_need in rows("planned_cash_needs.csv"):
    need_id = source_need["need_id"]
    evidence_id = evidence(f"EV-N-{need_id}", "planned_cash_needs.csv", need_id, "description", "declared")
    need_type = classify_need(source_need["description"])
    connection.execute(
        "INSERT INTO needs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'restricted', 'open', ?, ?)",
        (
            need_id,
            source_need["client_id"],
            need_type,
            source_need["description"],
            source_need["description"],
            amount(source_need["amount"]),
            source_need["currency"],
            source_need["due_from"],
            source_need["due_to"],
            urgency(source_need["due_from"], source_need["certainty"]),
            source_need["certainty"],
            evidence_id,
            AS_OF,
        ),
    )

strategic_needs = [
    ("SN-001", "CL-0002", "business_exit_transition", "Prepare for founder liquidity event", "Secondary share sale expected in Q4 2026; client wants a diversified post-event structure.", "high", "clients.csv:CL-0002"),
    ("SN-002", "CL-0008", "business_exit_transition", "Prepare for partial business sale", "Client is considering a minority sale of the franchise business in 2028.", "medium", "rm_notes.json:N-012"),
    ("SN-003", "CL-0013", "family_office_setup", "Plan an eventual family office", "Client objective includes an eventual family-office structure.", "medium", "clients.csv:CL-0013"),
    ("SN-004", "CL-0018", "cross_border_distribution", "Respond to pressure in Greater China luxury distribution", "The operating business is under pressure from weaker luxury demand.", "medium", "rm_notes.json:N-024"),
    ("SN-005", "CL-0005", "sustainability_policy", "Align holdings with sustainability policy", "Client believes the mandate is aligned, while current holdings include binding exclusions.", "high", "rm_notes.json:N-008"),
]
for need_id, client_id, need_type, title, description, need_urgency, source_ref in strategic_needs:
    evidence_id = evidence(f"EV-N-{need_id}", source_ref.split(":")[0], source_ref, "need", "observed")
    connection.execute(
        "INSERT INTO needs VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, 'Observed', 'restricted', 'open', ?, ?)",
        (need_id, client_id, need_type, title, description, need_urgency, evidence_id, AS_OF),
    )


def capability(cap_id: str, provider: str, cap_type: str, offering: str, description: str, level: str, availability: str, source: str) -> None:
    evidence_id = evidence(f"EV-C-{cap_id}", source.split(":")[0], source, "capability", level)
    connection.execute(
        "INSERT INTO capabilities VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)",
        (cap_id, provider, cap_type, offering, description, level, availability, evidence_id, AS_OF),
    )


client_capabilities = [
    ("CAP-ANDREAS-EXIT", "CL-0009", "business_exit_experience", "expertise", "Completed a majority business sale in 2024 and is navigating post-sale deployment.", "inferred", "unknown", "clients.csv:CL-0009"),
    ("CAP-FONG-GOV", "CL-0017", "family_office_governance", "expertise", "Multi-generational family office operating since the family business sale in 2009.", "inferred", "unknown", "clients.csv:CL-0017"),
    ("CAP-GRACE-HEALTH", "CL-0020", "healthcare_operations", "expertise", "Founder of a private healthcare clinics group with expansion experience.", "inferred", "unknown", "clients.csv:CL-0020"),
    ("CAP-YAMAMOTO-HEALTH", "CL-0016", "healthcare_sector_expertise", "expertise", "Pharmaceutical group board member with sector experience.", "inferred", "unknown", "clients.csv:CL-0016"),
    ("CAP-PRIYA-IMPACT", "CL-0010", "impact_policy_experience", "expertise", "Actively reviews sustainability screening and maintains a personal impact policy.", "observed", "unknown", "rm_notes.json:N-014"),
    ("CAP-TAN-PROPERTY", "CL-0011", "property_development_expertise", "access", "Built wealth through property development; may have relevant market knowledge or contacts.", "inferred", "unknown", "clients.csv:CL-0011"),
    ("CAP-ZHANG-ECOM", "CL-0013", "cross_border_ecommerce", "expertise", "Founder of a cross-border e-commerce platform.", "inferred", "unknown", "clients.csv:CL-0013"),
    ("CAP-ELENA-LUXURY", "CL-0018", "luxury_distribution", "expertise", "Runs luxury-goods distribution across Greater China.", "inferred", "unknown", "clients.csv:CL-0018"),
    ("CAP-ALISTAIR-FOUNDATION", "CL-0007", "foundation_experience", "expertise", "Actively planning a charitable foundation and endowment for 2027.", "observed", "unknown", "rm_notes.json:N-011"),
]
for item in client_capabilities:
    capability(*item)

bank_capabilities = [
    ("CAP-BANK-LENDING", "BANK-LENDING", "property_financing", "service", "Structures portfolio and property-backed financing solutions.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-FO", "BANK-FAMILY-OFFICE", "family_office_governance", "service", "Advises on family-office design, governance and operating models.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-PHIL", "BANK-PHILANTHROPY", "philanthropy_advisory", "service", "Supports foundation strategy, governance and impact frameworks.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-SUST", "BANK-SUSTAINABILITY", "sustainability_advisory", "service", "Reviews sustainability policies, exclusions and mandate alignment.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-WP", "BANK-WEALTH-PLANNING", "wealth_planning", "service", "Builds long-term funding and income plans around client obligations.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-WP-LIQ", "BANK-WEALTH-PLANNING", "liquidity_advisory", "service", "Creates liquidity plans for scheduled and contingent needs.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-ALTS", "BANK-ALTERNATIVES", "private_markets_advisory", "service", "Maps commitments, capital calls and liquidity options for private assets.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-TAX", "BANK-TAX", "tax_advisory", "service", "Coordinates tax and wealth-planning questions with qualified counsel.", "declared", "available", "synthetic-network-seed"),
    ("CAP-BANK-SUCCESSION", "BANK-FAMILY-OFFICE", "succession_advisory", "service", "Supports trust, succession and next-generation governance planning.", "declared", "available", "synthetic-network-seed"),
]
for item in bank_capabilities:
    capability(*item)

external_capabilities = [
    ("CAP-EXT-PROP", "EXT-HK-PROPERTY-CREDIT", "property_financing", "capital", "Illustrative specialist lender for Hong Kong property projects.", "declared", "unknown", "synthetic-network-seed"),
    ("CAP-EXT-HEALTH", "EXT-HEALTH-IMPACT", "philanthropy_advisory", "access", "Illustrative network of healthcare-access funders and operators.", "declared", "unknown", "synthetic-network-seed"),
    ("CAP-EXT-LUXURY", "EXT-LUXURY-COMMERCE", "cross_border_ecommerce", "access", "Illustrative industry network connecting luxury distributors and commerce platforms.", "declared", "unknown", "synthetic-network-seed"),
]
for item in external_capabilities:
    capability(*item)

for provider_id, actor_type in connection.execute("SELECT actor_id, actor_type FROM actors WHERE actor_type IN ('client', 'bank_team', 'external_organization')"):
    is_bank = actor_type == "bank_team"
    permission_id = f"PERM-{provider_id}"
    evidence_id = evidence(f"EV-P-{provider_id}", "synthetic-network-seed", permission_id, "permission", "inferred")
    connection.execute(
        "INSERT INTO permissions VALUES (?, ?, NULL, 'collaboration_intro', ?, ?, ?, ?, ?, NULL)",
        (permission_id, provider_id, "granted" if is_bank else "unknown", 1 if is_bank else 0, 1 if is_bank else 0, evidence_id, AS_OF if is_bank else None),
    )

# Known data argues against presenting Fong Family Office as a source of liquidity.
constraint_evidence = evidence("EV-X-FONG-LIQ", "rm_notes.json", "N-022", "note", "observed")
connection.execute(
    "INSERT INTO constraints_registry VALUES ('CON-FONG-LIQ', 'CL-0017', NULL, 'liquidity', 'review', ?, 12, ?, NULL)",
    ("Large commitments and a gated private-credit holding make available liquidity uncertain.", constraint_evidence),
)


opportunity_rows = connection.execute(
    """
    SELECT
      n.need_id,
      n.client_actor_id,
      n.need_type_id,
      c.capability_id,
      c.provider_actor_id,
      c.capability_type_id,
      c.offering_type,
      c.description AS capability_description,
      c.evidence_level,
      c.availability_status,
      a.display_name AS provider_name,
      a.actor_type,
      p.path_id,
      p.route_tier,
      p.path_strength,
      cr.relevance_weight,
      cr.rationale,
      COALESCE(pm.permission_status, 'unknown') AS permission_status,
      COALESCE(SUM(CASE WHEN x.effect = 'block' THEN 100 ELSE x.penalty_points END), 0) AS penalty
    FROM needs n
    JOIN compatibility_rules cr ON cr.need_type_id = n.need_type_id
    JOIN capabilities c ON c.capability_type_id = cr.capability_type_id
    JOIN actors a ON a.actor_id = c.provider_actor_id AND a.status = 'active'
    JOIN connection_paths p ON p.rm_actor_id = ? AND p.target_actor_id = c.provider_actor_id
    LEFT JOIN permissions pm ON pm.subject_actor_id = c.provider_actor_id AND pm.purpose_code = 'collaboration_intro'
    LEFT JOIN constraints_registry x ON x.actor_id = c.provider_actor_id
    WHERE n.status IN ('open', 'exploring')
      AND c.availability_status != 'unavailable'
      AND c.provider_actor_id != n.client_actor_id
    GROUP BY n.need_id, c.capability_id, p.path_id
    """,
    (RM_ID,),
).fetchall()


def score(row: sqlite3.Row) -> float:
    tier_points = {1: 30, 2: 20, 3: 10}[row["route_tier"]]
    evidence_points = {"declared": 10, "observed": 7, "inferred": 3}[row["evidence_level"]]
    permission_penalty = 0 if row["permission_status"] == "granted" else 8
    availability_penalty = 0 if row["availability_status"] == "available" else 5
    raw = tier_points + 40 * row["relevance_weight"] + 0.15 * row["path_strength"] + evidence_points
    return round(max(0, min(100, raw - permission_penalty - availability_penalty - row["penalty"])), 1)


for row in opportunity_rows:
    match_score = score(row)
    opportunity_id = f"OPP-{row['need_id']}-{row['capability_id']}"
    connection.execute(
        "INSERT INTO opportunities VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'suggested', ?, NULL, NULL)",
        (opportunity_id, row["need_id"], row["provider_actor_id"], row["path_id"], row["capability_id"], match_score, row["route_tier"], row["rationale"], AS_OF),
    )


def path_names(path_id: str) -> list[str]:
    result = [connection.execute("SELECT display_name FROM actors WHERE actor_id = ?", (RM_ID,)).fetchone()[0]]
    for hop in connection.execute(
        """
        SELECT a.display_name
        FROM connection_path_hops h
        JOIN relationships r ON r.relationship_id = h.relationship_id
        JOIN actors a ON a.actor_id = r.to_actor_id
        WHERE h.path_id = ?
        ORDER BY h.hop_order
        """,
        (path_id,),
    ):
        result.append(hop[0])
    return result


client_names = {row["client_id"]: row["client_name"] for row in client_rows}
output_needs = []
for need in connection.execute("SELECT * FROM needs WHERE status IN ('open', 'exploring') ORDER BY CASE urgency WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END, due_from"):
    candidates = []
    seen_providers: set[str] = set()
    for candidate in connection.execute(
        """
        SELECT o.*, a.display_name AS provider_name, a.actor_type,
               c.capability_type_id, c.offering_type, c.description AS capability_description,
               c.evidence_level, c.availability_status,
               COALESCE(pm.permission_status, 'unknown') AS permission_status
        FROM opportunities o
        JOIN actors a ON a.actor_id = o.provider_actor_id
        JOIN capabilities c ON c.capability_id = o.capability_id
        LEFT JOIN permissions pm ON pm.subject_actor_id = o.provider_actor_id AND pm.purpose_code = 'collaboration_intro'
        WHERE o.need_id = ?
        ORDER BY o.route_tier, o.match_score DESC
        """,
        (need["need_id"],),
    ):
        if candidate["provider_actor_id"] in seen_providers:
            continue
        seen_providers.add(candidate["provider_actor_id"])
        candidates.append({
            "opportunityId": candidate["opportunity_id"],
            "providerId": candidate["provider_actor_id"],
            "providerName": candidate["provider_name"],
            "providerType": candidate["actor_type"],
            "routeTier": candidate["route_tier"],
            "routeLabel": {1: "RM connection", 2: "Bank network", 3: "External route"}[candidate["route_tier"]],
            "score": candidate["match_score"],
            "capability": capability_types[candidate["capability_type_id"]],
            "offeringType": candidate["offering_type"],
            "rationale": candidate["rationale"],
            "capabilityDescription": candidate["capability_description"],
            "evidenceLevel": candidate["evidence_level"],
            "availability": candidate["availability_status"],
            "permission": candidate["permission_status"],
            "path": path_names(candidate["path_id"]),
            "nextAction": "Request permission and confirm interest" if candidate["actor_type"] == "client" else "Ask the team to assess the need" if candidate["actor_type"] == "bank_team" else "Confirm suitability before external outreach",
        })

    qualified = [candidate for candidate in candidates if candidate["score"] >= 50]
    recommended: list[str] = []
    used_tiers: list[int] = []
    for tier in (1, 2, 3):
        tier_candidates = [candidate for candidate in qualified if candidate["routeTier"] == tier]
        if not tier_candidates:
            continue
        used_tiers.append(tier)
        recommended.extend(candidate["opportunityId"] for candidate in tier_candidates[:3])
        if len(recommended) >= 2:
            break
    for candidate in candidates:
        candidate["recommended"] = candidate["opportunityId"] in recommended

    output_needs.append({
        "needId": need["need_id"],
        "clientId": need["client_actor_id"],
        "clientName": client_names[need["client_actor_id"]],
        "needType": need_types[need["need_type_id"]],
        "title": need["title"],
        "description": need["description"],
        "amount": need["amount"],
        "currency": need["currency"],
        "dueFrom": need["due_from"],
        "urgency": need["urgency"],
        "certainty": need["certainty"],
        "usedTiers": used_tiers,
        "candidates": candidates,
    })

capabilities_by_actor: dict[str, list[dict[str, str]]] = defaultdict(list)
for item in connection.execute(
    """
    SELECT c.provider_actor_id, c.capability_type_id, ct.display_name,
           c.offering_type, c.evidence_level, c.availability_status
    FROM capabilities c
    JOIN capability_types ct ON ct.capability_type_id = c.capability_type_id
    ORDER BY c.provider_actor_id, ct.display_name
    """
):
    capabilities_by_actor[item["provider_actor_id"]].append({
        "id": item["capability_type_id"],
        "label": item["display_name"],
        "offeringType": item["offering_type"],
        "evidenceLevel": item["evidence_level"],
        "availability": item["availability_status"],
    })

needs_by_actor: dict[str, list[dict[str, object]]] = defaultdict(list)
for item in output_needs:
    needs_by_actor[item["clientId"]].append({
        "needId": item["needId"],
        "title": item["title"],
        "needType": item["needType"],
        "urgency": item["urgency"],
        "candidateCount": len(item["candidates"]),
    })

graph_nodes = []
for item in connection.execute(
    """
    SELECT a.*, COALESCE(p.route_tier, 0) AS network_tier
    FROM actors a
    LEFT JOIN connection_paths p ON p.target_actor_id = a.actor_id AND p.rm_actor_id = ?
    WHERE a.status = 'active'
    ORDER BY a.actor_type, a.display_name
    """,
    (RM_ID,),
):
    graph_nodes.append({
        "actorId": item["actor_id"],
        "actorType": item["actor_type"],
        "name": item["display_name"],
        "organization": item["organization_name"],
        "jurisdiction": item["jurisdiction"],
        "networkTier": item["network_tier"],
        "capabilities": capabilities_by_actor[item["actor_id"]],
        "needs": needs_by_actor[item["actor_id"]],
    })

graph_edges = [{
    "relationshipId": item["relationship_id"],
    "source": item["from_actor_id"],
    "target": item["to_actor_id"],
    "relationshipType": item["relationship_type"],
    "networkTier": item["network_tier"],
    "strength": item["strength_score"],
} for item in connection.execute(
    "SELECT * FROM relationships WHERE relationship_status = 'active' ORDER BY network_tier, relationship_id"
)]

graph_opportunities = [{
    "needId": need["needId"],
    "clientId": need["clientId"],
    "providerId": candidate["providerId"],
    "providerName": candidate["providerName"],
    "routeTier": candidate["routeTier"],
    "score": candidate["score"],
    "recommended": candidate["recommended"],
} for need in output_needs for candidate in need["candidates"]]

connection.commit()
connection.execute("PRAGMA optimize")
connection.close()
temporary.replace(DATABASE)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps({"asOf": AS_OF, "minimumQualifiedOptions": 2, "needs": output_needs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
GRAPH_OUTPUT.write_text(json.dumps({
    "asOf": AS_OF,
    "rmActorId": RM_ID,
    "nodes": graph_nodes,
    "edges": graph_edges,
    "opportunities": graph_opportunities,
}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"Built {DATABASE.name}: {len(output_needs)} needs, {len(opportunity_rows)} candidate routes")
print(f"Wrote {OUTPUT}")
print(f"Wrote {GRAPH_OUTPUT}")
