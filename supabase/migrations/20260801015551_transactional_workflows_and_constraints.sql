-- Transactional write boundaries and validated data contracts for memorization_app.
-- The Streamlit server calls these functions with a server-side service_role key.

alter table public.users
  add constraint users_username_trimmed_length_check
  check (length(btrim(username)) between 2 and 50) not valid;
alter table public.users validate constraint users_username_trimmed_length_check;

create unique index users_username_normalized_key
  on public.users (lower(btrim(username)));

alter table public.users
  add constraint users_daily_quota_range_check
  check (daily_quota is null or daily_quota between 1 and 100) not valid;
alter table public.users validate constraint users_daily_quota_range_check;

alter table public.source_cards alter column user_id set not null;
alter table public.cards alter column user_id set not null;
alter table public.sessions alter column user_id set not null;

alter table public.source_cards
  add constraint source_cards_category_check
  check (category in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他')) not valid,
  add constraint source_cards_type_check
  check (card_type in ('規範','判例','類型','知識')) not valid,
  add constraint source_cards_text_check
  check (length(btrim(source_text)) > 0) not valid,
  add constraint source_cards_id_user_key unique (id, user_id);
alter table public.source_cards validate constraint source_cards_category_check;
alter table public.source_cards validate constraint source_cards_type_check;
alter table public.source_cards validate constraint source_cards_text_check;

alter table public.cards
  add constraint cards_category_check
  check (category in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他')) not valid,
  add constraint cards_type_check
  check (card_type in ('規範','判例','類型','知識')) not valid,
  add constraint cards_rank_check
  check (rank in ('A+','A','B+','B','C')) not valid,
  add constraint cards_progress_check
  check (
    coalesce(ease_factor, 2.5) >= 1.3
    and coalesce(interval, 0) >= 0
    and coalesce(repetitions, 0) >= 0
    and coalesce(blank_count, 0) >= 0
  ) not valid,
  add constraint cards_id_user_key unique (id, user_id);
alter table public.cards validate constraint cards_category_check;
alter table public.cards validate constraint cards_type_check;
alter table public.cards validate constraint cards_rank_check;
alter table public.cards validate constraint cards_progress_check;

alter table public.cards
  add constraint cards_source_owner_fkey
  foreign key (source_id, user_id)
  references public.source_cards (id, user_id)
  not valid;
alter table public.cards validate constraint cards_source_owner_fkey;

alter table public.daily_assignments
  add constraint daily_assignments_card_owner_fkey
  foreign key (card_id, user_id)
  references public.cards (id, user_id)
  on delete cascade
  not valid,
  add constraint daily_assignments_source_owner_fkey
  foreign key (source_id, user_id)
  references public.source_cards (id, user_id)
  on delete set null (source_id)
  not valid;
alter table public.daily_assignments
  validate constraint daily_assignments_card_owner_fkey;
alter table public.daily_assignments
  validate constraint daily_assignments_source_owner_fkey;

create or replace function public.sync_daily_assignments(
  p_user_id uuid,
  p_assignment_date date,
  p_card_ids uuid[]
)
returns table (
  card_id uuid,
  source_id uuid,
  "position" integer,
  completed_at timestamptz,
  quality integer
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_requested_ids uuid[] := coalesce(p_card_ids, array[]::uuid[]);
  v_final_ids uuid[];
begin
  if p_user_id is null or p_assignment_date is null then
    raise exception 'user_id and assignment_date are required' using errcode = '22023';
  end if;

  if cardinality(v_requested_ids) <> (
    select count(distinct requested_id)
    from unnest(v_requested_ids) as requested(requested_id)
  ) then
    raise exception 'duplicate card ids are not allowed' using errcode = '22023';
  end if;

  if exists (
    select 1
    from unnest(v_requested_ids) as requested(requested_id)
    left join public.cards c
      on c.id = requested.requested_id and c.user_id = p_user_id
    where c.id is null
  ) then
    raise exception 'card does not belong to user' using errcode = '42501';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended(p_user_id::text || ':' || p_assignment_date::text, 0)
  );

  select coalesce(array_agg(final_id order by completed_first, sort_position), array[]::uuid[])
  into v_final_ids
  from (
    select d.card_id as final_id, 0 as completed_first, d.position as sort_position
    from public.daily_assignments d
    where d.user_id = p_user_id
      and d.assignment_date = p_assignment_date
      and d.completed_at is not null
    union all
    select requested.requested_id, 1, requested.ordinality::integer
    from unnest(v_requested_ids) with ordinality as requested(requested_id, ordinality)
    where not exists (
      select 1
      from public.daily_assignments d
      where d.user_id = p_user_id
        and d.assignment_date = p_assignment_date
        and d.card_id = requested.requested_id
        and d.completed_at is not null
    )
  ) final_rows;

  delete from public.daily_assignments d
  where d.user_id = p_user_id
    and d.assignment_date = p_assignment_date
    and not (d.card_id = any(v_final_ids));

  update public.daily_assignments d
  set position = d.position + 1000000
  where d.user_id = p_user_id
    and d.assignment_date = p_assignment_date;

  insert into public.daily_assignments (
    user_id, assignment_date, card_id, source_id, position
  )
  select
    p_user_id,
    p_assignment_date,
    requested.requested_id,
    c.source_id,
    requested.ordinality::integer - 1
  from unnest(v_final_ids) with ordinality as requested(requested_id, ordinality)
  join public.cards c
    on c.id = requested.requested_id and c.user_id = p_user_id
  on conflict on constraint daily_assignments_user_id_assignment_date_card_id_key
  do update set
    source_id = excluded.source_id,
    position = excluded.position;

  return query
  select d.card_id, d.source_id, d.position, d.completed_at, d.quality
  from public.daily_assignments d
  where d.user_id = p_user_id
    and d.assignment_date = p_assignment_date
  order by d.position;
end;
$$;

create or replace function public.complete_daily_review(
  p_user_id uuid,
  p_assignment_date date,
  p_card_id uuid,
  p_quality integer,
  p_ease_factor double precision,
  p_interval integer,
  p_repetitions integer,
  p_next_review date
)
returns table (
  status text,
  assignment_persisted boolean,
  ease_factor double precision,
  "interval" integer,
  repetitions integer,
  next_review date
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_completed_at timestamptz;
  v_rows integer;
begin
  if p_quality not between 0 and 5
     or p_ease_factor < 1.3
     or p_interval < 0
     or p_repetitions < 0
     or p_next_review is null then
    raise exception 'invalid review progress' using errcode = '22023';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended(p_user_id::text || ':' || p_assignment_date::text, 0)
  );

  select d.completed_at
  into v_completed_at
  from public.daily_assignments d
  where d.user_id = p_user_id
    and d.assignment_date = p_assignment_date
    and d.card_id = p_card_id
  for update;

  if not found then
    raise exception 'daily assignment not found' using errcode = 'P0002';
  end if;

  if v_completed_at is not null then
    return query
    select
      'already_completed'::text,
      true,
      c.ease_factor,
      c.interval,
      c.repetitions,
      c.next_review
    from public.cards c
    where c.id = p_card_id and c.user_id = p_user_id;
    return;
  end if;

  update public.cards c
  set ease_factor = p_ease_factor,
      interval = p_interval,
      repetitions = p_repetitions,
      next_review = p_next_review
  where c.id = p_card_id and c.user_id = p_user_id;
  get diagnostics v_rows = row_count;
  if v_rows <> 1 then
    raise exception 'card does not belong to user' using errcode = '42501';
  end if;

  update public.daily_assignments d
  set completed_at = now(), quality = p_quality
  where d.user_id = p_user_id
    and d.assignment_date = p_assignment_date
    and d.card_id = p_card_id;

  return query select
    'applied'::text,
    true,
    p_ease_factor,
    p_interval,
    p_repetitions,
    p_next_review;
end;
$$;

create or replace function public.save_source_bundle(
  p_user_id uuid,
  p_bundle jsonb
)
returns table (source_count integer, card_count integer, source_id uuid)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_mode text := p_bundle->>'mode';
  v_source_id uuid;
  v_source_text text := btrim(coalesce(p_bundle->>'source_text', ''));
  v_title text := btrim(coalesce(p_bundle->>'title', ''));
  v_category text := p_bundle->>'category';
  v_card_type text := p_bundle->>'card_type';
  v_cards jsonb := coalesce(p_bundle->'cards', '[]'::jsonb);
  v_card jsonb;
  v_card_id uuid;
  v_card_count integer := jsonb_array_length(v_cards);
  v_rows integer;
begin
  if p_user_id is null or v_mode not in ('create', 'update', 'replace') then
    raise exception 'invalid bundle mode or user' using errcode = '22023';
  end if;
  if v_source_text = '' or v_card_count = 0 then
    raise exception 'source text and cards are required' using errcode = '22023';
  end if;
  if v_category not in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他')
     or v_card_type not in ('規範','判例','類型','知識') then
    raise exception 'invalid source metadata' using errcode = '22023';
  end if;

  for v_card in select value from jsonb_array_elements(v_cards)
  loop
    if btrim(coalesce(v_card->>'question', '')) = ''
       or v_card->>'category' is distinct from v_category
       or v_card->>'card_type' is distinct from v_card_type
       or v_card->>'rank' not in ('A+','A','B+','B','C') then
      raise exception 'invalid card metadata' using errcode = '22023';
    end if;
    if v_card_type in ('類型','知識') then
      if coalesce(v_card->>'answer', '') <> ''
         or coalesce((v_card->>'blank_count')::integer, 0) <> 0 then
        raise exception 'non-blank cards cannot have answers or blanks' using errcode = '22023';
      end if;
    elsif btrim(coalesce(v_card->>'answer', '')) = ''
       or coalesce((v_card->>'blank_count')::integer, 0) < 1 then
      raise exception 'blank cards require answers and blanks' using errcode = '22023';
    end if;
  end loop;

  if v_mode = 'create' then
    insert into public.source_cards (
      user_id, source_text, title, category, card_type
    ) values (
      p_user_id, v_source_text, v_title, v_category, v_card_type
    ) returning id into v_source_id;
  else
    v_source_id := nullif(p_bundle->>'source_id', '')::uuid;
    if v_source_id is null then
      raise exception 'source_id is required' using errcode = '22023';
    end if;
    perform 1 from public.source_cards s
    where s.id = v_source_id and s.user_id = p_user_id
    for update;
    if not found then
      raise exception 'source card does not belong to user' using errcode = '42501';
    end if;
    update public.source_cards s
    set source_text = v_source_text,
        title = v_title,
        category = v_category,
        card_type = v_card_type
    where s.id = v_source_id and s.user_id = p_user_id;
  end if;

  if v_mode = 'update' then
    if (
      select count(*)
      from public.cards c
      where c.user_id = p_user_id and c.source_id = v_source_id
    ) <> v_card_count
    or (
      select count(distinct nullif(value->>'id', '')::uuid)
      from jsonb_array_elements(v_cards)
    ) <> v_card_count then
      raise exception 'update must contain every linked card exactly once' using errcode = '22023';
    end if;

    for v_card in select value from jsonb_array_elements(v_cards)
    loop
      v_card_id := nullif(v_card->>'id', '')::uuid;
      update public.cards c
      set question = v_card->>'question',
          answer = coalesce(v_card->>'answer', ''),
          title = v_title,
          category = v_category,
          card_type = v_card_type,
          rank = v_card->>'rank',
          blank_count = (v_card->>'blank_count')::integer,
          highlighted_keywords = coalesce(v_card->>'highlighted_keywords', ''),
          ease_factor = coalesce((v_card->>'ease_factor')::double precision, c.ease_factor),
          interval = coalesce((v_card->>'interval')::integer, c.interval),
          repetitions = coalesce((v_card->>'repetitions')::integer, c.repetitions),
          next_review = coalesce((v_card->>'next_review')::date, c.next_review),
          is_favorite = coalesce((v_card->>'is_favorite')::boolean, c.is_favorite)
      where c.id = v_card_id
        and c.user_id = p_user_id
        and c.source_id = v_source_id;
      get diagnostics v_rows = row_count;
      if v_rows <> 1 then
        raise exception 'card does not belong to source and user' using errcode = '42501';
      end if;
    end loop;
  else
    if v_mode = 'replace' then
      delete from public.cards c
      where c.user_id = p_user_id and c.source_id = v_source_id;
    end if;

    for v_card in select value from jsonb_array_elements(v_cards)
    loop
      insert into public.cards (
        user_id, source_id, question, answer, title, category, card_type, rank,
        blank_count, highlighted_keywords, ease_factor, interval, repetitions,
        next_review, is_favorite
      ) values (
        p_user_id,
        v_source_id,
        v_card->>'question',
        coalesce(v_card->>'answer', ''),
        v_title,
        v_category,
        v_card_type,
        v_card->>'rank',
        (v_card->>'blank_count')::integer,
        coalesce(v_card->>'highlighted_keywords', ''),
        coalesce((v_card->>'ease_factor')::double precision, 2.5),
        coalesce((v_card->>'interval')::integer, 1),
        coalesce((v_card->>'repetitions')::integer, 0),
        coalesce((v_card->>'next_review')::date, current_date),
        coalesce((v_card->>'is_favorite')::boolean, false)
      );
    end loop;
  end if;

  return query select 1, v_card_count, v_source_id;
end;
$$;

create or replace function public.delete_source_bundle(
  p_user_id uuid,
  p_source_id uuid
)
returns table (source_count integer, card_count integer)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_card_count integer;
begin
  perform 1 from public.source_cards s
  where s.id = p_source_id and s.user_id = p_user_id
  for update;
  if not found then
    raise exception 'source card does not belong to user' using errcode = 'P0002';
  end if;

  delete from public.cards c
  where c.source_id = p_source_id and c.user_id = p_user_id;
  get diagnostics v_card_count = row_count;

  delete from public.source_cards s
  where s.id = p_source_id and s.user_id = p_user_id;

  return query select 1, v_card_count;
end;
$$;

create or replace function public.import_backup_atomic(
  p_user_id uuid,
  p_sources jsonb,
  p_cards jsonb,
  p_reset_progress boolean default false
)
returns table (source_count integer, card_count integer)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_sources jsonb := coalesce(p_sources, '[]'::jsonb);
  v_cards jsonb := coalesce(p_cards, '[]'::jsonb);
  v_source jsonb;
  v_card jsonb;
  v_source_map jsonb := '{}'::jsonb;
  v_export_id text;
  v_source_export_id text;
  v_source_id uuid;
  v_card_type text;
begin
  if p_user_id is null or jsonb_array_length(v_cards) = 0 then
    raise exception 'user and at least one card are required' using errcode = '22023';
  end if;

  for v_source in select value from jsonb_array_elements(v_sources)
  loop
    v_export_id := btrim(coalesce(v_source->>'export_id', ''));
    if v_export_id = '' or v_source_map ? v_export_id
       or btrim(coalesce(v_source->>'source_text', '')) = ''
       or v_source->>'category' not in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他')
       or v_source->>'card_type' not in ('規範','判例','類型','知識') then
      raise exception 'invalid source import item' using errcode = '22023';
    end if;

    insert into public.source_cards (
      user_id, source_text, title, category, card_type
    ) values (
      p_user_id,
      v_source->>'source_text',
      coalesce(v_source->>'title', ''),
      v_source->>'category',
      v_source->>'card_type'
    ) returning id into v_source_id;
    v_source_map := v_source_map || jsonb_build_object(v_export_id, v_source_id::text);
  end loop;

  for v_card in select value from jsonb_array_elements(v_cards)
  loop
    v_source_export_id := btrim(coalesce(v_card->>'source_export_id', ''));
    if v_source_export_id <> '' and not (v_source_map ? v_source_export_id) then
      raise exception 'card references missing source' using errcode = '22023';
    end if;
    v_source_id := null;
    if v_source_export_id <> '' then
      v_source_id := (v_source_map->>v_source_export_id)::uuid;
    end if;
    v_card_type := v_card->>'card_type';
    if btrim(coalesce(v_card->>'question', '')) = ''
       or v_card->>'category' not in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他')
       or v_card_type not in ('規範','判例','類型','知識')
       or v_card->>'rank' not in ('A+','A','B+','B','C') then
      raise exception 'invalid card import item' using errcode = '22023';
    end if;
    if v_card_type in ('類型','知識') then
      if coalesce(v_card->>'answer', '') <> ''
         or coalesce((v_card->>'blank_count')::integer, 0) <> 0 then
        raise exception 'invalid non-blank import item' using errcode = '22023';
      end if;
    elsif btrim(coalesce(v_card->>'answer', '')) = ''
       or coalesce((v_card->>'blank_count')::integer, 0) < 1 then
      raise exception 'invalid blank import item' using errcode = '22023';
    end if;

    insert into public.cards (
      user_id, source_id, question, answer, title, category, card_type, rank,
      blank_count, highlighted_keywords, ease_factor, interval, repetitions,
      next_review, is_favorite
    ) values (
      p_user_id,
      v_source_id,
      v_card->>'question',
      coalesce(v_card->>'answer', ''),
      coalesce(v_card->>'title', ''),
      v_card->>'category',
      v_card_type,
      v_card->>'rank',
      (v_card->>'blank_count')::integer,
      coalesce(v_card->>'highlighted_keywords', ''),
      case when p_reset_progress then 2.5 else coalesce((v_card->>'ease_factor')::double precision, 2.5) end,
      case when p_reset_progress then 1 else coalesce((v_card->>'interval')::integer, 1) end,
      case when p_reset_progress then 0 else coalesce((v_card->>'repetitions')::integer, 0) end,
      case when p_reset_progress then current_date else coalesce((v_card->>'next_review')::date, current_date) end,
      coalesce((v_card->>'is_favorite')::boolean, false)
    );
  end loop;

  return query select jsonb_array_length(v_sources), jsonb_array_length(v_cards);
end;
$$;

revoke execute on function public.sync_daily_assignments(uuid, date, uuid[])
  from public, anon, authenticated;
revoke execute on function public.complete_daily_review(uuid, date, uuid, integer, double precision, integer, integer, date)
  from public, anon, authenticated;
revoke execute on function public.save_source_bundle(uuid, jsonb)
  from public, anon, authenticated;
revoke execute on function public.delete_source_bundle(uuid, uuid)
  from public, anon, authenticated;
revoke execute on function public.import_backup_atomic(uuid, jsonb, jsonb, boolean)
  from public, anon, authenticated;

grant execute on function public.sync_daily_assignments(uuid, date, uuid[])
  to service_role;
grant execute on function public.complete_daily_review(uuid, date, uuid, integer, double precision, integer, integer, date)
  to service_role;
grant execute on function public.save_source_bundle(uuid, jsonb)
  to service_role;
grant execute on function public.delete_source_bundle(uuid, uuid)
  to service_role;
grant execute on function public.import_backup_atomic(uuid, jsonb, jsonb, boolean)
  to service_role;
