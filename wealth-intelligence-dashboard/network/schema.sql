PRAGMA foreign_keys = ON;

CREATE TABLE evidence (
  evidence_id TEXT PRIMARY KEY,
  source_system TEXT NOT NULL,
  source_record_id TEXT,
  source_field TEXT,
  observed_at TEXT,
  evidence_level TEXT NOT NULL CHECK (evidence_level IN ('declared', 'observed', 'inferred')),
  sensitivity TEXT NOT NULL DEFAULT 'confidential' CHECK (sensitivity IN ('internal', 'confidential', 'restricted'))
);

CREATE TABLE actors (
  actor_id TEXT PRIMARY KEY,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('rm', 'client', 'bank_team', 'external_organization', 'individual')),
  display_name TEXT NOT NULL,
  organization_name TEXT,
  jurisdiction TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'unverified')),
  evidence_id TEXT REFERENCES evidence(evidence_id),
  last_verified_at TEXT
);

CREATE TABLE relationships (
  relationship_id TEXT PRIMARY KEY,
  from_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  to_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  relationship_type TEXT NOT NULL,
  owner_actor_id TEXT REFERENCES actors(actor_id),
  network_tier INTEGER NOT NULL CHECK (network_tier BETWEEN 1 AND 3),
  strength_score INTEGER NOT NULL DEFAULT 50 CHECK (strength_score BETWEEN 0 AND 100),
  relationship_status TEXT NOT NULL DEFAULT 'active' CHECK (relationship_status IN ('active', 'dormant', 'unverified', 'blocked')),
  evidence_id TEXT REFERENCES evidence(evidence_id),
  last_verified_at TEXT,
  UNIQUE (from_actor_id, to_actor_id, relationship_type)
);

CREATE TABLE connection_paths (
  path_id TEXT PRIMARY KEY,
  rm_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  target_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  route_tier INTEGER NOT NULL CHECK (route_tier BETWEEN 1 AND 3),
  hop_count INTEGER NOT NULL CHECK (hop_count >= 1),
  path_strength INTEGER NOT NULL CHECK (path_strength BETWEEN 0 AND 100),
  computed_at TEXT NOT NULL,
  UNIQUE (rm_actor_id, target_actor_id)
);

CREATE TABLE connection_path_hops (
  path_id TEXT NOT NULL REFERENCES connection_paths(path_id) ON DELETE CASCADE,
  hop_order INTEGER NOT NULL CHECK (hop_order >= 1),
  relationship_id TEXT NOT NULL REFERENCES relationships(relationship_id),
  PRIMARY KEY (path_id, hop_order)
);

CREATE TABLE need_types (
  need_type_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE needs (
  need_id TEXT PRIMARY KEY,
  client_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  need_type_id TEXT NOT NULL REFERENCES need_types(need_type_id),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  amount REAL,
  currency TEXT,
  due_from TEXT,
  due_to TEXT,
  urgency TEXT NOT NULL DEFAULT 'medium' CHECK (urgency IN ('low', 'medium', 'high', 'critical')),
  certainty TEXT,
  confidentiality TEXT NOT NULL DEFAULT 'restricted' CHECK (confidentiality IN ('internal', 'confidential', 'restricted')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'exploring', 'matched', 'closed', 'cancelled')),
  evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
  created_at TEXT NOT NULL
);

