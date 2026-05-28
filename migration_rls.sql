-- 全テーブルでRLS (Row Level Security) を有効化
-- RLSは「どの行を読める/書けるか」を制御します。
-- Data APIにテーブルを到達可能にするGRANTとは別レイヤーです。
-- SupabaseのData API明示GRANT対応は migration_data_api_grants.sql を実行してください。
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_cards ENABLE ROW LEVEL SECURITY;

-- 明示的に「アクセス拒否」ポリシーを作成（念のため）
-- Service Role Key（サーバー側管理者キー）はRLSをバイパスできるため、アプリは動作します。
-- anon/authenticated から直接Data APIを使う運用に変える場合は、
-- 所有者ベースのRLSポリシーを別途設計してください。

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
DROP POLICY IF EXISTS "Users can manage own source cards" ON public.source_cards;
CREATE POLICY "No public access" ON public.source_cards FOR ALL USING (false);
