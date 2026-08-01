CREATE TABLE IF NOT EXISTS public.daily_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  assignment_date DATE NOT NULL,
  card_id UUID NOT NULL REFERENCES public.cards(id) ON DELETE CASCADE,
  source_id UUID REFERENCES public.source_cards(id) ON DELETE SET NULL,
  position INTEGER NOT NULL CHECK (position >= 0),
  completed_at TIMESTAMPTZ,
  quality INTEGER CHECK (quality IS NULL OR quality BETWEEN 0 AND 5),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, assignment_date, card_id),
  UNIQUE (user_id, assignment_date, position)
);

CREATE INDEX IF NOT EXISTS idx_daily_assignments_user_date
  ON public.daily_assignments (user_id, assignment_date, position);

CREATE INDEX IF NOT EXISTS idx_daily_assignments_card
  ON public.daily_assignments (card_id);

ALTER TABLE public.daily_assignments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "No public access" ON public.daily_assignments;
CREATE POLICY "No public access" ON public.daily_assignments FOR ALL USING (false);;
