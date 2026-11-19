create index cards_active_user_target_idx on public.cards (user_id, (coalesce(source_id,id))) where study_archived_at is null;
