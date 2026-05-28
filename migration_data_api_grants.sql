-- Supabase Data API explicit grants migration
--
-- Run this after the base tables exist.
-- This app is operated as a trusted Streamlit server-side app: SUPABASE_KEY must
-- be a server-side service_role/secret key, not a browser-exposed anon key.
--
-- Supabase is changing public-schema table exposure so new tables are not
-- automatically reachable through the Data API. Keep Data API access explicit:
-- RLS controls row access, while GRANT controls whether a role can reach a table
-- through PostgREST / GraphQL / supabase clients at all.

-- Opt in to explicit grants for future objects in public.
-- New tables/functions/sequences must receive an intentional GRANT in the same
-- migration that creates them.
-- This migration updates postgres-owned default privileges. Supabase-managed
-- supabase_admin default privileges may require project/platform-level handling.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON TABLES
  FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON FUNCTIONS
  FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON SEQUENCES
  FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS
  FROM PUBLIC;

-- Do not expose the app tables to public client roles.
-- Existing projects may already have implicit grants from Supabase defaults, so
-- revoke them before applying the service_role-only grants used by this app.
REVOKE ALL PRIVILEGES ON TABLE
  public.users,
  public.sessions,
  public.cards,
  public.source_cards
FROM anon, authenticated, service_role;

REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
FROM anon, authenticated, service_role;

-- Explicit Data API access for the server-side Supabase key used by Streamlit.
GRANT USAGE ON SCHEMA public TO service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  public.users,
  public.sessions,
  public.cards,
  public.source_cards
TO service_role;

-- Safe no-op for UUID-only schemas, required if any serial/identity sequences
-- exist now or are added before the next migration is applied.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
