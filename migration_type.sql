-- タイプ（下位カテゴリ）カラム追加マイグレーション
-- Supabase SQLエディタで実行してください

-- cards テーブルに card_type カラム追加
ALTER TABLE public.cards ADD COLUMN IF NOT EXISTS card_type TEXT DEFAULT NULL;

-- source_cards テーブルに card_type カラム追加
ALTER TABLE public.source_cards ADD COLUMN IF NOT EXISTS card_type TEXT DEFAULT NULL;
