import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {PGlite} from '@electric-sql/pglite';
import {generate, holes} from '../src/cards.ts';
import type {Assignment, Daily, Library} from '../src/cards.ts';
import {prepareMigration} from '../scripts/prepare-migration.ts';

const root = new URL('../../supabase/',import.meta.url);
const owner = '00000000-0000-4000-8000-000000000001';
const signedIn = '00000000-0000-4000-8000-000000000002';
const otherOwner = '00000000-0000-4000-8000-000000000003';
const otherAuth = '00000000-0000-4000-8000-000000000004';
const sourceId = '00000000-0000-4000-8000-000000000005';
const oldA = '00000000-0000-4000-8000-000000000006';
const oldB = '00000000-0000-4000-8000-000000000007';

async function schema() {
  const db = await PGlite.create();
  await db.exec(`
    create role service_role bypassrls;
    create role anon;
    create role authenticated;
    create role supabase_auth_admin;
    create schema auth;
    create table auth.users(id uuid primary key, email text);
    create function auth.uid() returns uuid language sql as $$
      select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
    $$;
  `);
  for (const name of ['users','source_cards','cards','daily_assignments']) {
    await db.exec(await readFile(new URL(`database/schemas/public/tables/${name}.sql`,root),'utf8'));
  }
  for (const name of [
    '20260923085046_preserve_review_progress_and_restore_source_only',
    '20261116071017_guarded_source_regeneration',
    '20261116071044_web_study_workspace',
    '20261119025151_study_experience',
    '20261119030016_study_active_target_index',
  ]) {
    try {
      await db.exec(await readFile(new URL(`migrations/${name}.sql`,root),'utf8'));
    } catch (cause) {
      throw new Error(`Failed loading ${name}`,{cause});
    }
  }
  await db.exec(`
    insert into public.users(id,username,password_hash,daily_quota) values
      ('${owner}','test-owner','',1),('${otherOwner}','second-user','',15);
    insert into auth.users values ('${signedIn}','owner@example.test'),('${otherAuth}','other@example.test');
    insert into study_private.invitations values ('owner@example.test'),('other@example.test');
    insert into study_private.identities values ('${signedIn}','${owner}'),('${otherAuth}','${otherOwner}');
  `);
  return db;
}

async function asUser<T>(db: PGlite, user: string, action: string, payload: object = {}): Promise<T> {
  return db.transaction(async tx => {
    await tx.exec('set local role authenticated');
    await tx.query("select set_config('request.jwt.claim.sub',$1,true)",[user]);
    const result = await tx.query<{value:T}>('select public.study_api($1,$2::jsonb) as value',[action,payload]);
    return result.rows[0].value;
  });
}

test('compact reads, progress, and idempotent import respect ownership', async () => {
  const db = await schema();
  try {
    const payload = {
      request_id:'00000000-0000-4000-8000-000000000072',sources:[],
      cards:[{question:'架空の単独カード',answer:'',card_type:'知識',category:'民法',rank:'A+',blank_count:0}],
    };
    const imported = await asUser(db,signedIn,'legacy_import',payload);
    assert.deepEqual(await asUser(db,signedIn,'legacy_import',payload),imported);
    assert.equal((await asUser<Library>(db,signedIn,'library')).cards.length,1);
    assert.equal((await asUser<Library>(db,otherAuth,'library')).cards.length,0);
    assert.equal(await asUser(db,signedIn,'restore_available'),false);
    assert.equal(await asUser(db,otherAuth,'restore_available'),true);
    await assert.rejects(asUser(db,signedIn,'favorite',{id:oldA,source:true,favorite:true}),{code:'40001'});

    const created = await asUser<{id:string}>(db,signedIn,'save_bundle',{
      title:'規範',source_text:'【甲】【乙】【丙】',rank:'A+',category:'民法',card_type:'規範',
      tags:['債権'],variants:generate('【甲】【乙】【丙】','規範'),
    });
    const range = {mode:'range',tags:['債権'],ranks:['A+'],subjects:['民法']};
    assert.deepEqual(await asUser(db,signedIn,'practice_search',range),[created.id]);
    assert.deepEqual(await asUser(db,otherAuth,'practice_search',range),[]);
    const page = await asUser<Library>(db,signedIn,'practice_page',{filters:range,ids:[created.id]});
    assert.equal(page.sources.length,1);
    assert(page.cards.length>0);
    assert.equal((await asUser<Library>(db,otherAuth,'practice_page',{filters:range,ids:[created.id]})).cards.length,0);
    assert.equal((await asUser<{total:number}>(db,signedIn,'manage_list',{query:'架空の単独'})).total,1);
    assert.equal((await asUser<{active:number}>(db,signedIn,'stats_view')).active,2);
    assert.equal((await asUser<{source:unknown}>(db,otherAuth,'manage_detail',{id:created.id})).source,null);
    const view = await asUser<{total:number;current:Assignment;holes:number}>(db,signedIn,'review_view');
    assert.equal(view.total,1);
    assert(view.current.card_id);
    assert(view.holes>=0);
  } finally {
    await db.close();
  }
});

