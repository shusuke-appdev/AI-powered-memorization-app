CREATE FUNCTION public.import_backup_atomic (
  p_user_id        uuid,
  p_sources        jsonb,
  p_cards          jsonb,
  p_reset_progress boolean DEFAULT false
)
  RETURNS TABLE (
    source_count integer,
    card_count   integer
  )
  LANGUAGE plpgsql
  SET search_path TO ''
  AS $function$
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
$function$;

REVOKE ALL ON FUNCTION public.import_backup_atomic(uuid, jsonb, jsonb, boolean) FROM PUBLIC;

GRANT ALL ON FUNCTION public.import_backup_atomic(uuid, jsonb, jsonb, boolean) TO service_role;