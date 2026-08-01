CREATE INDEX IF NOT EXISTS idx_daily_assignments_source
  ON public.daily_assignments (source_id)
  WHERE source_id IS NOT NULL;

DROP POLICY IF EXISTS "Users can manage own source cards" ON public.source_cards;;
