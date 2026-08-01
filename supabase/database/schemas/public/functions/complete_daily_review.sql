CREATE FUNCTION public.complete_daily_review (
  p_user_id         uuid,
  p_assignment_date date,
  p_card_id         uuid,
  p_quality         integer,
  p_ease_factor     double precision,
  p_interval        integer,
  p_repetitions     integer,
  p_next_review     date
)
  RETURNS TABLE (
    status               text,
    assignment_persisted boolean,
    ease_factor          double precision,
    "interval"           integer,
    repetitions          integer,
    next_review          date
  )
  LANGUAGE plpgsql
  SET search_path TO ''
  AS $function$
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
$function$;

REVOKE ALL ON FUNCTION public.complete_daily_review(uuid, date, uuid, integer, double precision, integer, integer, date) FROM PUBLIC;

GRANT ALL ON FUNCTION public.complete_daily_review(uuid, date, uuid, integer, double precision, integer, integer, date) TO service_role;