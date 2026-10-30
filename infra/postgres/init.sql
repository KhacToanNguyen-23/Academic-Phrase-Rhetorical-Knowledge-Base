-- Extensions dùng cho AP-RKB (xem doc/adr/0002-postgresql.md)
CREATE EXTENSION IF NOT EXISTS vector;     -- near-duplicate, diversification (FR-02.5, FR-07.6)
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy search (FR-07.1)
CREATE EXTENSION IF NOT EXISTS ltree;      -- taxonomy hierarchy (FR-01.1)
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid, hashing
