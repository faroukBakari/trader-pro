-- PostgreSQL 16 initialization script for trader-pro datastore
-- Loads required extensions (stock postgres:16 image includes btree_gist in contrib)

-- btree_gist: Required for EXCLUDE constraints with range types
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Verify extension loaded
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'btree_gist') THEN
        RAISE EXCEPTION 'btree_gist extension failed to load';
    END IF;
    RAISE NOTICE 'PostgreSQL initialized with btree_gist extension';
END
$$;
