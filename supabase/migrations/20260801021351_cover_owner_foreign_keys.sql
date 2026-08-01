-- Cover the composite ownership foreign keys added by the transactional migration.
create index cards_source_user_idx
  on public.cards (source_id, user_id)
  where source_id is not null;

create index daily_assignments_card_user_idx
  on public.daily_assignments (card_id, user_id);

create index daily_assignments_source_user_idx
  on public.daily_assignments (source_id, user_id)
  where source_id is not null;
