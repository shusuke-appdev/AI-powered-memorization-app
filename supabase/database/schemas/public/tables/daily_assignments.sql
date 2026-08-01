CREATE TABLE public.daily_assignments (
  id              uuid                     DEFAULT gen_random_uuid() NOT NULL,
  user_id         uuid                     NOT NULL,
  assignment_date date                     NOT NULL,
  card_id         uuid                     NOT NULL,
  source_id       uuid,
  "position"      integer                  NOT NULL,
  completed_at    timestamp with time zone,
  quality         integer,
  created_at      timestamp with time zone DEFAULT now() NOT NULL
);

CREATE INDEX idx_daily_assignments_source ON public.daily_assignments (source_id)
  WHERE source_id IS NOT NULL;

CREATE INDEX daily_assignments_source_user_idx ON public.daily_assignments (source_id, user_id)
  WHERE source_id IS NOT NULL;

CREATE INDEX daily_assignments_card_user_idx ON public.daily_assignments (card_id, user_id);

CREATE INDEX idx_daily_assignments_card ON public.daily_assignments (card_id);

CREATE INDEX idx_daily_assignments_user_date ON public.daily_assignments (user_id, assignment_date, "position");

CREATE POLICY "No public access" ON public.daily_assignments
  USING (false);

ALTER TABLE public.daily_assignments
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_card_id_fkey FOREIGN KEY (card_id) REFERENCES public.cards(id) ON DELETE CASCADE;

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_card_owner_fkey FOREIGN KEY (card_id, user_id) REFERENCES public.cards(id, user_id) ON DELETE CASCADE;

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_pkey PRIMARY KEY (id);

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_position_check CHECK ("position" >= 0);

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_quality_check CHECK (quality IS NULL OR quality >= 0 AND quality <= 5);

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_user_id_assignment_date_card_id_key UNIQUE (user_id, assignment_date, card_id);

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_user_id_assignment_date_position_key UNIQUE (user_id, assignment_date, "position");

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_source_owner_fkey FOREIGN KEY (source_id, user_id) REFERENCES public.source_cards(id, user_id) ON DELETE SET NULL (source_id);

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.source_cards(id) ON DELETE SET NULL;

ALTER TABLE public.daily_assignments
  ADD CONSTRAINT daily_assignments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

GRANT DELETE, INSERT, SELECT, UPDATE ON public.daily_assignments TO service_role;