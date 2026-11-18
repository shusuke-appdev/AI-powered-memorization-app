alter table public.source_cards
  add column study_tags text[] not null default '{}',
  add column study_version uuid not null default gen_random_uuid(),
  add column study_favorite boolean not null default false,
  add column study_archived_at timestamptz;

alter table public.cards
  add column study_tags text[] not null default '{}',
  add column study_version uuid not null default gen_random_uuid(),
  add column study_layout jsonb,
  add column study_archived_at timestamptz,
  add constraint cards_study_layout_array check (jsonb_typeof(study_layout) = 'array');

create table study_private.identities (
  auth_id uuid primary key references auth.users(id) on delete cascade,
  user_id uuid not null unique references public.users(id) on delete cascade
);
create table study_private.invitations (email text primary key check (email = lower(btrim(email))));
create table study_private.targets (
  id uuid primary key,
  user_id uuid not null references public.users(id) on delete cascade,
  version uuid not null default gen_random_uuid(),
  next_review date not null,
  interval integer not null check (interval >= 0),
  ease_factor double precision not null check (ease_factor >= 1.3),
  repetitions integer not null check (repetitions >= 0),
  seen_holes integer[] not null default '{}',
  unique (id, user_id)
);
create index study_targets_due on study_private.targets(user_id, next_review);

create table study_private.assignments (
  target_id uuid not null,
  user_id uuid not null,
  day date not null,
  card_id uuid not null,
  version uuid not null,
  position integer not null check (position >= 0),
  title text not null,
  category text not null,
  card_type text,
  rank text not null,
  layout jsonb not null check (jsonb_typeof(layout) = 'array'),
  answer text not null default '',
  grades jsonb not null default '{}' check (jsonb_typeof(grades) = 'object'),
  revision integer not null default 0,
  completed_at timestamptz,
  next_review date,
  retried integer[] not null default '{}',
  primary key (target_id, day),
  foreign key (target_id, user_id) references study_private.targets(id, user_id) on delete cascade
);
create index study_assignments_date on study_private.assignments(user_id, day desc, position);
create index study_assignments_card on study_private.assignments(card_id, day desc);

create table study_private.presets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null check (length(btrim(name)) between 1 and 100),
  filters jsonb not null check (jsonb_typeof(filters) = 'object'),
  unique (user_id, name)
);
create table study_private.bundle_receipts (
  user_id uuid not null references public.users(id) on delete cascade,
  request_id uuid not null,
  fingerprint text not null,
  response jsonb not null,
  primary key (user_id,request_id)
);

alter table study_private.identities enable row level security;
alter table study_private.invitations enable row level security;
alter table study_private.targets enable row level security;
alter table study_private.assignments enable row level security;
alter table study_private.presets enable row level security;
alter table study_private.bundle_receipts enable row level security;
revoke all on all tables in schema study_private from public, anon, authenticated;
grant usage on schema study_private to authenticated, supabase_auth_admin;

create function study_private.check_invitation(event jsonb) returns jsonb
language sql stable security definer set search_path = ''
as $$
  select case when event->'user'->'app_metadata'->>'provider' = 'google' and exists (
    select 1 from study_private.invitations i
    where i.email = lower(btrim(event->'user'->>'email'))
  ) then '{}'::jsonb else '{"error":{"http_code":403,"message":"Invitation required"}}'::jsonb end
$$;
revoke all on function study_private.check_invitation(jsonb) from public, anon, authenticated;
grant execute on function study_private.check_invitation(jsonb) to supabase_auth_admin;

create function study_private.today() returns date
language sql stable set search_path = ''
as $$ select (now() at time zone 'Asia/Tokyo')::date $$;

create function study_private.layout(c public.cards) returns jsonb
language plpgsql immutable set search_path = ''
as $$
declare
  pieces text[];
  answers text[];
  n integer;
  result jsonb := '[]';
begin
  if c.study_layout is not null then return c.study_layout; end if;
  if c.card_type in ('知識','類型') then return jsonb_build_array(c.question); end if;
  pieces := regexp_split_to_array(c.question, '_{3,}');
  n := cardinality(pieces) - 1;
  answers := case when n = 1 then array[c.answer] else string_to_array(c.answer, ' / ') end;
  if n < 1 or n is distinct from cardinality(answers) or exists (
    select 1 from unnest(answers) x where btrim(x) = ''
  ) then return jsonb_build_array(c.question); end if;
  for i in 1..n loop
    result := result || jsonb_build_array(pieces[i], jsonb_build_object('hole',i,'answer',answers[i]));
  end loop;
  return result || jsonb_build_array(pieces[n+1]);
