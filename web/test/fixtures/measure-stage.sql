-- The caller substitutes SEED with performance.sql, replacing :'owner' with fixture_owner.
-- Run on staging only. No synthetic writes survive the inner transaction.
do $measure$
declare
  fixture_owner uuid := gen_random_uuid();
  fixture_auth uuid := gen_random_uuid();
  fixture_email text := fixture_auth||'@example.test';
  filter jsonb := '{"mode":"range","subjects":["民法"]}';
  view_now jsonb;
  current_card jsonb;
  started timestamptz;
  initial_plan json;
  legacy_bytes integer;
  review_bytes integer;
  practice_bytes integer;
  legacy_ms double precision[] := '{}';
  review_ms double precision[] := '{}';
  practice_ms double precision[] := '{}';
  grade_ms double precision[] := '{}';
  result jsonb;
  grade_payload jsonb;
begin
  begin
    insert into public.users(id,username,password_hash) values (fixture_owner,'timing-'||fixture_owner,'');
    insert into auth.users(id,email) values (fixture_auth,fixture_email);
    insert into study_private.invitations(email) values (fixture_email);
    insert into study_private.identities(auth_id,user_id) values (fixture_auth,fixture_owner);
    -- SEED
    execute format(
      'explain (analyze,buffers,format json) select c.id from public.cards c
       where c.user_id=%L and coalesce(c.source_id,c.id)=%L and c.study_archived_at is null',
      fixture_owner,md5('perf-source-1')::uuid
    ) into initial_plan;
    perform set_config('request.jwt.claim.sub',fixture_auth::text,true);
    execute 'set local role authenticated';
    for sample in 1..20 loop
      started := clock_timestamp();
      legacy_bytes := octet_length(public.study_api('library')::text);
      legacy_ms := legacy_ms || (1000*extract(epoch from clock_timestamp()-started))::double precision;
      started := clock_timestamp();
      view_now := public.study_api('review_view');
      review_ms := review_ms || (1000*extract(epoch from clock_timestamp()-started))::double precision;
      review_bytes := octet_length(view_now::text);
      started := clock_timestamp();
      practice_bytes := octet_length(public.study_api('practice_options')::text)
        + octet_length(public.study_api('practice_search',filter)::text);
      practice_ms := practice_ms || (1000*extract(epoch from clock_timestamp()-started))::double precision;
      current_card := view_now->'current';
      grade_payload := current_card || jsonb_build_object('grades',jsonb_build_object('1',4),'finish',false);
      begin
        started := clock_timestamp();
        perform public.study_api('evaluate',grade_payload);
        grade_ms := grade_ms || (1000*extract(epoch from clock_timestamp()-started))::double precision;
        raise exception 'discard timing grade' using errcode='P0981';
      exception when sqlstate 'P0981' then null;
      end;
    end loop;
    execute 'reset role';
    select jsonb_build_object(
      'legacy_json_bytes',legacy_bytes,'review_json_bytes',review_bytes,'practice_json_bytes',practice_bytes,
      'legacy_p95_ms',(select round(percentile_disc(.95) within group(order by t)::numeric,1) from unnest(legacy_ms) t),
      'review_p95_ms',(select round(percentile_disc(.95) within group(order by t)::numeric,1) from unnest(review_ms) t),
      'practice_p95_ms',(select round(percentile_disc(.95) within group(order by t)::numeric,1) from unnest(practice_ms) t),
      'grade_p95_ms',(select round(percentile_disc(.95) within group(order by t)::numeric,1) from unnest(grade_ms) t),
      'sources',(select count(*) from public.source_cards where user_id=fixture_owner),
      'cards',(select count(*) from public.cards where user_id=fixture_owner),
      'active',(select count(*) from public.cards where user_id=fixture_owner and study_archived_at is null),
      'plan',initial_plan->0->'Plan'->>'Node Type',
      'plan_ms',initial_plan->0->>'Execution Time'
    ) into result;
    raise exception 'discard timing fixture' using errcode='P0982';
  exception when sqlstate 'P0982' then null;
  end;
  if exists(select 1 from public.users where id=fixture_owner)
    or exists(select 1 from auth.users where id=fixture_auth)
    or exists(select 1 from study_private.invitations where email=fixture_email) then
    raise exception 'synthetic user still present';
  end if;
  perform set_config('study.synthetic_timing',result::text,false);
end
$measure$;
select current_setting('study.synthetic_timing')::jsonb as synthetic_stage_timing;
