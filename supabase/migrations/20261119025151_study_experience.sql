create or replace function study_private.evaluate(p_user uuid,p_data jsonb) returns jsonb
language plpgsql set search_path = ''
as $$
declare
  a study_private.assignments%rowtype;
  t study_private.targets%rowtype;
  changes jsonb := p_data->'grades';
  all_grades jsonb;
  hole_ids integer[];
  valid_keys text[];
  quality integer;
  next_interval integer;
  normal_interval integer;
  next_repetitions integer;
  next_ease double precision;
  covered integer[];
  complete boolean := coalesce((p_data->>'finish')::boolean,false);
begin
  select d.* into a from study_private.assignments d where d.user_id=p_user
    and d.target_id=(p_data->>'target_id')::uuid and d.day=(p_data->>'day')::date;
  if not found or a.version is distinct from (p_data->>'version')::uuid
    or a.card_id is distinct from (p_data->>'card_id')::uuid then
    raise exception 'assignment changed' using errcode='40001';
  end if;
  if a.completed_at is not null then
    if jsonb_typeof(changes)='object' and changes<>'{}'::jsonb and a.grades @> changes then
      return to_jsonb(a);
    end if;
    raise exception 'review already completed with different grades' using errcode='40001';
  end if;
  if a.day<>study_private.today() then raise exception 'day changed' using errcode='40001'; end if;
  select t0.* into t from study_private.targets t0 where t0.id=a.target_id and t0.user_id=p_user for update;
  if t.version is distinct from a.version then raise exception 'card changed' using errcode='40001'; end if;
  hole_ids := study_private.holes(a.layout);
  valid_keys := case when cardinality(hole_ids)=0 then array['0'] else hole_ids::text[] end;
  if jsonb_typeof(changes) is distinct from 'object' or changes='{}'::jsonb or exists (
    select 1 from jsonb_each(changes) g where g.key<>all(valid_keys)
      or not (g.value <@ case when cardinality(hole_ids)=0
        then '[0,3,4,5]'::jsonb else '[0,2,4]'::jsonb end and jsonb_typeof(g.value)='number')
  ) then raise exception 'invalid grades' using errcode='22023'; end if;

  if a.revision is distinct from (p_data->>'revision')::integer then
    if not complete and a.grades @> changes then return to_jsonb(a); end if;
    raise exception 'draft changed' using errcode='40001';
  end if;
  all_grades := a.grades || changes;
  if complete then
    if not (all_grades ?& valid_keys) then raise exception 'missing grades' using errcode='22023'; end if;
    select min(value::integer) into quality from jsonb_each(all_grades);
    normal_interval := case t.repetitions when 0 then 1 when 1 then 6
      else greatest(1,floor(least(t.interval*t.ease_factor,36500))::integer) end;
    next_repetitions := t.repetitions+1;
    next_interval := normal_interval;
    if quality=0 then
      next_interval := 1;
      next_repetitions := 0;
    elsif quality=2 then
      next_interval := least(normal_interval,greatest(1,t.interval/2));
      next_repetitions := t.repetitions;
    end if;
    select coalesce(array_agg(distinct h order by h),'{}') into covered from unnest(t.seen_holes || hole_ids) h;
    if quality=4 and cardinality(hole_ids)>0 and exists (
      select 1 from study_private.active_targets(p_user) active where active.id=t.id and not (covered @> active.holes)
    ) then next_interval := least(next_interval,6); end if;
    next_ease := greatest(1.3,t.ease_factor+0.1-(5-quality)*(0.08+(5-quality)*0.02));
    update study_private.targets set next_review=a.day+next_interval, interval=next_interval,
      ease_factor=next_ease, repetitions=next_repetitions, seen_holes=covered where id=t.id;
  end if;
  update study_private.assignments d set grades=all_grades, revision=d.revision+1,
    completed_at=case when complete then now() else null end,
    next_review=case when complete then a.day+next_interval else null end
    where d.target_id=a.target_id and d.day=a.day returning d.* into a;
  return to_jsonb(a);
end;
$$;


