CREATE FUNCTION public.save_source_bundle (
  p_user_id uuid,
  p_bundle  jsonb
)
  RETURNS TABLE (
    source_count integer,
    card_count   integer,
    source_id    uuid
  )
  LANGUAGE plpgsql
  SET search_path TO ''
  AS $function$
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
$function$;

REVOKE ALL ON FUNCTION public.save_source_bundle(uuid, jsonb) FROM PUBLIC;

GRANT ALL ON FUNCTION public.save_source_bundle(uuid, jsonb) TO service_role;