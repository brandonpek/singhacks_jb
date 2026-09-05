import sqlite3
import tempfile
import unittest
import json
from pathlib import Path

from scripts.crawl_public_network import (
    capability_tags,
    export_browser_snapshot,
    save,
    seeded_people_query,
    transform_people,
    transform_relationships,
)


def literal(value: str) -> dict[str, str]:
    return {"type": "literal", "value": value}


def entity(entity_id: str) -> dict[str, str]:
    return {"type": "uri", "value": f"http://www.wikidata.org/entity/{entity_id}"}


class PublicNetworkCrawlerTest(unittest.TestCase):
    def test_transforms_deduplicates_and_stages_pending_records(self) -> None:
        people = transform_people([
            {
                "person": entity("Q100"),
                "personLabel": literal("Example Founder"),
                "description": literal("Example public figure"),
                "sitelinks": literal("120"),
                "countryLabel": literal("Singapore"),
                "occupationLabel": literal("entrepreneur"),
            },
            {
                "person": entity("Q100"),
                "personLabel": literal("Example Founder"),
                "sitelinks": literal("120"),
                "occupationLabel": literal("philanthropist"),
            },
        ], limit=10)
        organizations, relationships = transform_relationships([
            {
                "person": entity("Q100"),
                "related": entity("Q200"),
                "relatedLabel": literal("Example Foundation"),
                "relationshipType": literal("founded"),
            },
            {
                "person": entity("Q100"),
                "related": entity("Q200"),
                "relatedLabel": literal("Example Foundation"),
                "relationshipType": literal("founded"),
            },
        ], people)

        self.assertEqual(list(people), ["Q100"])
        self.assertEqual(len(relationships), 1)
        self.assertEqual(
            {item["capability_tag"] for item in capability_tags(people["Q100"])},
            {"operating_business_experience", "philanthropy_experience"},
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "public-network.db"
            save(database, "TEST-RUN", "2026-09-04T00:00:00+00:00", people, organizations, relationships)
            browser_output = Path(directory) / "public-network.json"
            export_browser_snapshot(database, browser_output, "2026-09-04T00:00:00+00:00")
            connection = sqlite3.connect(database)
            try:
                actor_count = connection.execute("SELECT COUNT(*) FROM public_actors").fetchone()[0]
                relationship_count = connection.execute("SELECT COUNT(*) FROM public_relationships").fetchone()[0]
                statuses = connection.execute("SELECT DISTINCT review_status FROM public_actors").fetchall()
            finally:
                connection.close()
            snapshot = json.loads(browser_output.read_text(encoding="utf-8"))

        self.assertEqual(actor_count, 2)
        self.assertEqual(relationship_count, 1)
        self.assertEqual(statuses, [("pending",)])
        self.assertEqual(len(snapshot["actors"]), 2)
        self.assertEqual(snapshot["status"], "review_staging")

    def test_profile_query_uses_only_explicit_seed_ids(self) -> None:
        query = seeded_people_query(("Q100", "Q200"))

        self.assertIn("VALUES ?person { wd:Q100 wd:Q200 }", query)
        self.assertNotIn("LIMIT", query)

    def test_profile_filters_unrelated_organizations(self) -> None:
        people = transform_people([{
            "person": entity("Q100"),
            "personLabel": literal("Example Executive"),
            "sitelinks": literal("12"),
            "occupationLabel": literal("businessperson"),
        }], limit=1)
        organizations, relationships = transform_relationships([
            {
                "person": entity("Q100"),
                "related": entity("Q200"),
                "relatedLabel": literal("Alibaba Group"),
                "relationshipType": literal("employed_by"),
            },
            {
                "person": entity("Q100"),
                "related": entity("Q300"),
                "relatedLabel": literal("Unrelated Former Employer"),
                "relationshipType": literal("employed_by"),
            },
        ], people, ("alibaba",))

        self.assertEqual(list(organizations), ["Q200"])
        self.assertEqual(len(relationships), 1)

    def test_replace_removes_previous_staging_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "public-network.db"
            first_people = transform_people([{
                "person": entity("Q100"),
                "personLabel": literal("Old Figure"),
                "sitelinks": literal("100"),
                "occupationLabel": literal("businessperson"),
            }], limit=1)
            replacement_people = transform_people([{
                "person": entity("Q101"),
                "personLabel": literal("Relevant Figure"),
                "sitelinks": literal("50"),
                "occupationLabel": literal("entrepreneur"),
            }], limit=1)
            save(database, "RUN-1", "2026-09-04T00:00:00+00:00", first_people, {}, [])
            save(database, "RUN-2", "2026-09-05T00:00:00+00:00", replacement_people, {}, [], replace_existing=True)
            connection = sqlite3.connect(database)
            try:
                names = connection.execute("SELECT display_name FROM public_actors").fetchall()
                runs = connection.execute("SELECT run_id FROM crawl_runs").fetchall()
            finally:
                connection.close()

        self.assertEqual(names, [("Relevant Figure",)])
        self.assertEqual(runs, [("RUN-2",)])


if __name__ == "__main__":
    unittest.main()