end;
$$;

create function study_private.holes(p_layout jsonb) returns integer[]
language sql immutable set search_path = ''
as $$
  select coalesce(array_agg((value->>'hole')::int order by ordinality), '{}')
  from jsonb_array_elements(p_layout) with ordinality where jsonb_typeof(value) = 'object'
$$;

create function study_private.assignment_layout(c public.cards) returns jsonb
language sql immutable set search_path = ''
as $$
  select case when c.source_id is not null and c.study_layout is null
    then jsonb_build_array(c.question) else study_private.layout(c) end
$$;

create function study_private.rank_weight(p_rank text) returns integer
language sql immutable set search_path = ''
as $$ select case p_rank when 'A+' then 5 when 'A' then 4 when 'B+' then 3 when 'C' then 1 else 2 end $$;

create function study_private.active_targets(p_user uuid)
returns table(id uuid, rank_weight integer, holes integer[])
language sql stable set search_path = ''
as $$
  select coalesce(c.source_id, c.id), max(study_private.rank_weight(c.rank)),
    coalesce(array_agg(distinct h.id) filter (where h.id is not null), '{}')
  from public.cards c
  left join lateral unnest(study_private.holes(study_private.assignment_layout(c))) h(id) on true
  where c.user_id = p_user and c.study_archived_at is null
  group by coalesce(c.source_id, c.id)
$$;

create function study_private.seed_targets(p_user uuid) returns void
language sql set search_path = ''
as $$
  insert into study_private.targets(id,user_id,next_review,interval,ease_factor,repetitions)
  select distinct on (coalesce(c.source_id,c.id))
    coalesce(c.source_id,c.id), c.user_id, coalesce(c.next_review,study_private.today()),
    coalesce(c.interval,1), coalesce(c.ease_factor,2.5), coalesce(c.repetitions,0)
  from public.cards c where c.user_id = p_user and c.study_archived_at is null
  order by coalesce(c.source_id,c.id), coalesce(c.next_review,study_private.today()), c.id
  on conflict(id) do nothing
$$;

create function study_private.library(p_user uuid) returns jsonb
language sql stable set search_path = ''
as $$
  select jsonb_build_object(
    'sources',coalesce((select jsonb_agg(to_jsonb(s) order by s.title,s.id) from public.source_cards s
      where s.user_id=p_user and s.study_archived_at is null),'[]'),
    'cards',coalesce((select jsonb_agg(card order by card->>'title',card->>'id') from (
      select to_jsonb(c) as card from public.cards c where c.user_id=p_user
      union all
      select r.card || jsonb_build_object('study_archived_at',r.archived_at,'study_tags','[]'::jsonb)
        from study_private.replaced_cards r where r.user_id=p_user
    ) records),'[]'),
    'targets',coalesce((select jsonb_agg(to_jsonb(t)) from study_private.targets t where t.user_id=p_user),'[]'),
    'history',coalesce((select jsonb_agg(to_jsonb(d) order by d.day desc, d.completed_at desc)
      from study_private.assignments d where d.user_id=p_user and d.completed_at is not null
        and d.day >= study_private.today()-29),'[]'),
    'presets',coalesce((select jsonb_agg(to_jsonb(p) order by p.name) from study_private.presets p where p.user_id=p_user),'[]'),
    'quota',coalesce((select daily_quota from public.users where id=p_user),15)
  )
$$;

create function study_private.daily(p_user uuid) returns jsonb
language plpgsql set search_path = ''
as $$
declare
  today date := study_private.today();
  quota integer := coalesce((select u.daily_quota from public.users u where u.id=p_user),15);
  remaining integer;
  start_position integer;
  candidate record;
  chosen public.cards%rowtype;
