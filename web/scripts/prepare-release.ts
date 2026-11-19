import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {join} from 'node:path';

const dist = process.argv[2] ?? 'dist';
if (execFileSync('git',['status','--porcelain'],{encoding:'utf8'}).trim()) {
  throw new Error('配信前にGitの作業ツリーを空にしてください。');
}
const revision = execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim();
const hash = (data: Uint8Array) => createHash('sha256').update(data).digest('hex');
const index = await readFile(join(dist,'index.html'));
const assets = await readdir(join(dist,'assets'));
const manifest: Record<string,string> = {};
let configured = false;
for (const name of assets.filter(file => /\.(js|css)$/.test(file)).sort()) {
  const filename = `assets/${name}`;
  const bytes = await readFile(join(dist,filename));
  manifest[filename] = hash(bytes);
  if (!name.endsWith('.js')) continue;
  const code = bytes.toString('utf8');
  if (/sb_secret_[A-Za-z0-9_-]{20,}|GOCSPX-[A-Za-z0-9_-]{12,}/.test(code)) {
    throw new Error('静的ファイルに秘密情報が含まれています。');
  }
  configured ||= /sb_publishable_[A-Za-z0-9_-]{20,}/.test(code) && /https:\/\/[a-z0-9]{20}\.supabase\.co/.test(code);
}
if (!configured) throw new Error('配信先のSupabase公開設定を確認してください。');
for (const route of ['review','practice','manage','add','stats']) {
  await writeFile(join(dist,`${route}.html`),index);
}
await writeFile(join(dist,'release.json'),JSON.stringify({revision,index:hash(index),assets:manifest}));
console.log(`Release ${revision.slice(0,8)}: ${Object.keys(manifest).length} assets verified`);
