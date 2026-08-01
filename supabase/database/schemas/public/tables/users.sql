CREATE TABLE public.users (
  id            uuid                     DEFAULT gen_random_uuid() NOT NULL,
  username      text                     NOT NULL,
  password_hash text                     NOT NULL,
  api_key       text                     DEFAULT ''::text,
  created_at    timestamp with time zone DEFAULT now(),
  daily_quota   integer                  DEFAULT 15
);

CREATE UNIQUE INDEX users_username_normalized_key ON public.users (lower(btrim(username)));

CREATE POLICY "No public access" ON public.users
  USING (false);

ALTER TABLE public.users
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.users
  ADD CONSTRAINT users_daily_quota_range_check CHECK (daily_quota IS NULL OR daily_quota >= 1 AND daily_quota <= 100);

ALTER TABLE public.users
  ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE public.users
  ADD CONSTRAINT users_username_key UNIQUE (username);

ALTER TABLE public.users
  ADD CONSTRAINT users_username_trimmed_length_check CHECK (length(btrim(username)) >= 2 AND length(btrim(username)) <= 50);

GRANT DELETE, INSERT, SELECT, UPDATE ON public.users TO service_role;