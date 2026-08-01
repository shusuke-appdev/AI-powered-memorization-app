CREATE TABLE public.source_cards (
  id          uuid                     DEFAULT gen_random_uuid() NOT NULL,
  user_id     uuid                     NOT NULL,
  source_text text                     NOT NULL,
  title       text                     DEFAULT ''::text,
  category    text                     DEFAULT 'その他'::text,
  created_at  timestamp with time zone DEFAULT now(),
  card_type   text
);

CREATE INDEX idx_source_cards_user_id ON public.source_cards (user_id);

CREATE POLICY "No public access" ON public.source_cards
  USING (false);

ALTER TABLE public.source_cards
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.source_cards
  ADD CONSTRAINT source_cards_category_check CHECK (category = ANY (ARRAY['民法'::text, '商法'::text, '刑法'::text, '憲法'::text, '行政法'::text, '民事訴訟法'::text, '刑事訴訟法'::text, 'その他'::text]));

ALTER TABLE public.source_cards
  ADD CONSTRAINT source_cards_id_user_key UNIQUE (id, user_id);

ALTER TABLE public.source_cards
  ADD CONSTRAINT source_cards_pkey PRIMARY KEY (id);

ALTER TABLE public.source_cards
  ADD CONSTRAINT source_cards_text_check CHECK (length(btrim(source_text)) > 0);

ALTER TABLE public.source_cards
  ADD CONSTRAINT source_cards_type_check CHECK (card_type = ANY (ARRAY['規範'::text, '判例'::text, '類型'::text, '知識'::text]));

ALTER TABLE public.source_cards
  ADD CONSTRAINT source_cards_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

GRANT DELETE, INSERT, SELECT, UPDATE ON public.source_cards TO service_role;