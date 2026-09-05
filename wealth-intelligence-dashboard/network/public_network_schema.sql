PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS crawl_runs (
  run_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  actor_count INTEGER NOT NULL DEFAULT 0,
  relationship_count INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS public_actors (
  source_id TEXT PRIMARY KEY,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('individual', 'organization')),
  display_name TEXT NOT NULL,
  description TEXT,
  country TEXT,
  prominence_score INTEGER,
  source_url TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  first_seen_run_id TEXT NOT NULL REFERENCES crawl_runs(run_id),
  last_seen_run_id TEXT NOT NULL REFERENCES crawl_runs(run_id),
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
  content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public_relationships (
  relationship_id TEXT PRIMARY KEY,
  from_source_id TEXT NOT NULL REFERENCES public_actors(source_id),
  to_source_id TEXT NOT NULL REFERENCES public_actors(source_id),
  relationship_type TEXT NOT NULL CHECK (relationship_type IN ('employed_by', 'member_of', 'affiliated_with', 'founded', 'leads', 'chairs')),
  evidence_level TEXT NOT NULL DEFAULT 'public_assertion' CHECK (evidence_level = 'public_assertion'),
  source_url TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  first_seen_run_id TEXT NOT NULL REFERENCES crawl_runs(run_id),
  last_seen_run_id TEXT NOT NULL REFERENCES crawl_runs(run_id),
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
  UNIQUE (from_source_id, to_source_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS public_capability_tags (
  source_id TEXT NOT NULL REFERENCES public_actors(source_id),
  capability_tag TEXT NOT NULL,
  basis TEXT NOT NULL,
  confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
  PRIMARY KEY (source_id, capability_tag)
);

CREATE INDEX IF NOT EXISTS idx_public_actors_review_prominence
  ON public_actors(review_status, prominence_score DESC);
CREATE INDEX IF NOT EXISTS idx_public_relationships_from_review
  ON public_relationships(from_source_id, review_status);
CREATE INDEX IF NOT EXISTS idx_public_relationships_to_review
  ON public_relationships(to_source_id, review_status);
CREATE INDEX IF NOT EXISTS idx_public_capability_tags_tag_review
  ON public_capability_tags(capability_tag, review_status);

PRAGMA optimize;
