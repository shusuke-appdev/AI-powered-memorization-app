-- Migration for Rank System & Daily Quota

-- 1. Add rank column to cards
-- 'rank' will store the importance rank: A+, A, B+, B, C (default: 'B')
ALTER TABLE public.cards ADD COLUMN IF NOT EXISTS rank VARCHAR(10) DEFAULT 'B';

-- 2. Add daily_quota column to users
-- Default quota is 15
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS daily_quota INTEGER DEFAULT 15;

-- 3. Add highlighted_keywords column to cards
-- 'highlighted_keywords' stores comma separated keywords for Type/Knowledge cards
ALTER TABLE public.cards ADD COLUMN IF NOT EXISTS highlighted_keywords TEXT DEFAULT '';