test('production-sized synthetic library remains compact at the normal entry points', async () => {
  const db = await schema();
  try {
    const seed = (await readFile(new URL('./fixtures/performance.sql',import.meta.url),'utf8'))
      .replaceAll(":'owner'",`'${owner}'`);
    await db.exec(seed);
    await db.exec('analyze public.cards; analyze public.source_cards');
    const initial = await asUser<Library>(db,signedIn,'library');
    assert.equal(initial.sources.length,545);
    assert.equal(initial.cards.length,2727);
    assert.equal(initial.cards.filter(card => !card.study_archived_at).length,1631);
    const filters = {mode:'range',subjects:['民法']};
    const review = await asUser<{current:Assignment}>(db,signedIn,'review_view');
    const options = await asUser(db,signedIn,'practice_options');
    const ids = await asUser<string[]>(db,signedIn,'practice_search',filters);
    assert.equal(ids.length,545);
    const bytes = (value:unknown) => Buffer.byteLength(JSON.stringify(value),'utf8');
    const sizes = {legacy:bytes(initial),review:bytes(review),practice:bytes(options)+bytes(ids)};
    assert(sizes.legacy>5_000_000);
    assert(sizes.review<=600_000 && sizes.practice<=600_000);
    const first = await asUser<Library>(db,signedIn,'practice_page',{filters,ids:ids.slice(0,20)});
    const second = await asUser<Library>(db,signedIn,'practice_page',{filters,ids:ids.slice(20,40)});
    assert.equal(first.sources.length,20);
    assert.equal(second.sources.length,20);
    assert(first.cards.every(card => ids.slice(0,20).includes(card.source_id!)));
    assert(second.cards.every(card => ids.slice(20,40).includes(card.source_id!)));
    assert.deepEqual(await asUser(db,otherAuth,'practice_search',filters),[]);
    console.log('Synthetic initial JSON bytes',sizes);
  } finally {
    await db.close();
  }
});

function evaluate(item: Assignment, grades: Assignment['grades'], finish: boolean) {
  return {target_id:item.target_id,card_id:item.card_id,version:item.version,day:item.day,
    revision:item.revision,grades,finish};
}

test('Tokyo midnight rejects old unfinished work but preserves an acknowledged final retry', async () => {
  const db = await schema();
  try {
    const make = (title:string) => asUser<{id:string}>(db,signedIn,'save_bundle',{
      title,source_text:'【目的】を示す。',rank:'A',category:'民法',card_type:'規範',
      variants:generate('【目的】を示す。','規範'),
    });
    await make('確定用');
    await make('未完了用');
    await asUser(db,signedIn,'quota',{quota:2});
    const [first,pending] = (await asUser<Daily>(db,signedIn,'daily')).assignments;
    const request = evaluate(first,{1:4},true);
    const finished = await asUser<Assignment>(db,signedIn,'evaluate',request);
    await db.exec(`create or replace function study_private.today() returns date
      language sql stable set search_path='' as $$ select ((now() at time zone 'Asia/Tokyo')::date+1) $$`);
    assert.deepEqual(await asUser(db,signedIn,'evaluate',request),finished);
    await assert.rejects(asUser(db,signedIn,'evaluate',evaluate(pending,{1:4},true)),{code:'40001'});
    const tomorrow = await asUser<Daily>(db,signedIn,'daily');
    assert.notEqual(tomorrow.day,first.day);
    assert(tomorrow.assignments.every(item => item.day===tomorrow.day && !item.completed_at));
  } finally {
    await db.close();
  }
});

test('local preflight backup round-trips in an isolated database',{skip:!process.env.STUDY_BACKUP_AUDIT},async () => {
  const snapshot = JSON.parse(await readFile(process.env.STUDY_BACKUP_AUDIT!,'utf8'));
  assert(Array.isArray(snapshot.snapshots) && snapshot.snapshots.length>0,'No owner backups');
  for (const row of snapshot.snapshots) {
    const target = await schema();
    try {
      const normalized = await target.query<{value:unknown}>('select $1::jsonb as value',[row.backup]);
      await asUser(target,signedIn,'restore',row.backup);
      const restored = await asUser<Record<string,unknown[]>>(target,signedIn,'backup');
      assert(JSON.stringify(restored)===JSON.stringify(normalized.rows[0].value),'Backup or restored content differs');
      console.log('Restored snapshot counts',Object.fromEntries(
        ['sources','cards','targets','assignments','legacy_assignments','replaced_cards','presets']
          .map(name => [name,restored[name].length]),
      ));
    } catch (cause) {
      // Keep card contents and real identifiers out of test output.
      const code = (cause as {code?:string}).code;
      throw new Error(`Isolated backup check failed${code ? ` (${code})` : ''}`);
    } finally {
      await target.close();
    }
  }
});

