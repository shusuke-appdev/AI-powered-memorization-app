import {noBlanks, ranks, subjects, types} from './cards.ts';
import type {Card} from './cards.ts';

type Row = Record<string, unknown>;
const asText = (value: unknown) => value === undefined || value === null ? '' : String(value);

export function readCsv(text: string): Row[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;
  text = text.replace(/^\uFEFF/,'');
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"' && (quoted || !cell)) {
      if (quoted && text[i+1] === '"') {cell += '"';i++;}
      else quoted = !quoted;
    } else if (!quoted && (char === '\n' || char === '\r')) {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
      if (char === '\r' && text[i+1] === '\n') i++;
    } else if (!quoted && char === ',') {
      row.push(cell);
      cell = '';
    } else {
      cell += char;
    }
  }
  if (quoted) throw new Error('CSVの引用符が閉じられていません。');
  if (row.length || cell) rows.push([...row,cell]);
  const headers = rows.shift();
  if (!headers?.includes('question')) throw new Error('CSVに question 列がありません。');
  return rows.filter(values => values.some(value => value !== '')).map(values =>
    Object.fromEntries(headers.map((header,i) => [header,values[i] ?? ''])));
}

export function exportCsv(cards: Card[]): string {
  const keys = ['question','answer','title','category','card_type','rank','blank_count','is_favorite','ease_factor','interval','repetitions','next_review'] as const;
  const quote = (value: unknown) => `"${asText(value).replaceAll('"','""')}"`;
  return [keys.join(','),...cards.filter(card => !card.study_archived_at)
    .map(card => keys.map(key => quote(card[key])).join(','))].join('\r\n');
}

export function prepareImport(text: string, csv: boolean, existing: Pick<Card,'question'|'answer'|'study_archived_at'>[]) {
  const raw = csv ? {version:'csv',cards:readCsv(text),source_cards:[]} : JSON.parse(text);
  if (!raw || typeof raw !== 'object') throw new Error('バックアップの形式を確認してください。');
  if (String(raw.version) === '3.0') {
    if (!['sources','cards','targets','assignments','presets','replaced_cards','legacy_assignments'].every(key =>
      Array.isArray(raw[key]) && raw[key].every((row: unknown) => row && typeof row === 'object' && !Array.isArray(row)))) {
      throw new Error('完全バックアップに必要な項目がありません。');
    }
    const quota = Number(raw.quota);
    if (!Number.isInteger(quota) || quota<1 || quota>100) throw new Error('バックアップの復習上限を確認してください。');
    return {mode:'restore',payload:raw, cards:raw.cards.length, sources:raw.sources.length, warnings:['完全バックアップは空のデッキに復元します。']};
  }
  if (!['1','2','csv'].includes(String(raw.version ?? '1').split('.')[0]) ||
     !Array.isArray(raw.cards) || (raw.source_cards !== undefined && !Array.isArray(raw.source_cards))) {
    throw new Error('このバックアップ形式には対応していません。');
  }
  const known = new Set<string>();
  const normalizeCategory = (value: unknown) => subjects.includes(asText(value)) ? asText(value) : 'その他';
  const sources = (raw.source_cards ?? []).map((source: Row,index: number) => {
    const export_id = asText(source.export_id ?? source.id);
    const source_text = asText(source.source_text).trim();
    if (!export_id || !source_text || known.has(export_id)) throw new Error(`原文 ${index+1} の識別子または本文を確認してください。`);
    known.add(export_id);
    return {
      export_id, source_text, title:asText(source.title), category:normalizeCategory(source.category),
      card_type:types.includes(asText(source.card_type)) ? source.card_type : '規範',
    };
  });
  const allReferences = new Set<string>();
  const retained = new Set<string>();
  const key = (question: string,answer: string) => JSON.stringify([question,answer]);
  const seen = new Set(existing.filter(card => !card.study_archived_at).map(card => key(card.question,card.answer)));
  let legacy = 0;
  let skipped = 0;
  const cards = raw.cards.flatMap((card: Row,index: number) => {
    const question = asText(card.question).trim();
    let answer = asText(card.answer).trim();
    const card_type = types.includes(asText(card.card_type)) ? asText(card.card_type) : answer ? '規範' : '知識';
    const source_export_id = asText(card.source_export_id ?? card.source_id);
    if (!question || (source_export_id && !known.has(source_export_id))) throw new Error(`カード ${index+1} の本文または参照先を確認してください。`);
    if (source_export_id) allReferences.add(source_export_id);
    if (noBlanks(card_type) && (answer || Number(card.blank_count ?? 0) !== 0)) {legacy++;answer = '';}
    if (!noBlanks(card_type) && !answer) throw new Error(`カード ${index+1} に答えがありません。`);
    const signature = key(question,answer);
    if (seen.has(signature)) {skipped++;return [];}
    seen.add(signature);
    retained.add(source_export_id);
    const count = question.match(/_{3,}/g)?.length ?? 0;
    return [{
      question,answer,card_type,source_export_id,title:asText(card.title),category:normalizeCategory(card.category),
      rank:ranks.includes(asText(card.rank)) ? card.rank : 'B', blank_count:noBlanks(card_type) ? 0 : Math.max(1,count),
      highlighted_keywords:asText(card.highlighted_keywords), is_favorite:[true,1,'true','1'].includes(card.is_favorite as string),
      ease_factor:numeric(card.ease_factor,2.5,1.3), interval:Math.floor(numeric(card.interval,1,0)),
      repetitions:Math.floor(numeric(card.repetitions,0,0)),
      next_review:/^\d{4}-\d{2}-\d{2}$/.test(asText(card.next_review)) ? card.next_review : null,
    }];
  });
  const keepSources = sources.filter((source: {export_id:string}) => !allReferences.has(source.export_id) || retained.has(source.export_id));
  const warnings = [];
  if (csv) warnings.push('CSVのカードは原文と紐づいていません。');
  if (legacy) warnings.push(`旧形式の知識・類型 ${legacy} 件は、未使用の答えと穴数を整理して復元します。元ファイルを保管してください。`);
  if (skipped) warnings.push(`重複 ${skipped} 件をスキップします。`);
  return {mode:'legacy_import',payload:{sources:keepSources,cards},cards:cards.length,sources:keepSources.length,warnings};
}

function numeric(value: unknown,fallback: number,minimum: number): number {
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) && number >= minimum ? number : fallback;
}

export function writeDownload(name: string,text: string,type: string) {
  const url = URL.createObjectURL(new Blob([text],{type}));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url),1000);
}
