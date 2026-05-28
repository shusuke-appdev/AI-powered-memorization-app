-- Cleanup after daily_assignments rollout
--
-- Adds the source_id covering index requested by Supabase performance advisor
-- and removes the old owner-based source_cards policy that is unused in the
-- current server-side service_role-only access model.

CREATE INDEX IF NOT EXISTS idx_daily_assignments_source
  ON public.daily_assignments (source_id)
  WHERE source_id IS NOT NULL;

DROP POLICY IF EXISTS "Users can manage own source cards" ON public.source_cards;
