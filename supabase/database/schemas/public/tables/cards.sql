CREATE TABLE public.cards (
  id                   uuid                     DEFAULT gen_random_uuid() NOT NULL,
  user_id              uuid                     NOT NULL,
  question             text                     NOT NULL,
  answer               text                     NOT NULL,
  title                text                     DEFAULT ''::text,
  category             text                     DEFAULT 'その他'::text,
  ease_factor          double precision         DEFAULT 2.5,
  "interval"           integer                  DEFAULT 1,
  repetitions          integer                  DEFAULT 0,
  next_review          date                     DEFAULT CURRENT_DATE,
  source_id            uuid,
  blank_count          integer                  DEFAULT 1,
  created_at           timestamp with time zone DEFAULT now(),
  is_favorite          boolean                  DEFAULT false,
  card_type            text,
  rank                 character varying(10)    DEFAULT 'B'::character varying,
  highlighted_keywords text                     DEFAULT ''::text
);

CREATE INDEX cards_source_user_idx ON public.cards (source_id, user_id)
  WHERE source_id IS NOT NULL;

CREATE INDEX idx_cards_user_id ON public.cards (user_id);

CREATE INDEX idx_cards_source_id ON public.cards (source_id);

CREATE POLICY "No public access" ON public.cards
  USING (false);

ALTER TABLE public.cards
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cards
  ADD CONSTRAINT cards_category_check CHECK (category = ANY (ARRAY['民法'::text, '商法'::text, '刑法'::text, '憲法'::text, '行政法'::text, '民事訴訟法'::text, '刑事訴訟法'::text, 'その他'::text]));

ALTER TABLE public.cards
  ADD CONSTRAINT cards_id_user_key UNIQUE (id, user_id);

ALTER TABLE public.cards
  ADD CONSTRAINT cards_pkey PRIMARY KEY (id);

ALTER TABLE public.cards
  ADD CONSTRAINT cards_progress_check
    CHECK
    (COALESCE(ease_factor, 2.5::double precision) >= 1.3::double precision AND COALESCE("interval", 0) >= 0 AND COALESCE(repetitions, 0) >= 0 AND COALESCE(blank_count, 0) >= 0);

ALTER TABLE public.cards
  ADD CONSTRAINT cards_rank_check
    CHECK (rank::text = ANY (ARRAY['A+'::character varying, 'A'::character varying, 'B+'::character varying, 'B'::character varying, 'C'::character varying]::text[]));

ALTER TABLE public.cards
  ADD CONSTRAINT cards_type_check CHECK (card_type = ANY (ARRAY['規範'::text, '判例'::text, '類型'::text, '知識'::text]));

ALTER TABLE public.cards
  ADD CONSTRAINT cards_source_owner_fkey FOREIGN KEY (source_id, user_id) REFERENCES public.source_cards(id, user_id);

ALTER TABLE public.cards
  ADD CONSTRAINT cards_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.source_cards(id) ON DELETE SET NULL;

ALTER TABLE public.cards
  ADD CONSTRAINT cards_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

GRANT DELETE, INSERT, SELECT, UPDATE ON public.cards TO service_role;