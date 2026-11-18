import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {generate, matchesVariant, ranks, subjects, types} from '../src/cards.ts';
import type {Card, Source} from '../src/cards.ts';

export function prepareMigration(snapshot: {version: string; sources: Source[]; cards: Card[]}) {
  if (snapshot.version !== '3.0' || !Array.isArray(snapshot.sources) || !Array.isArray(snapshot.cards)) {
    throw new Error('study_migration_snapshot のJSONを指定してください。');
  }
  const groups = new Map<string, Card[]>();
  for (const card of snapshot.cards) {
    if (!card.source_id || card.study_archived_at) continue;
    const group = groups.get(card.source_id) ?? [];
    group.push(card);
    groups.set(card.source_id, group);
  }
  const bundles = [];
  const exceptions = [];
  const reconciliation = [];
  for (const source of snapshot.sources) {
    if ('study_archived_at' in source && source.study_archived_at) continue;
    try {
      if (!source.card_type || !types.includes(source.card_type)) throw new Error('種類を判定できません。');
      const group = groups.get(source.id) ?? [];
      const rank = ranks.find(rank => group.some(card => card.rank === rank)) ?? 'B';
      const variants = generate(source.source_text,source.card_type);
      const kept = new Set<string>();
      for (const variant of variants) {
        const same = group.find(card => !kept.has(card.id) && matchesVariant(card,variant,source.card_type!));
        if (same) kept.add(same.id);
      }
      reconciliation.push({id:source.id,kept:kept.size,new:variants.length-kept.size,archived:group.length-kept.size});
      bundles.push({
        id: source.id, version: source.study_version, expected_text: source.source_text,
        source_text: source.source_text, title: source.title ?? '',
        category: subjects.includes(source.category ?? '') ? source.category : 'その他',
        card_type: source.card_type, rank, tags: source.study_tags,
        variants,
      });
    } catch (error) {
      exceptions.push({id: source.id, reason: error instanceof Error ? error.message : '形式を判定できません。'});
    }
  }
  const migration_id = createHash('sha256').update(JSON.stringify({snapshot,bundles,exceptions})).digest('hex');
  return {migration_id,snapshot,bundles,exceptions,reconciliation};
}

if (import.meta.main) {
  const [, , input, output] = process.argv;
  if (!input || !output) throw new Error('npm run prepare-migration -- <snapshot.json> <plan.json>');
  const plan = prepareMigration(JSON.parse(await readFile(input,'utf8')));
  await writeFile(output, JSON.stringify(plan,null,2), {flag:'wx'});
  console.log(JSON.stringify({
    migration_id: plan.migration_id, sources: plan.bundles.length, exceptions: plan.exceptions.length,
    variants: plan.bundles.reduce((count,bundle) => count + bundle.variants.length,0),
    kept:plan.reconciliation.reduce((count,row) => count+row.kept,0),
    archived:plan.reconciliation.reduce((count,row) => count+row.archived,0),
  }));
}
