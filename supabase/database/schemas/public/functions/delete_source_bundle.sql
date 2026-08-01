CREATE FUNCTION public.delete_source_bundle (
  p_user_id   uuid,
  p_source_id uuid
)
  RETURNS TABLE (
    source_count integer,
    card_count   integer
  )
  LANGUAGE plpgsql
  SET search_path TO ''
  AS $function$
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
$function$;

REVOKE ALL ON FUNCTION public.delete_source_bundle(uuid, uuid) FROM PUBLIC;

GRANT ALL ON FUNCTION public.delete_source_bundle(uuid, uuid) TO service_role;