begin
  perform study_private.seed_targets(p_user);
  delete from study_private.assignments d
  where d.user_id=p_user and d.day=today and d.completed_at is null and not exists (
    select 1 from public.cards c join study_private.targets t on t.id=d.target_id
    where c.user_id=p_user and c.id=d.card_id and c.study_archived_at is null and t.version=d.version
  );

  -- Preserve confirmed work and the active draft when the quota is reduced.
  delete from study_private.assignments d where d.user_id=p_user and d.day=today and d.target_id in (
    select pending.target_id from study_private.assignments pending
    where pending.user_id=p_user and pending.day=today and pending.completed_at is null
      and pending.grades='{}'::jsonb
    order by pending.position
    offset greatest(quota - (select count(*) from study_private.assignments kept
      where kept.user_id=p_user and kept.day=today and (kept.completed_at is not null or kept.grades<>'{}'::jsonb)),0)
  );

  select greatest(quota-count(*),0),coalesce(max(d.position)+1,0)
    into remaining,start_position from study_private.assignments d where d.user_id=p_user and d.day=today;
  for candidate in
    select t.*, active.rank_weight from study_private.targets t
    join study_private.active_targets(p_user) active on active.id=t.id
    where t.user_id=p_user and t.next_review<=today and not exists (
      select 1 from study_private.assignments d where d.target_id=t.id and d.day=today
    )
    order by case when t.next_review <= today-7 then t.next_review end asc nulls last,
      active.rank_weight desc,t.next_review,t.ease_factor,t.id
    limit remaining
  loop
    select c.* into chosen from public.cards c
    where c.user_id=p_user and coalesce(c.source_id,c.id)=candidate.id and c.study_archived_at is null
    order by (
      select count(*) from unnest(study_private.holes(study_private.assignment_layout(c))) h
      where h <> all(candidate.seen_holes)
    ) desc,
    (select max(d.day) from study_private.assignments d
      where d.card_id=c.id and d.user_id=p_user and d.completed_at is not null) asc nulls first,
    c.id limit 1;
    insert into study_private.assignments(
      user_id,target_id,day,card_id,version,position,title,category,card_type,rank,layout,answer
    ) values (
      p_user,candidate.id,today,chosen.id,candidate.version,start_position,coalesce(chosen.title,''),
      coalesce(chosen.category,'その他'),chosen.card_type,
      (array['C','B','B+','A','A+'])[candidate.rank_weight],
      study_private.assignment_layout(chosen),case when chosen.card_type in ('知識','類型') then '' else chosen.answer end
    );
    start_position := start_position+1;
  end loop;
  return jsonb_build_object(
    'day',today,
    'assignments',coalesce((select jsonb_agg(to_jsonb(d) order by d.position)
      from study_private.assignments d where d.user_id=p_user and d.day=today),'[]'),
    'unassigned',(select count(*) from study_private.targets t join study_private.active_targets(p_user) active on active.id=t.id
      where t.user_id=p_user and t.next_review<=today and not exists (
        select 1 from study_private.assignments d where d.target_id=t.id and d.day=today
      ))
  );
end;
$$;

