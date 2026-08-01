CREATE TABLE public.sessions (
  token      uuid                     DEFAULT gen_random_uuid() NOT NULL,
  user_id    uuid                     NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone NOT NULL
);

CREATE INDEX idx_sessions_user_id ON public.sessions (user_id);

CREATE POLICY "No public access" ON public.sessions
  USING (false);

ALTER TABLE public.sessions
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.sessions
  ADD CONSTRAINT sessions_pkey PRIMARY KEY (token);

ALTER TABLE public.sessions
  ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

GRANT DELETE, INSERT, SELECT, UPDATE ON public.sessions TO service_role;