create table study_private.mutation_receipts (
  user_id uuid not null references public.users(id) on delete cascade,
  operation text not null,
  request_id uuid not null,
  fingerprint text not null,
  response jsonb not null,
  created_at timestamptz not null default now(),
  primary key(user_id,operation,request_id)
);
alter table study_private.mutation_receipts enable row level security;
revoke all on study_private.mutation_receipts from public, anon, authenticated;

create function study_private.scope_owner() returns uuid
language plpgsql stable set search_path = ''
as $$
declare v_owner uuid;
begin
  select i.user_id into v_owner
  from study_private.identities i
  join auth.users a on a.id=i.auth_id
  join study_private.invitations v on v.email=lower(btrim(a.email))
  where i.auth_id=auth.uid();
  if v_owner is null then raise exception 'invitation required' using errcode='42501'; end if;
  return v_owner;
end;
$$;

create function study_private.retry_items(p_owner uuid)
returns table(item jsonb,hole integer,layout jsonb,sort_position integer,ordinality bigint)
language sql stable set search_path = ''
as $$
  select to_jsonb(d)-'layout'-'answer', h.hole, d.layout, d.position, h.ordinality
  from study_private.assignments d
  join study_private.targets t on t.id=d.target_id and t.user_id=d.user_id and t.version=d.version
  join public.cards c on c.id=d.card_id and c.user_id=d.user_id and c.study_archived_at is null
  cross join lateral unnest(study_private.holes(d.layout)) with ordinality h(hole,ordinality)
  where d.user_id=p_owner and d.day=study_private.today() and d.completed_at is not null
    and (d.grades->>h.hole::text)::int in (0,2) and not (h.hole=any(d.retried))
$$;

create function study_private.review_view(p_owner uuid) returns jsonb
language plpgsql set search_path = ''
as $$
declare v_daily jsonb; v_day date:=study_private.today();
begin
  perform pg_advisory_xact_lock(hashtextextended(p_owner::text,739));
  v_daily := study_private.daily(p_owner);
  return (
    select jsonb_build_object(
      'day',v_day,'unassigned',v_daily->'unassigned',
      'total',count(*),'completed',count(*) filter(where d.completed_at is not null),
      'holes',coalesce(sum(cardinality(study_private.holes(d.layout))),0),
      'remaining',coalesce(sum((select count(*) from unnest(study_private.holes(d.layout)) h
        where not (d.grades ? h::text))) filter (where d.completed_at is null),0),
      'current',(select to_jsonb(a) from study_private.assignments a where a.user_id=p_owner
        and a.day=v_day and a.completed_at is null order by a.position limit 1),
      'next_review',(select a.next_review from study_private.assignments a where a.user_id=p_owner
        and a.day=v_day and a.completed_at is not null order by a.completed_at desc limit 1),
      'retry_count',(select count(*) from study_private.retry_items(p_owner)),
      'reviewed_sources',coalesce((select jsonb_agg(jsonb_build_object('id',s.id,'title',s.title) order by s.title,s.id)
        from public.source_cards s where s.user_id=p_owner and s.study_archived_at is null and exists
        (select 1 from study_private.assignments a where a.user_id=p_owner and a.day=v_day
          and a.target_id=s.id and a.completed_at is not null)),'[]'::jsonb))
    from study_private.assignments d where d.user_id=p_owner and d.day=v_day
  );
end;
$$;

create function study_private.filter_has(options jsonb,value text) returns boolean
language sql immutable set search_path = ''
as $$ select coalesce(jsonb_array_length(options),0)=0 or coalesce(options ? value,false) $$;

