import {readFile,writeFile} from 'node:fs/promises';
import {createClient} from '@supabase/supabase-js';

const [operation,user,path,confirmation] = process.argv.slice(2);
if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(user ?? '') || !path ||
    !['snapshot','apply'].includes(operation)) {
  throw new Error('node scripts/migrate.ts snapshot <user-id> <new-file> | apply <user-id> <plan> --cutover-confirmed');
}
if (operation === 'apply' && confirmation !== '--cutover-confirmed') {
  throw new Error('書き込み停止と差分確認後に --cutover-confirmed を指定してください。');
}
const url = process.env.SUPABASE_URL;
const key = process.env.SUPABASE_SECRET_KEY;
if (!url || !key) throw new Error('管理者の実行環境で SUPABASE_URL と SUPABASE_SECRET_KEY を設定してください。');
const db = createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
if (operation === 'snapshot') {
  const {data,error} = await db.rpc('study_migration_snapshot',{p_user:user});
  if (error) throw new Error(`スナップショット取得に失敗しました (${error.code})。`);
  await writeFile(path,JSON.stringify(data,null,2),{flag:'wx'});
  console.log(JSON.stringify({sources:data.sources.length,cards:data.cards.length,legacy_assignments:data.legacy_assignments.length}));
} else {
  const plan = JSON.parse(await readFile(path,'utf8'));
  const {data,error} = await db.rpc('study_apply_regeneration',{p_user:user,p_plan:plan});
  if (error) throw new Error(`移行を確定できませんでした (${error.code})。`);
  console.log(JSON.stringify({sources:data.changes.length,exceptions:data.exceptions.length,
    kept:data.changes.reduce((sum:number,row:{kept:number}) => sum+row.kept,0),
    new:data.changes.reduce((sum:number,row:{new:number}) => sum+row.new,0),
    archived:data.changes.reduce((sum:number,row:{archived:number}) => sum+row.archived,0)}));
}
