-- 全テーブルでRLS (Row Level Security) を有効化
-- これにより、デフォルトで全ての外部アクセスが拒否されます
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_cards ENABLE ROW LEVEL SECURITY;

-- 明示的に「アクセス拒否」ポリシーを作成（念のため）
-- Service Role Key（サーバー側管理者キー）はこれをバイパスできるため、アプリは動作します

-- users
DROP POLICY IF EXISTS "No public access" ON public.users;
CREATE POLICY "No public access" ON public.users FOR ALL USING (false);

-- sessions
DROP POLICY IF EXISTS "No public access" ON public.sessions;
CREATE POLICY "No public access" ON public.sessions FOR ALL USING (false);

-- cards
DROP POLICY IF EXISTS "No public access" ON public.cards;
CREATE POLICY "No public access" ON public.cards FOR ALL USING (false);

-- source_cards
DROP POLICY IF EXISTS "No public access" ON public.source_cards;
CREATE POLICY "No public access" ON public.source_cards FOR ALL USING (false);