create function study_private.practice_matches(p_owner uuid, f jsonb, ids uuid[] default null)
returns table(card_id uuid,target_id uuid,weight integer,title text)
language sql stable set search_path = ''
as $$
  with last_grades as (
    select distinct on(d.target_id,g.key) d.target_id,g.key,g.value::integer as grade
    from study_private.assignments d
    join study_private.targets t on t.id=d.target_id and t.user_id=d.user_id and t.version=d.version
    cross join lateral jsonb_each_text(d.grades) g
    where f->>'mode'='weak' and d.user_id=p_owner and d.completed_at is not null
      and d.day>=study_private.today()-29 and (ids is null or d.target_id=any(ids))
      and g.key::int=any(study_private.holes(d.layout))
    order by d.target_id,g.key,d.day desc,d.completed_at desc
  ), candidates as (
    select c.id, coalesce(c.source_id,c.id) as target, c.title, study_private.rank_weight(c.rank) as rank,
      coalesce(t.ease_factor,c.ease_factor,2.5) as ease,
      coalesce(t.repetitions,c.repetitions,0) as repetitions,
      case when f->>'mode'='weak' then (select count(*)::integer from last_grades g
        where g.target_id=coalesce(c.source_id,c.id) and g.grade in (0,2)
          and g.key::int=any(study_private.holes(study_private.layout(c)))) else 0 end as weak
    from public.cards c
    left join public.source_cards s on s.id=c.source_id and s.user_id=c.user_id
    left join study_private.targets t on t.id=coalesce(c.source_id,c.id) and t.user_id=c.user_id
    where c.user_id=p_owner and c.study_archived_at is null
      and (ids is null or coalesce(c.source_id,c.id)=any(ids))
      and (c.source_id is null or s.study_archived_at is null)
      and study_private.filter_has(f->'subjects',coalesce(c.category,'その他'))
      and study_private.filter_has(f->'ranks',coalesce(c.rank,'B'))
      and study_private.filter_has(f->'types',c.card_type)
      and (coalesce(jsonb_array_length(f->'tags'),0)=0
        or (f->'tags') ?| coalesce(s.study_tags,c.study_tags,'{}'))
      and (not coalesce((f->>'favorite')::boolean,false) or coalesce(c.is_favorite,false) or coalesce(s.study_favorite,false))
      and (coalesce(f->>'mode','range')<>'priority' or c.rank in ('A+','A'))
      and (coalesce(btrim(f->>'query'),'')='' or exists(select 1
        from unnest(array[c.title,s.source_text,c.question,c.answer]) text_field
        where strpos(lower(text_field),lower(btrim(f->>'query')))>0))
  )
  select c.id,c.target,c.weak*5+c.rank,c.title
  from candidates c where coalesce(f->>'mode','range')<>'weak' or c.weak>0
    or ((c.ease<2 or (c.ease<2.3 and c.repetitions<2)) and not exists
      (select 1 from last_grades g where g.target_id=c.target))
$$;

create function study_private.practice_options(p_owner uuid) returns jsonb
language sql stable set search_path = ''
as $$
  select jsonb_build_object(
    'tags',coalesce((select jsonb_agg(to_jsonb(x) order by x.category,x.tag) from (
      select distinct coalesce(s.category,'その他') as category, unnest(s.study_tags) as tag
      from public.source_cards s where s.user_id=p_owner and s.study_archived_at is null
      union
      select distinct coalesce(c.category,'その他'),unnest(c.study_tags)
      from public.cards c where c.user_id=p_owner and c.source_id is null and c.study_archived_at is null
    ) x),'[]'::jsonb),
    'presets',coalesce((select jsonb_agg(to_jsonb(p)-'user_id' order by p.name)
      from study_private.presets p where p.user_id=p_owner),'[]'::jsonb))
$$;

create function study_private.practice_page(p_owner uuid,f jsonb,ids uuid[]) returns jsonb
language sql stable set search_path = ''
as $$
  select jsonb_build_object(
    'sources',coalesce((select jsonb_agg(to_jsonb(s)-'user_id') from public.source_cards s
      where s.user_id=p_owner and s.id=any(ids) and s.study_archived_at is null),'[]'::jsonb),
    'cards',coalesce((select jsonb_agg(to_jsonb(c)-'user_id' order by c.title,c.id)
      from study_private.practice_matches(p_owner,f,ids) m join public.cards c on c.id=m.card_id),'[]'::jsonb),
    'targets',coalesce((select jsonb_agg(to_jsonb(t)-'user_id') from study_private.targets t
      where t.user_id=p_owner and t.id=any(ids)),'[]'::jsonb),
    'history',coalesce((select jsonb_agg(to_jsonb(d)-'user_id'-'answer' order by d.day desc,d.completed_at desc)
      from study_private.assignments d where f->>'mode'='weak' and d.user_id=p_owner and d.target_id=any(ids)
        and d.completed_at is not null and d.day>=study_private.today()-29),'[]'::jsonb),
    'presets','[]'::jsonb,'quota',0)