create function study_private.evaluate(p_user uuid,p_data jsonb) returns jsonb
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
  if a.completed_at is not null then return to_jsonb(a); end if;
  if a.day<>study_private.today() then raise exception 'day changed' using errcode='40001'; end if;
  select t0.* into t from study_private.targets t0 where t0.id=a.target_id and t0.user_id=p_user for update;
  if t.version is distinct from a.version then raise exception 'card changed' using errcode='40001'; end if;
  hole_ids := study_private.holes(a.layout);
  valid_keys := case when cardinality(hole_ids)=0 then array['0'] else hole_ids::text[] end;
  if jsonb_typeof(changes) is distinct from 'object' or exists (
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

create function study_private.relearn(p_user uuid,p_data jsonb) returns jsonb
language plpgsql set search_path = ''
as $$
declare a study_private.assignments%rowtype;
begin
  update study_private.assignments d set retried=(
    select array_agg(distinct h order by h) from unnest(d.retried || array[(p_data->>'hole')::int]) h
  ) from study_private.targets t
  where d.user_id=p_user and d.day=study_private.today() and d.day=(p_data->>'day')::date
    and d.target_id=(p_data->>'target_id')::uuid and d.completed_at is not null
    and d.version=(p_data->>'version')::uuid and t.id=d.target_id and t.version=d.version
    and (d.grades->>(p_data->>'hole'))::int in (0,2)
    and (p_data->>'hole')::int=any(study_private.holes(d.layout))
  returning d.* into a;
  if not found then raise exception 'assignment changed' using errcode='40001'; end if;
  return to_jsonb(a);
end;
$$;

create function study_private.save_bundle(p_user uuid,p_data jsonb,p_migrating boolean default false)
returns jsonb language plpgsql set search_path = ''
as $$
declare
  sid uuid := nullif(p_data->>'id','')::uuid;
  prev public.source_cards%rowtype;
  src text := btrim(p_data->>'source_text');
  v_title text := btrim(coalesce(p_data->>'title',''));
  v_category text := p_data->>'category';
  kind text := p_data->>'card_type';
  v_rank text := p_data->>'rank';
  topics text[] := array(select jsonb_array_elements_text(coalesce(p_data->'tags','[]')));
  item jsonb;
  layout jsonb;
  slot_ids integer[];
  q text;
  a text;
  matched public.cards%rowtype;
  saved uuid;
  kept uuid[] := '{}';
  kept_existing integer := 0;
  archived integer := 0;
  favorite boolean := false;
  learning_changed boolean;
begin
  if coalesce(src,'')='' or not coalesce(kind in ('知識','類型','規範','判例'),false)
    or not coalesce(v_category in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他'),false)
    or not coalesce(v_rank in ('A+','A','B+','B','C'),false)
    or jsonb_typeof(p_data->'variants') is distinct from 'array'
    or jsonb_array_length(p_data->'variants') not between 1 and 5 then
    raise exception 'invalid bundle' using errcode='22023';
  end if;
  if sid is null then
    insert into public.source_cards(user_id,source_text,title,category,card_type,study_tags)
    values(p_user,src,v_title,v_category,kind,topics) returning id into sid;
    learning_changed := true;
  else
    select s.* into prev from public.source_cards s where s.id=sid and s.user_id=p_user
      and s.study_archived_at is null for update;
    if not found or prev.study_version is distinct from (p_data->>'version')::uuid
      or (p_migrating and p_data->>'expected_text' is distinct from prev.source_text) then
      raise exception 'source changed' using errcode='40001';
    end if;
    select prev.study_favorite or coalesce(bool_or(c.is_favorite),false) into favorite
      from public.cards c where c.source_id=sid and c.user_id=p_user;
    learning_changed := prev.source_text is distinct from src or prev.card_type is distinct from kind;
    update public.source_cards s set source_text=src,title=v_title,category=v_category,
      card_type=kind,study_tags=topics,study_favorite=favorite,study_version=gen_random_uuid()
      where s.id=sid and s.user_id=p_user;
  end if;

  for item in select value from jsonb_array_elements(p_data->'variants') loop
    layout := item->'layout';
    if jsonb_typeof(layout) is distinct from 'array' or exists (
      select 1 from jsonb_array_elements(layout) part where jsonb_typeof(part) not in ('string','object')
        or jsonb_typeof(part)='object' and (
          jsonb_typeof(part->'hole') is distinct from 'number' or (part->>'hole')::int<1
          or jsonb_typeof(part->'answer') is distinct from 'string' or btrim(part->>'answer')=''
        )
    ) then raise exception 'invalid cloze' using errcode='22023'; end if;
    slot_ids := study_private.holes(layout);
    select string_agg(case when jsonb_typeof(part)='object' then '______' else part#>>'{}' end,'' order by n),
      coalesce(string_agg(part->>'answer',' / ' order by n),'')
      into q,a from jsonb_array_elements(layout) with ordinality x(part,n);
    if coalesce(btrim(q),'')='' or ((kind in ('知識','類型'))<>(cardinality(slot_ids)=0))
      or cardinality(slot_ids)<>(select count(distinct h) from unnest(slot_ids) h) then
      raise exception 'invalid cloze' using errcode='22023';
    end if;
    select c.* into matched from public.cards c
    where c.user_id=p_user and c.source_id=sid and c.study_archived_at is null and c.id<>all(kept)
      and c.question=q and c.answer=a and c.card_type=kind and (
        c.study_layout=layout or (c.study_layout is null and
          cardinality(study_private.holes(study_private.layout(c)))=cardinality(slot_ids))
      )
    order by c.id limit 1;
    if not found then
      insert into public.cards(user_id,source_id,title,category,card_type,rank,question,answer,
        blank_count,highlighted_keywords,study_layout,next_review)
      values(p_user,sid,v_title,v_category,kind,v_rank,q,a,cardinality(slot_ids),'',layout,study_private.today())
      returning id into saved;
    else
      update public.cards c set title=v_title,category=v_category,rank=v_rank,
        blank_count=cardinality(slot_ids),study_layout=layout
        where c.id=matched.id and c.user_id=p_user;
      saved := matched.id;
      kept_existing := kept_existing+1;
    end if;
    kept := array_append(kept,saved);
  end loop;
  update public.cards c set study_archived_at=now()
  where c.user_id=p_user and c.source_id=sid and c.study_archived_at is null and c.id<>all(kept);
  get diagnostics archived = row_count;
  if learning_changed or archived>0 or kept_existing<cardinality(kept) then
    update study_private.targets t set version=gen_random_uuid(),seen_holes='{}',
      next_review=case when learning_changed and not p_migrating
        then least(t.next_review,study_private.today()) else t.next_review end
    where t.id=sid and t.user_id=p_user;
    delete from study_private.assignments where target_id=sid and user_id=p_user and completed_at is null;
  end if;
  perform study_private.seed_targets(p_user);
  return jsonb_build_object('id',sid,'kept',kept_existing,'new',cardinality(kept)-kept_existing,'archived',archived);
end;
$$;

create function study_private.save_orphan(p_user uuid,p_data jsonb) returns jsonb
language plpgsql set search_path = ''
as $$
declare
  cid uuid := (p_data->>'id')::uuid;
  old public.cards%rowtype;
  kind text := p_data->>'card_type';
  q text := btrim(p_data->>'question');
  a text := case when kind in ('知識','類型') then '' else btrim(p_data->>'answer') end;
  changed boolean;
begin
  select c.* into old from public.cards c where c.user_id=p_user and c.id=cid and c.source_id is null
    and c.study_archived_at is null for update;
  if not found or old.study_version is distinct from (p_data->>'version')::uuid then
    raise exception 'card changed' using errcode='40001';
  end if;
  if not coalesce(kind in ('知識','類型','規範','判例'),false)
    or not coalesce(p_data->>'category' in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他'),false)
    or not coalesce(p_data->>'rank' in ('A+','A','B+','B','C'),false)
    or coalesce(q,'')='' or (kind not in ('知識','類型') and coalesce(a,'')='') then
    raise exception 'invalid card' using errcode='22023';
  end if;
  changed := old.question is distinct from q or old.answer is distinct from a or old.card_type is distinct from kind;
  update public.cards c set title=btrim(coalesce(p_data->>'title','')),category=p_data->>'category',
    rank=p_data->>'rank',card_type=kind,question=q,answer=a,
    blank_count=case when kind in ('知識','類型') then 0
      else greatest(1,cardinality(regexp_split_to_array(q,'_{3,}'))-1) end,
    study_layout=case when changed then null else old.study_layout end,
    study_tags=array(select jsonb_array_elements_text(coalesce(p_data->'tags','[]'))),
    study_version=gen_random_uuid()
    where c.id=cid and c.user_id=p_user;
  if changed then
    update study_private.targets t set version=gen_random_uuid(),seen_holes='{}',
      next_review=least(t.next_review,study_private.today()) where t.id=cid and t.user_id=p_user;
    delete from study_private.assignments where target_id=cid and user_id=p_user and completed_at is null;
  end if;
  return jsonb_build_object('id',cid);
end;
$$;

create function study_private.backup(p_user uuid) returns jsonb
language sql stable set search_path = ''
as $$
  select jsonb_build_object(
    'version','3.0',
    'sources',coalesce((select jsonb_agg(to_jsonb(s)-'user_id' order by s.id) from public.source_cards s where s.user_id=p_user),'[]'),
    'cards',coalesce((select jsonb_agg(to_jsonb(c)-'user_id' order by c.id) from public.cards c where c.user_id=p_user),'[]'),
    'targets',coalesce((select jsonb_agg(to_jsonb(t)-'user_id' order by t.id) from study_private.targets t where t.user_id=p_user),'[]'),
    'assignments',coalesce((select jsonb_agg(to_jsonb(d)-'user_id' order by d.day,d.target_id) from study_private.assignments d where d.user_id=p_user),'[]'),
    'legacy_assignments',coalesce((select jsonb_agg(to_jsonb(d)-'user_id' order by d.id) from public.daily_assignments d where d.user_id=p_user),'[]'),
    'replaced_cards',coalesce((select jsonb_agg(to_jsonb(c)-'user_id' order by c.id) from study_private.replaced_cards c where c.user_id=p_user),'[]'),
    'presets',coalesce((select jsonb_agg(to_jsonb(p)-'user_id' order by p.id) from study_private.presets p where p.user_id=p_user),'[]'),
    'quota',coalesce((select daily_quota from public.users where id=p_user),15)
  )
$$;

create function study_private.restore(p_user uuid,p_data jsonb) returns jsonb
language plpgsql set search_path = ''
as $$
begin
  if p_data->>'version' is distinct from '3.0' or jsonb_typeof(p_data->'sources') is distinct from 'array'
    or jsonb_typeof(p_data->'cards') is distinct from 'array'
    or jsonb_typeof(p_data->'targets') is distinct from 'array'
    or jsonb_typeof(p_data->'assignments') is distinct from 'array'
    or jsonb_typeof(p_data->'legacy_assignments') is distinct from 'array'
    or jsonb_typeof(p_data->'replaced_cards') is distinct from 'array'
    or jsonb_typeof(p_data->'presets') is distinct from 'array' then
    raise exception 'invalid backup' using errcode='22023';
  end if;
  if exists(select 1 from public.source_cards where user_id=p_user)
    or exists(select 1 from public.cards where user_id=p_user)
    or exists(select 1 from study_private.targets where user_id=p_user)
    or exists(select 1 from study_private.presets where user_id=p_user) then
    raise exception 'restore requires empty library' using errcode='55000';
  end if;

  insert into public.source_cards select (jsonb_populate_record(null::public.source_cards,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'sources');
  insert into public.cards select (jsonb_populate_record(null::public.cards,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'cards');
  insert into study_private.targets select (jsonb_populate_record(null::study_private.targets,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'targets');
  insert into study_private.assignments select (jsonb_populate_record(null::study_private.assignments,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'assignments');
  insert into public.daily_assignments select (jsonb_populate_record(null::public.daily_assignments,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'legacy_assignments');
  insert into study_private.replaced_cards select (jsonb_populate_record(null::study_private.replaced_cards,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'replaced_cards');
  insert into study_private.presets select (jsonb_populate_record(null::study_private.presets,
    value || jsonb_build_object('user_id',p_user))).* from jsonb_array_elements(p_data->'presets');
  update public.users set daily_quota=(p_data->>'quota')::int where id=p_user;
  return jsonb_build_object('cards',jsonb_array_length(p_data->'cards'));
end;
$$;

create function study_private.dispatch(p_action text,p_data jsonb) returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  owner_id uuid;
  item_id uuid := nullif(p_data->>'id','')::uuid;
  v_request_id uuid := nullif(p_data->>'request_id','')::uuid;
  bundle_key text;
  result jsonb;
begin
  select i.user_id into owner_id from study_private.identities i
    join auth.users a on a.id=i.auth_id
    join study_private.invitations v on v.email=lower(btrim(a.email))
    where i.auth_id=auth.uid();
  if owner_id is null then raise exception 'invitation required' using errcode='42501'; end if;
  if p_action='library' then return study_private.library(owner_id); end if;
  if p_action='backup' then return study_private.backup(owner_id); end if;
  if p_action='card_history' then
    return jsonb_build_object(
      'recent',coalesce((select jsonb_agg(jsonb_build_object('day',d.day,'grades',d.grades) order by d.day desc)
        from study_private.assignments d where d.card_id=item_id and d.user_id=owner_id and d.completed_at is not null),'[]'),
      'legacy',coalesce((select r.assignments from study_private.replaced_cards r
        where r.id=item_id and r.user_id=owner_id),
        (select jsonb_agg(jsonb_build_object('assignment_date',d.assignment_date,'quality',d.quality) order by d.assignment_date desc)
          from public.daily_assignments d where d.card_id=item_id and d.user_id=owner_id and d.completed_at is not null),'[]')
    );
  end if;

  perform pg_advisory_xact_lock(hashtextextended(owner_id::text,739));
  case p_action
    when 'daily' then return study_private.daily(owner_id);
    when 'evaluate' then return study_private.evaluate(owner_id,p_data);
    when 'relearn' then return study_private.relearn(owner_id,p_data);
    when 'save_bundle' then
      if v_request_id is null then return study_private.save_bundle(owner_id,p_data); end if;
      select b.fingerprint,b.response into bundle_key,result from study_private.bundle_receipts b
        where b.user_id=owner_id and b.request_id=v_request_id;
      if found then
        if bundle_key<>md5(p_data::text) then raise exception 'save already applied' using errcode='40001'; end if;
        return result;
      end if;
      result := study_private.save_bundle(owner_id,p_data);
      insert into study_private.bundle_receipts(user_id,request_id,fingerprint,response)
        values(owner_id,v_request_id,md5(p_data::text),result);
      return result;
    when 'save_orphan' then return study_private.save_orphan(owner_id,p_data);
    when 'source_metadata' then
      if not coalesce(p_data->>'category' in ('民法','商法','刑法','憲法','行政法','民事訴訟法','刑事訴訟法','その他'),false)
        or not coalesce(p_data->>'rank' in ('A+','A','B+','B','C'),false) then
        raise exception 'invalid metadata' using errcode='22023';
      end if;
      update public.source_cards set title=btrim(coalesce(p_data->>'title','')),category=p_data->>'category',
        study_tags=array(select jsonb_array_elements_text(coalesce(p_data->'tags','[]'))),study_version=gen_random_uuid()
        where id=item_id and user_id=owner_id and study_version=(p_data->>'version')::uuid and study_archived_at is null;
      if not found then raise exception 'source changed' using errcode='40001'; end if;
      update public.cards set title=btrim(coalesce(p_data->>'title','')),category=p_data->>'category',rank=p_data->>'rank'
        where source_id=item_id and user_id=owner_id and study_archived_at is null;
    when 'restore' then return study_private.restore(owner_id,p_data);
    when 'legacy_import' then
      select to_jsonb(r) into result from public.import_backup_atomic(owner_id,p_data->'sources',p_data->'cards',false) r;
      perform study_private.seed_targets(owner_id);
      return result;
    when 'quota' then
      update public.users set daily_quota=(p_data->>'quota')::int where id=owner_id;
    when 'favorite' then
      if (p_data->>'source')::boolean then
        update public.source_cards set study_favorite=(p_data->>'favorite')::boolean
          where id=item_id and user_id=owner_id and study_archived_at is null;
        update public.cards set is_favorite=(p_data->>'favorite')::boolean
          where source_id=item_id and user_id=owner_id and study_archived_at is null;
      else
        update public.cards set is_favorite=(p_data->>'favorite')::boolean
          where id=item_id and user_id=owner_id and source_id is null and study_archived_at is null;
      end if;
    when 'archive' then
      if (p_data->>'source')::boolean then
        update public.source_cards set study_archived_at=now()
          where id=item_id and user_id=owner_id and study_version=(p_data->>'version')::uuid
            and study_archived_at is null;
        if not found then raise exception 'source changed' using errcode='40001'; end if;
        update public.cards set study_archived_at=now()
          where source_id=item_id and user_id=owner_id and study_archived_at is null;
      else
        update public.cards set study_archived_at=now()
          where id=item_id and user_id=owner_id and source_id is null and study_version=(p_data->>'version')::uuid
            and study_archived_at is null;
        if not found then raise exception 'card changed' using errcode='40001'; end if;
      end if;
      update study_private.targets set version=gen_random_uuid() where id=item_id and user_id=owner_id;
      delete from study_private.assignments where target_id=item_id and user_id=owner_id and completed_at is null;
    when 'preset' then
      if item_id is null then
        insert into study_private.presets(user_id,name,filters) values(owner_id,btrim(p_data->>'name'),p_data->'filters')
        on conflict(user_id,name) do update set filters=excluded.filters;
      else
        update study_private.presets set name=btrim(p_data->>'name'),filters=p_data->'filters'
          where id=item_id and user_id=owner_id;
      end if;
    when 'delete_preset' then
      delete from study_private.presets where id=item_id and user_id=owner_id;
    else raise exception 'unknown operation' using errcode='22023';
  end case;
  return '{"ok":true}'::jsonb;
end;
$$;

create function public.study_api(p_action text,p_payload jsonb default '{}') returns jsonb
language sql security invoker set search_path = ''
as $$ select study_private.dispatch(p_action,p_payload) $$;

revoke execute on all functions in schema study_private from public, anon, authenticated;
grant execute on function study_private.dispatch(text,jsonb) to authenticated;
revoke execute on function public.study_api(text,jsonb) from public, anon, service_role;
grant execute on function public.study_api(text,jsonb) to authenticated;

create table study_private.migration_runs (
  user_id uuid not null references public.users(id) on delete cascade,
  migration_id text not null,
  result jsonb not null,
  primary key (user_id,migration_id)
);
alter table study_private.migration_runs enable row level security;
revoke all on study_private.migration_runs from public, anon, authenticated;

create function public.study_migration_snapshot(p_user uuid) returns jsonb
language sql stable security definer set search_path = ''
as $$ select study_private.backup(p_user) $$;

create function public.study_apply_regeneration(p_user uuid,p_plan jsonb) returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  run_id text := p_plan->>'migration_id';
  bundle jsonb;
  offsets jsonb;
  report jsonb;
  changes jsonb := '[]';
  snap jsonb;
begin
  if not coalesce(run_id ~ '^[a-f0-9]{64}$',false) or jsonb_typeof(p_plan->'bundles') is distinct from 'array'
    or jsonb_typeof(p_plan->'exceptions') is distinct from 'array' then
    raise exception 'invalid migration plan' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_user::text,739));
  select r.result into report from study_private.migration_runs r where r.user_id=p_user and r.migration_id=run_id;
  if found then return report; end if;
  if exists(select 1 from study_private.migration_runs r where r.user_id=p_user) then
    raise exception 'migration already completed' using errcode='55000';
  end if;
  snap := study_private.backup(p_user);
  if snap is distinct from p_plan->'snapshot' then
    raise exception 'migration snapshot changed' using errcode='40001';
  end if;
  select jsonb_agg(id order by id) into offsets from (
    select value->>'id' as id from jsonb_array_elements((p_plan->'bundles') || (p_plan->'exceptions'))
  ) listed;
  if coalesce(offsets,'[]') is distinct from (
    select coalesce(jsonb_agg(s.id::text order by s.id),'[]') from public.source_cards s
    where s.user_id=p_user and s.study_archived_at is null
  ) then raise exception 'migration source list changed' using errcode='40001'; end if;

  perform study_private.seed_targets(p_user);
  -- Snapshot a single completion per original/day without assigning fake hole grades.
  insert into study_private.assignments(
    target_id,user_id,day,card_id,version,position,title,category,card_type,rank,layout,answer,
    grades,completed_at,next_review
  )
  select distinct on(coalesce(c.source_id,c.id),d.assignment_date)
    coalesce(c.source_id,c.id),p_user,d.assignment_date,c.id,t.version,d.position,
    coalesce(c.title,''),coalesce(c.category,'その他'),c.card_type,coalesce(c.rank,'B'),
    study_private.layout(c),c.answer,case when d.quality is null then '{}'::jsonb
      else jsonb_build_object('0',d.quality) end,d.completed_at,t.next_review
  from public.daily_assignments d join public.cards c on c.id=d.card_id and c.user_id=d.user_id
    join study_private.targets t on t.id=coalesce(c.source_id,c.id) and t.user_id=c.user_id
  where d.user_id=p_user and d.completed_at is not null
  order by coalesce(c.source_id,c.id),d.assignment_date,d.completed_at,d.position,c.id
  on conflict(target_id,day) do nothing;

  -- A card replaced on the legacy screen can still account for today's original.
  insert into study_private.assignments(
    target_id,user_id,day,card_id,version,position,title,category,card_type,rank,layout,answer,
    grades,completed_at,next_review
  )
  select t.id,p_user,x.assignment_date,r.id,t.version,x.position,
    coalesce(r.card->>'title',''),coalesce(r.card->>'category','その他'),r.card->>'card_type',
    coalesce(r.card->>'rank','B'),jsonb_build_array(r.card->>'question'),coalesce(r.card->>'answer',''),
    case when x.quality is null then '{}'::jsonb else jsonb_build_object('0',x.quality) end,
    x.completed_at,t.next_review
  from study_private.replaced_cards r join study_private.targets t on t.id=r.source_id and t.user_id=r.user_id
    cross join lateral jsonb_populate_recordset(null::public.daily_assignments,r.assignments) x
  where r.user_id=p_user and x.completed_at is not null
  order by x.completed_at,x.position,r.id
  on conflict(target_id,day) do nothing;

  for bundle in select value from jsonb_array_elements(p_plan->'bundles') loop
    changes := changes || jsonb_build_array(study_private.save_bundle(p_user,bundle,true));
  end loop;
  report := jsonb_build_object('changes',changes,'exceptions',p_plan->'exceptions');
  insert into study_private.migration_runs(user_id,migration_id,result) values(p_user,run_id,report);
  return report;
end;
$$;

revoke execute on function public.study_migration_snapshot(uuid), public.study_apply_regeneration(uuid,jsonb)
from public, anon, authenticated;
grant execute on function public.study_migration_snapshot(uuid), public.study_apply_regeneration(uuid,jsonb)
to service_role;
