-- Use the named unique constraint so PL/pgSQL output columns cannot shadow it.
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

  select coalesce(
    array_agg(final_id order by completed_first, sort_position),
    array[]::uuid[]
  )
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

revoke execute on function public.sync_daily_assignments(uuid, date, uuid[])
  from public, anon, authenticated;
grant execute on function public.sync_daily_assignments(uuid, date, uuid[])
  to service_role;

;
