GRANT USAGE ON SCHEMA public TO service_role;

REVOKE ALL PRIVILEGES ON TABLE public.daily_assignments
  FROM anon, authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.daily_assignments
  TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;;
