# Network opportunity model

This model converts client needs into governed introduction routes. It always orders candidates by network tier before score:

1. RM-connected clients
2. Julius Baer teams and institutional network
3. External organizations

The engine only moves to the next tier when the current tier has fewer than the configured number of qualified options. A match is an internal hypothesis, not permission to disclose a client's identity or make contact.

## Core records

- `actors`: clients, RMs, bank teams and external organizations.
- `relationships`: directional, source-backed connections.
- `connection_paths` and `connection_path_hops`: cached routes from an RM to a possible provider.
- `needs`: normalized client needs, amounts, dates and confidentiality.
- `capabilities`: expertise, capital, access or services an actor may provide.
- `compatibility_rules`: explicit mappings from needs to capabilities.
- `permissions`: purpose-specific consent for identity disclosure and contact.
- `constraints_registry`: capacity, conflict, jurisdiction, liquidity, MNPI, privacy, suitability and timing checks.
- `opportunities`: scored candidate routes awaiting RM review.
- `introductions`: dual-consent workflow and outcome tracking.
- `evidence`: provenance for every material assertion.

## Build and inspect

From the dashboard directory:

```bash
python3 scripts/build_network.py
python3 scripts/find_collaborations.py --client CL-0014
```

The build creates `network/network.db` and the browser-ready `public/data/network-matches.json`. Both are derived artifacts; edit the schema or seed definitions rather than editing generated output manually.

## Ranking behavior

The score combines compatibility, relationship strength, evidence quality, known availability and constraints. Route tier is sorted before score, so a higher-scoring external provider never silently outranks a credible first-degree route.

Client capabilities seeded from the hackathon data use `inferred` evidence and `unknown` availability. The first recommended action for those rows is therefore to request permission and confirm interest. Bank-team capabilities are modeled as declared services. External organizations are illustrative synthetic entries.

## Public enrichment crawler

`scripts/crawl_public_network.py` is a separate, opt-in enrichment task backed by Wikidata. It can select general public figures using a configurable sitelink threshold or use an explicit, reviewable seed profile. It then collects public employment, affiliation, membership, founder and leadership relationships in a second request.

It intentionally writes to `network/public_network_staging.db`, not `network/network.db`. It also exports a review-only browser snapshot to `public/data/public-network-staging.json` so pending records can appear in the amber Public Data lane on the network map. Every actor, relationship, and inferred capability tag starts with `review_status = 'pending'`; no record becomes a trusted route or implies contact permission.

Preview the query without network access:

```bash
python3 scripts/crawl_public_network.py --print-queries
```

Run a small review crawl:

```bash
python3 scripts/crawl_public_network.py \
  --limit 25 \
  --min-sitelinks 50 \
  --user-agent "AccessAlphaPublicNetworkCrawler/0.1 (contact: your-email@example.com)"
```

Replace the staging lane with the curated network for Elena Marchetti-Wong's Greater China luxury-distribution need:

```bash
python3 scripts/crawl_public_network.py \
  --profile elena-luxury-distribution \
  --replace \
  --user-agent "AccessAlphaPublicNetworkCrawler/0.1 (contact: your-email@example.com)"
```

The profile includes commerce-platform, Hong Kong retail and supply-chain, and global luxury-group leaders. Its organization keyword filter excludes unrelated historical employers before records reach staging. `--replace` clears only `network/public_network_staging.db`; it never touches the trusted `network/network.db`.

Or use the package task and pass the same options after `--`:

```bash
pnpm crawl:public-network -- --limit 25 --min-sitelinks 50
```

The prominence score is only the number of Wikidata sitelinks, not a judgement of influence, trust, wealth, or suitability. The crawler excludes contact details, social handles, home addresses, and client information. For production, add compliance review, sanctions/adverse-media screening, data-retention rules, and an explicit approval step that maps reviewed staging records into the governed network schema.