test('guarded replacement, owner isolation, source assignment, retries and restore', async () => {
  const db = await schema();
  try {
    await db.exec(`
      insert into public.source_cards(id,user_id,source_text,title,category,card_type)
        values ('${sourceId}','${owner}','【甲】かつ【乙】または【丙】','旧原文','民法','規範');
      insert into public.cards(id,user_id,source_id,question,answer,title,category,card_type,rank,blank_count,is_favorite,interval,next_review)
      values
        ('${oldA}','${owner}','${sourceId}','______かつ______または丙','甲 / 乙','旧原文','民法','規範','A+',2,true,30,study_private.today()),
        ('${oldB}','${owner}','${sourceId}','手編集______','補足','旧原文','民法','規範','B',1,false,1,study_private.today()+1);
      insert into public.daily_assignments(user_id,assignment_date,card_id,source_id,position,completed_at,quality)
        values ('${owner}',study_private.today(),'${oldB}','${sourceId}',0,now(),4);
    `);
    const expected = {source:{source_text:'【甲】かつ【乙】または【丙】',title:'旧原文',category:'民法',card_type:'規範'},
      cards:[
        {id:oldA,question:'______かつ______または丙',answer:'甲 / 乙',title:'旧原文',category:'民法',card_type:'規範',rank:'A+',highlighted_keywords:''},
        {id:oldB,question:'手編集______',answer:'補足',title:'旧原文',category:'民法',card_type:'規範',rank:'B',highlighted_keywords:''},
      ],
    };
    const request = {
      mode:'replace',source_id:sourceId,source_text:'【甲】かつ【乙】または【丙】',title:'旧原文',category:'民法',
      card_type:'規範',expected,cards:[{...expected.cards[0],blank_count:2}],
    };
    await assert.rejects(db.query('select public.replace_source_bundle_checked($1,$2::jsonb)',[owner,{
      ...request,expected:{...expected,source:{...expected.source,title:'古いタイトル'}},
    }]),{code:'40001'});
    await db.query('select public.replace_source_bundle_checked($1,$2::jsonb)',[owner,request]);
    const preserved = await db.query<{interval:number}>('select interval from public.cards where id=$1',[oldA]);
    assert.equal(preserved.rows[0].interval,30);
    const archived = await db.query<{assignments:unknown[]}>('select assignments from study_private.replaced_cards where id=$1',[oldB]);
    assert.equal(archived.rows[0].assignments.length,1);

    const snapshot = (await db.query<{snapshot:Parameters<typeof prepareMigration>[0]}>(
      'select public.study_migration_snapshot($1) as snapshot',[owner],
    )).rows[0].snapshot;
    const plan = prepareMigration(snapshot);
    assert.equal(plan.bundles.length,1);
    const migrationSql = 'select public.study_apply_regeneration($1,$2::jsonb) as value';
    const migrated = await db.query(migrationSql,[owner,plan]);
    assert.deepEqual((await db.query(migrationSql,[owner,plan])).rows,migrated.rows);
    const imported = await asUser<Daily>(db,signedIn,'daily');
    assert.equal(imported.assignments.length,1);
    assert.equal(imported.assignments[0].target_id,sourceId);
    assert(imported.assignments[0].completed_at);
    const library = await asUser<Library>(db,signedIn,'library');
    assert.equal(library.cards.filter(card => card.source_id===sourceId && !card.study_archived_at).length,3);
    assert(library.cards.find(card => card.id===oldA && card.is_favorite && !card.study_archived_at));
    assert(library.cards.find(card => card.id===oldB && card.study_archived_at));
    assert.equal((await asUser<Library>(db,otherAuth,'library')).cards.length,0);
    await assert.rejects(asUser(db,'00000000-0000-4000-8000-000000000099','library'),{code:'42501'});
    await assert.rejects(db.transaction(async tx => {
      await tx.exec('set local role anon');
      await tx.query("select public.study_api('library')");
    }),{code:'42501'});
    await assert.rejects(asUser(db,otherAuth,'source_metadata',{id:sourceId,version:library.sources[0].study_version,category:'民法',rank:'A'}),{code:'40001'});

    const long = Array.from({length:21},(_,i) => `【項目${i+1}】`).join('、');
    const create = (title: string,source_text: string,rank: string) => asUser<{id:string}>(db,signedIn,'save_bundle',{
      title,source_text,rank,category:'民法',card_type:'規範',tags:['債権'],variants:generate(source_text,'規範'),
    });
    const study = await create('長い原文',long,'A+');
    const overdue = await create('期限超過','【旧い】らしい','C');
    const futurePayload = {
      request_id:'00000000-0000-4000-8000-000000000089',
      title:'未来',source_text:'【来週】の論点',rank:'A+',category:'民法',card_type:'規範',
      variants:generate('【来週】の論点','規範'),
    };
    const future = await asUser<{id:string}>(db,signedIn,'save_bundle',futurePayload);
    assert.deepEqual(await asUser(db,signedIn,'save_bundle',futurePayload),future);
    await assert.rejects(asUser(db,signedIn,'save_bundle',{...futurePayload,title:'別の内容'}),{code:'40001'});
    await db.query('update study_private.targets set next_review=study_private.today()-7 where id=$1',[overdue.id]);
    await db.query('update study_private.targets set next_review=study_private.today()+1 where id=$1',[future.id]);
    await asUser(db,signedIn,'quota',{quota:3});
    const assigned = await asUser<Daily>(db,signedIn,'daily');
    assert.deepEqual(assigned.assignments.map(item => item.target_id),[sourceId,overdue.id,study.id]);
    assert.deepEqual(await asUser(db,signedIn,'daily'),assigned);
    const item = assigned.assignments[2];
    const slots = holes(item.layout);
    assert.equal(slots.length,11);
    const first = Object.fromEntries(slots.slice(0,8).map((hole,i) => [hole.hole,i===0 ? 0 : 4])) as Assignment['grades'];
    await assert.rejects(asUser(db,signedIn,'evaluate',evaluate(item,first,true)),{code:'22023'});
    const partial = await asUser<Assignment>(db,signedIn,'evaluate',evaluate(item,first,false));
    assert.equal(partial.completed_at,null);
    assert.deepEqual((await asUser<Daily>(db,signedIn,'daily')).assignments[2].grades,first);
    assert.deepEqual(await asUser(db,signedIn,'evaluate',evaluate(item,first,false)),partial);
    await assert.rejects(asUser(db,signedIn,'evaluate',evaluate(item,{[slots[0].hole]:4},false)),{code:'40001'});
    await assert.rejects(asUser(db,signedIn,'evaluate',{...evaluate(partial,{},false),day:'2026-01-01'}),{code:'40001'});
    const second = Object.fromEntries(slots.slice(8).map(hole => [hole.hole,4])) as Assignment['grades'];
    const saved = await asUser<Assignment>(db,signedIn,'evaluate',evaluate(partial,second,true));
    assert(saved.completed_at);
    assert.equal(Object.keys(saved.grades).length,11);
    assert.deepEqual(await asUser(db,signedIn,'evaluate',evaluate(partial,second,true)),saved);
    await assert.rejects(asUser(db,signedIn,'evaluate',evaluate(partial,{
      ...second,[slots[8].hole]:0,
    },true)),{code:'40001'});
    const retry = await asUser<Assignment>(db,signedIn,'relearn',{
      target_id:saved.target_id,day:saved.day,version:saved.version,hole:slots[0].hole,
    });
    assert.equal(retry.next_review,saved.next_review);
    assert.deepEqual(retry.retried,[slots[0].hole]);
    await asUser(db,signedIn,'preset',{name:'論点',filters:{mode:'range',subjects:['民法']}});
    await assert.rejects(asUser(db,otherAuth,'evaluate',evaluate(item,first,false)),{code:'40001'});
    const priorVersion = (await asUser<Library>(db,signedIn,'library')).sources.find(row => row.id===overdue.id)!.study_version;
    await asUser(db,signedIn,'archive',{id:overdue.id,version:priorVersion,source:true});
    await assert.rejects(asUser(db,signedIn,'evaluate',evaluate(assigned.assignments[1],{1:4},true)),{code:'40001'});

    const backup = await asUser<Record<string,unknown>>(db,signedIn,'backup');
    const restoredDb = await schema();
    try {
      await asUser(restoredDb,signedIn,'restore',backup);
      assert.deepEqual(await asUser(restoredDb,signedIn,'backup'),backup);
    } finally {
      await restoredDb.close();
    }
  } finally {
    await db.close();
  }
});