$$;

create function study_private.archives_for(p_owner uuid)
returns table(id uuid,title text,rank text,archived_at timestamptz)
language sql stable set search_path = ''
as $$
  select c.id,c.title,c.rank,c.study_archived_at
  from public.cards c where c.user_id=p_owner and c.study_archived_at is not null
  union all
  select r.id,r.card->>'title',r.card->>'rank',r.archived_at
  from study_private.replaced_cards r where r.user_id=p_owner
$$;

create function study_private.manage_list(p_owner uuid, f jsonb) returns jsonb
language sql stable set search_path = ''
as $$
  with candidates as (
    select s.id,true as source,s.title,s.category,s.card_type,s.study_tags,
      left(s.source_text,40) as caption,
      (select count(*) from public.cards c where c.user_id=s.user_id and c.source_id=s.id and c.study_archived_at is null) as card_count,
      coalesce((select max(study_private.rank_weight(c.rank)) from public.cards c where c.user_id=s.user_id
        and c.source_id=s.id and c.study_archived_at is null),2) as rank_weight,
      s.study_favorite or exists(select 1 from public.cards c where c.user_id=s.user_id and c.source_id=s.id
        and c.study_archived_at is null and c.is_favorite) as favorite
    from public.source_cards s where s.user_id=p_owner and s.study_archived_at is null
      and (coalesce(btrim(f->>'query'),'')='' or exists(select 1 from unnest(array[s.title,s.source_text]||s.study_tags) value
        where strpos(lower(value),lower(btrim(f->>'query')))>0)
        or exists(select 1 from public.cards c where c.user_id=s.user_id and c.source_id=s.id and c.study_archived_at is null
          and (strpos(lower(c.question),lower(btrim(f->>'query')))>0 or strpos(lower(c.answer),lower(btrim(f->>'query')))>0)))
    union all
    select c.id,false,c.title,c.category,c.card_type,c.study_tags,left(c.question,40),1,
      study_private.rank_weight(c.rank),coalesce(c.is_favorite,false)
    from public.cards c where c.user_id=p_owner and c.source_id is null and c.study_archived_at is null
      and (coalesce(btrim(f->>'query'),'')='' or exists(select 1 from unnest(array[c.title,c.question,c.answer]||c.study_tags) value
        where strpos(lower(value),lower(btrim(f->>'query')))>0))
  ), filtered as (
    select c.*,t.next_review,(array['C','B','B+','A','A+'])[c.rank_weight] as rank
    from candidates c left join study_private.targets t on t.id=c.id and t.user_id=p_owner
    where (coalesce(f->>'subject','')='' or coalesce(c.category,'その他')=f->>'subject')
      and (coalesce(f->>'type','')='' or c.card_type=f->>'type')
  ), paged as (
    select * from filtered order by
      case when f->>'sort'='rank' then rank_weight end desc,
      case when f->>'sort'='favorite' then favorite end desc,
      case when f->>'sort'='due' then next_review end asc nulls last,
      coalesce(nullif(title,''),caption),id
    offset greatest(coalesce((f->>'offset')::int,0),0) limit 20
  )
  select jsonb_build_object('total',(select count(*) from filtered),
    'archives',(select count(*) from study_private.archives_for(p_owner)),
    'items',coalesce((select jsonb_agg(to_jsonb(p)) from paged p),'[]'::jsonb))
$$;

create function study_private.stats_view(p_owner uuid) returns jsonb
language sql stable set search_path = ''
as $$
  with recent as (
    select * from study_private.assignments d
    where d.user_id=p_owner and d.completed_at is not null and d.day>=study_private.today()-29
  ), grades as (
    select g.value::integer as grade from recent r cross join lateral jsonb_each_text(r.grades) g
    where g.key::int=any(study_private.holes(r.layout))
  ), weak as (
    select distinct on(m.target_id) m.target_id,m.card_id,m.weight
    from study_private.practice_matches(p_owner,'{"mode":"weak"}') m order by m.target_id,m.weight desc,m.card_id
  )
  select jsonb_build_object(
    'active',(select count(distinct coalesce(c.source_id,c.id)) from public.cards c where c.user_id=p_owner and c.study_archived_at is null),
    'reviewed',(select count(distinct target_id) from recent),
    'due',(select count(*) from study_private.targets t where t.user_id=p_owner and t.next_review<study_private.today()
      and exists (select 1 from public.cards c where c.user_id=p_owner and coalesce(c.source_id,c.id)=t.id and c.study_archived_at is null)),
    'correct',(select count(*) from grades where grade=4),
    'partial',(select count(*) from grades where grade=2),
    'missed',(select count(*) from grades where grade=0),
    'weak',coalesce((select jsonb_agg(to_jsonb(w)) from (
      select c.title,coalesce(c.category,'その他') as category from weak m
      join public.cards c on c.id=m.card_id order by m.weight desc,c.title,c.id limit 10
    ) w),'[]'::jsonb))