CREATE TABLE capability_types (
  capability_type_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE capabilities (
  capability_id TEXT PRIMARY KEY,
  provider_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  capability_type_id TEXT NOT NULL REFERENCES capability_types(capability_type_id),
  offering_type TEXT NOT NULL CHECK (offering_type IN ('expertise', 'capital', 'access', 'service')),
  description TEXT NOT NULL,
  evidence_level TEXT NOT NULL CHECK (evidence_level IN ('declared', 'observed', 'inferred')),
  availability_status TEXT NOT NULL DEFAULT 'unknown' CHECK (availability_status IN ('available', 'unknown', 'unavailable')),
  minimum_amount REAL,
  maximum_amount REAL,
  currency TEXT,
  jurisdiction TEXT,
  evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
  last_verified_at TEXT
);

CREATE TABLE compatibility_rules (
  need_type_id TEXT NOT NULL REFERENCES need_types(need_type_id),
  capability_type_id TEXT NOT NULL REFERENCES capability_types(capability_type_id),
  relevance_weight REAL NOT NULL CHECK (relevance_weight BETWEEN 0 AND 1),
  rationale TEXT NOT NULL,
  PRIMARY KEY (need_type_id, capability_type_id)
);

CREATE TABLE permissions (
  permission_id TEXT PRIMARY KEY,
  subject_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  counterparty_actor_id TEXT REFERENCES actors(actor_id),
  purpose_code TEXT NOT NULL,
  permission_status TEXT NOT NULL DEFAULT 'unknown' CHECK (permission_status IN ('unknown', 'granted', 'denied', 'expired')),
  identity_disclosure_allowed INTEGER NOT NULL DEFAULT 0 CHECK (identity_disclosure_allowed IN (0, 1)),
  contact_allowed INTEGER NOT NULL DEFAULT 0 CHECK (contact_allowed IN (0, 1)),
  evidence_id TEXT REFERENCES evidence(evidence_id),
  granted_at TEXT,
  expires_at TEXT
);

CREATE TABLE constraints_registry (
  constraint_id TEXT PRIMARY KEY,
  actor_id TEXT REFERENCES actors(actor_id),
  need_id TEXT REFERENCES needs(need_id),
  constraint_type TEXT NOT NULL CHECK (constraint_type IN ('capacity', 'conflict', 'jurisdiction', 'liquidity', 'mnpi', 'privacy', 'suitability', 'timing')),
  effect TEXT NOT NULL CHECK (effect IN ('block', 'review', 'penalty')),
  description TEXT NOT NULL,
  penalty_points INTEGER NOT NULL DEFAULT 0 CHECK (penalty_points BETWEEN 0 AND 100),
  evidence_id TEXT REFERENCES evidence(evidence_id),
  valid_until TEXT
);

CREATE TABLE opportunities (
  opportunity_id TEXT PRIMARY KEY,
  need_id TEXT NOT NULL REFERENCES needs(need_id),
  provider_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  path_id TEXT NOT NULL REFERENCES connection_paths(path_id),
  capability_id TEXT NOT NULL REFERENCES capabilities(capability_id),
  match_score REAL NOT NULL CHECK (match_score BETWEEN 0 AND 100),
  route_tier INTEGER NOT NULL CHECK (route_tier BETWEEN 1 AND 3),
  rationale TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested', 'consent_requested', 'approved', 'rejected', 'introduced', 'closed')),
  generated_at TEXT NOT NULL,
  reviewed_by_actor_id TEXT REFERENCES actors(actor_id),
  reviewed_at TEXT,
  UNIQUE (need_id, provider_actor_id, capability_id)
);

CREATE TABLE introductions (
  introduction_id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(opportunity_id),
  initiated_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  requester_consent TEXT NOT NULL DEFAULT 'pending' CHECK (requester_consent IN ('pending', 'granted', 'denied')),
  provider_consent TEXT NOT NULL DEFAULT 'pending' CHECK (provider_consent IN ('pending', 'granted', 'denied')),
  introduction_status TEXT NOT NULL DEFAULT 'draft' CHECK (introduction_status IN ('draft', 'awaiting_consent', 'ready', 'sent', 'accepted', 'declined', 'completed')),
  identity_disclosed_at TEXT,
  introduced_at TEXT,
  outcome_summary TEXT
);

CREATE INDEX idx_relationships_from_status ON relationships(from_actor_id, relationship_status);
CREATE INDEX idx_relationships_to_status ON relationships(to_actor_id, relationship_status);
CREATE INDEX idx_paths_rm_tier_target ON connection_paths(rm_actor_id, route_tier, target_actor_id);
CREATE INDEX idx_needs_open_client_type ON needs(client_actor_id, need_type_id) WHERE status IN ('open', 'exploring');
CREATE INDEX idx_capabilities_type_availability ON capabilities(capability_type_id, availability_status, provider_actor_id);
CREATE INDEX idx_permissions_subject_purpose ON permissions(subject_actor_id, purpose_code, permission_status);
CREATE INDEX idx_constraints_actor_effect ON constraints_registry(actor_id, effect);
CREATE INDEX idx_opportunities_need_tier_score ON opportunities(need_id, route_tier, match_score DESC);

PRAGMA optimize;
