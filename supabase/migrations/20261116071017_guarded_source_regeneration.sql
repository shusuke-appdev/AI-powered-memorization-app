create schema if not exists study_private;
revoke all on schema study_private from public;
grant usage on schema study_private to service_role;

create table study_private.replaced_cards (
  id uuid primary key,
  user_id uuid not null references public.users(id) on delete cascade,
  source_id uuid,
  card jsonb not null,
  assignments jsonb not null,
  archived_at timestamptz not null default now()
);
alter table study_private.replaced_cards enable row level security;
grant select, insert on study_private.replaced_cards to service_role;

create function public.replace_source_bundle_checked(p_user_id uuid, p_bundle jsonb)
returns table(source_count integer, card_count integer, source_id uuid)
language plpgsql security invoker set search_path = ''
as $$
declare
  sid uuid := (p_bundle->>'source_id')::uuid;
  old_source public.source_cards%rowtype;
  current_cards jsonb;
  expected jsonb := p_bundle->'expected';
  items jsonb := p_bundle->'cards';
  item jsonb;
  matched uuid;
  kept uuid[] := '{}';
  fav boolean;
  day date := (now() at time zone 'Asia/Tokyo')::date;
begin
  if p_bundle->>'mode' is distinct from 'replace' or expected is null or
     jsonb_typeof(items) is distinct from 'array' or jsonb_array_length(items) = 0 then
    raise exception 'invalid replacement' using errcode = '22023';
  end if;
  select s.* into old_source from public.source_cards s
  where s.id = sid and s.user_id = p_user_id for update;
  if not found then raise exception 'replacement conflict' using errcode = '40001'; end if;
  perform c.id from public.cards c
  where c.source_id = sid and c.user_id = p_user_id order by c.id for update;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', c.id, 'question', c.question, 'answer', c.answer,
    'title', coalesce(c.title, ''), 'category', coalesce(c.category, 'その他'),
    'card_type', c.card_type, 'rank', coalesce(c.rank, 'B'),
    'highlighted_keywords', coalesce(c.highlighted_keywords, '')
  ) order by c.id), '[]'), coalesce(bool_or(c.is_favorite), false)
  into current_cards, fav from public.cards c where c.source_id = sid and c.user_id = p_user_id;

  if expected->'source' is distinct from jsonb_build_object(
    'source_text', old_source.source_text, 'title', old_source.title,
    'category', old_source.category, 'card_type', old_source.card_type
  ) or expected->'cards' is distinct from current_cards then
    raise exception 'replacement conflict' using errcode = '40001';
  end if;

  for item in select value from jsonb_array_elements(items) loop
    if coalesce(btrim(item->>'question'), '') = ''
      or not coalesce(item->>'card_type' = p_bundle->>'card_type', false)
      or not coalesce(item->>'category' = p_bundle->>'category', false)
      or not coalesce(item->>'rank' in ('A+','A','B+','B','C'), false)
      or (case when item->>'card_type' in ('知識','類型')
        then coalesce(item->>'answer','') <> '' or (item->>'blank_count')::int is distinct from 0
        else coalesce(btrim(item->>'answer'),'') = '' or coalesce((item->>'blank_count')::int,0) < 1
      end) then
      raise exception 'invalid replacement card' using errcode = '22023';
    end if;

    select c.id into matched from public.cards c
    where c.source_id = sid and c.user_id = p_user_id and c.id <> all(kept)
      and c.question = item->>'question' and c.answer = item->>'answer'
      and c.card_type = item->>'card_type'
    order by c.id limit 1;
    if matched is null then
      insert into public.cards(
        user_id, source_id, question, answer, title, category, card_type, rank,
        blank_count, highlighted_keywords, is_favorite, next_review
      ) values (
        p_user_id, sid, item->>'question', item->>'answer', p_bundle->>'title',
        item->>'category', item->>'card_type', item->>'rank', (item->>'blank_count')::int,
        item->>'highlighted_keywords', fav, day
      ) returning id into matched;
    else
      update public.cards c set title = p_bundle->>'title', category = item->>'category',
        rank = item->>'rank', blank_count = (item->>'blank_count')::int,
        highlighted_keywords = item->>'highlighted_keywords'
      where c.id = matched and c.user_id = p_user_id;
    end if;
    kept := array_append(kept, matched);
  end loop;

  insert into study_private.replaced_cards(id, user_id, source_id, card, assignments)
  select c.id, p_user_id, sid, to_jsonb(c), coalesce((
    select jsonb_agg(to_jsonb(d) order by d.assignment_date, d.position)
    from public.daily_assignments d where d.card_id = c.id and d.user_id = p_user_id
  ), '[]')
  from public.cards c where c.source_id = sid and c.user_id = p_user_id and c.id <> all(kept);
  delete from public.cards c
  where c.source_id = sid and c.user_id = p_user_id and c.id <> all(kept);

  update public.source_cards s set source_text = p_bundle->>'source_text', title = p_bundle->>'title',
    category = p_bundle->>'category', card_type = p_bundle->>'card_type'
  where s.id = sid and s.user_id = p_user_id;
  return query select 1, cardinality(kept), sid;
end;
$$;

revoke execute on function public.replace_source_bundle_checked(uuid, jsonb)
from public, anon, authenticated;
grant execute on function public.replace_source_bundle_checked(uuid, jsonb) to service_role;