$$;

create function study_private.restore_available(p_owner uuid) returns boolean
language sql stable set search_path = ''
as $$
  select not exists(select 1 from public.source_cards where user_id=p_owner)
    and not exists(select 1 from public.cards where user_id=p_owner)
    and not exists(select 1 from public.daily_assignments where user_id=p_owner)
    and not exists(select 1 from study_private.targets where user_id=p_owner)
    and not exists(select 1 from study_private.assignments where user_id=p_owner)
    and not exists(select 1 from study_private.replaced_cards where user_id=p_owner)
    and not exists(select 1 from study_private.presets where user_id=p_owner)
$$;

create function study_private.dispatch_experience(p_action text,p_data jsonb) returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid:=study_private.scope_owner();
  item_id uuid:=nullif(p_data->>'id','')::uuid;
  key uuid:=nullif(p_data->>'request_id','')::uuid;
  payload_hash text;
  saved study_private.mutation_receipts%rowtype;
  result jsonb;
  ids uuid[];
begin
  case p_action
    when 'review_view' then return study_private.review_view(v_owner);
    when 'review_retry' then return (select jsonb_build_object('assignment',r.item,'hole',r.hole,'items',r.layout)
      from study_private.retry_items(v_owner) r order by r.sort_position,r.ordinality limit 1);
    when 'review_source' then return (select to_jsonb(s.source_text) from public.source_cards s
      where s.id=item_id and s.user_id=v_owner and s.study_archived_at is null);
    when 'quota_view' then return (select to_jsonb(coalesce(daily_quota,15)) from public.users where id=v_owner);
    when 'practice_options' then return study_private.practice_options(v_owner);
    when 'practice_search' then return (select coalesce(jsonb_agg(r.target_id order by r.weight desc,r.title,r.target_id),'[]')
      from (select distinct on(m.target_id) m.target_id,m.weight,m.title
        from study_private.practice_matches(v_owner,p_data) m order by m.target_id,m.weight desc,m.title,m.card_id) r);
    when 'practice_page' then
      ids:=array(select value::uuid from jsonb_array_elements_text(p_data->'ids'));
      if cardinality(ids)>20 then raise exception 'practice page too long' using errcode='22023'; end if;
      return study_private.practice_page(v_owner,p_data->'filters',ids);
    when 'manage_list' then return study_private.manage_list(v_owner,p_data);
    when 'manage_detail' then return jsonb_build_object(
      'source',(select to_jsonb(s)-'user_id' from public.source_cards s where s.id=item_id and s.user_id=v_owner and s.study_archived_at is null),
      'cards',coalesce((select jsonb_agg(to_jsonb(c)-'user_id' order by c.id)
        from public.cards c where c.user_id=v_owner and c.study_archived_at is null
          and (c.source_id=item_id or (c.id=item_id and c.source_id is null))),'[]'::jsonb));
    when 'archive_list' then return (select coalesce(jsonb_agg(to_jsonb(a)),'[]') from (
      select * from study_private.archives_for(v_owner) order by archived_at desc,id
      offset greatest(coalesce((p_data->>'offset')::int,0),0) limit 20
    ) a);
    when 'archive_detail' then return coalesce(
      (select to_jsonb(c)-'user_id' from public.cards c where c.id=item_id and c.user_id=v_owner and c.study_archived_at is not null),
      (select r.card-'user_id' from study_private.replaced_cards r where r.id=item_id and r.user_id=v_owner));
    when 'stats_view' then return study_private.stats_view(v_owner);
    when 'restore_available' then return to_jsonb(study_private.restore_available(v_owner));
    when 'csv_cards' then return (select coalesce(jsonb_agg(to_jsonb(c)-'user_id'-'study_layout' order by c.title,c.id),'[]')
      from public.cards c where c.user_id=v_owner and c.study_archived_at is null);
    when 'import_matches' then return (select coalesce(jsonb_agg(distinct jsonb_build_object('question',c.question,'answer',c.answer)),'[]')
      from public.cards c join jsonb_to_recordset(p_data->'cards') input(question text,answer text)
        on c.question=input.question and coalesce(c.answer,'')=coalesce(input.answer,'')
      where c.user_id=v_owner and c.study_archived_at is null);
    else null;
  end case;

  if p_action not in ('save_orphan','source_metadata','archive','legacy_import','restore','favorite','preset','delete_preset') then
    return study_private.dispatch(p_action,p_data);
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_owner::text,739));
  if key is not null then
    payload_hash:=md5(p_data::text);
    select * into saved from study_private.mutation_receipts r
      where r.user_id=v_owner and r.operation=p_action and r.request_id=key;
    if found then
      if saved.fingerprint<>payload_hash then raise exception 'request changed' using errcode='40001'; end if;
      return saved.response;
    end if;
  end if;
  if p_action='restore' and not study_private.restore_available(v_owner) then
    raise exception 'restore requires empty library' using errcode='55000';
  end if;
  if p_action='favorite' and not (
    (coalesce((p_data->>'source')::boolean,false) and exists
      (select 1 from public.source_cards where id=item_id and user_id=v_owner and study_archived_at is null))
    or (not coalesce((p_data->>'source')::boolean,false) and exists
      (select 1 from public.cards where id=item_id and user_id=v_owner and source_id is null and study_archived_at is null))
  ) then raise exception 'card not available' using errcode='40001'; end if;
  if p_action in ('preset','delete_preset') and item_id is not null and not exists
    (select 1 from study_private.presets where id=item_id and user_id=v_owner) then
    raise exception 'preset not available' using errcode='40001';
  end if;
  if p_action='legacy_import' then
    with incoming as (
      select value from jsonb_array_elements(p_data->'cards')
    ), remaining as (
      select value from incoming i where not exists (
        select 1 from public.cards c where c.user_id=v_owner and c.study_archived_at is null
          and c.question=i.value->>'question' and coalesce(c.answer,'')=coalesce(i.value->>'answer','')
      )
    ), source_rows as (
      select s.value from jsonb_array_elements(p_data->'sources') s
      where exists (select 1 from remaining r where r.value->>'source_export_id'=s.value->>'export_id')
        or not exists (select 1 from incoming i where i.value->>'source_export_id'=s.value->>'export_id')
    )
    select p_data || jsonb_build_object(
      'cards',coalesce((select jsonb_agg(value) from remaining),'[]'),
      'sources',coalesce((select jsonb_agg(value) from source_rows),'[]')) into p_data;
  end if;
  result:=study_private.dispatch(p_action,p_data);
  if key is not null then
    delete from study_private.mutation_receipts where user_id=v_owner and created_at<now()-interval '30 days';
    insert into study_private.mutation_receipts(user_id,operation,request_id,fingerprint,response)
      values(v_owner,p_action,key,payload_hash,result);
  end if;
  return result;
end;
$$;

revoke execute on function study_private.scope_owner(), study_private.retry_items(uuid), study_private.review_view(uuid),
  study_private.filter_has(jsonb,text), study_private.practice_matches(uuid,jsonb,uuid[]),
  study_private.practice_options(uuid), study_private.practice_page(uuid,jsonb,uuid[]), study_private.archives_for(uuid),
  study_private.manage_list(uuid,jsonb), study_private.stats_view(uuid), study_private.restore_available(uuid),
  study_private.dispatch_experience(text,jsonb) from public, anon, authenticated;
grant execute on function study_private.dispatch_experience(text,jsonb) to authenticated;

create or replace function public.study_api(p_action text,p_payload jsonb default '{}') returns jsonb
language sql security invoker set search_path = ''
as $$ select study_private.dispatch_experience(p_action,p_payload) $$;
