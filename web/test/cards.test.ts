import assert from 'node:assert/strict';
import test from 'node:test';
import {combinations, generate, holes, layoutFor, practiceCandidates, sections, defaults} from '../src/cards.ts';
import type {Assignment, Card, Library} from '../src/cards.ts';
import {prepareImport,readCsv} from '../src/backup.ts';

test('half clozes are deterministic, distinct, complete and overlap', () => {
  for(let n=1;n<=500;n++) {
    const rows = combinations(n);
    assert.equal(new Set(rows.map(row => row.join(','))).size,rows.length);
    assert.deepEqual(combinations(n),rows);
    assert.deepEqual([...new Set(rows.flat())].sort((a,b) => a-b),Array.from({length:n},(_,i) => i+1));
    for (const row of rows) assert.equal(new Set(row).size,Math.ceil(n/2));
    if (n>2) for (const [i,row] of rows.entries()) {
      assert(rows.slice(i+1).every(other => row.some(hole => other.includes(hole))),String(n));
    }
  }
});

test('long cards use sections, with adjacent brackets, literal underscores and slashes intact', () => {
  const source = '注___【甲 / 乙】【丙】' + Array.from({length:98},(_,i) => `、【項目${i}】`).join('');
  const cards = generate(source,'規範');
  assert.equal(cards.length,5);
  assert(cards.every(card => card.blank_count === 50));
  const answer = cards.flatMap(card => holes(card.layout)).find(hole => hole.hole === 1);
  assert.equal(answer?.answer,'甲 / 乙');
  assert(cards.every(card => sections(card.layout).every(part => holes(part).length <= 8)));
  assert.throws(() => generate('【閉じない','規範'));
  assert.throws(() => generate('原文','規範'));
  assert.equal(generate('用語【甲】','知識')[0].blank_count,0);
});

function card(id: string, source_id: string, rank = 'A+'): Card {
  return {id,source_id,rank,question:'本文______と______',answer:'甲 / 乙',blank_count:2,
    title:'試験用',category:'民法',card_type:'規範',is_favorite:true,study_tags:[],
    study_version:'version',study_layout:['本文',{hole:1,answer:'甲'},'と',{hole:2,answer:'乙'}],
    study_archived_at:null,repetitions:0,interval:1,ease_factor:2.5,next_review:'2099-01-01'};
}

test('practice counts originals, intersects filters and uses the latest outcome per hole', () => {
  const attempt = (grades: Assignment['grades'], version = 'current') => ({
    target_id:'original',version,layout:card('variant','original').study_layout!,grades,
  }) as Assignment;
  const library: Library = {
    sources:[{id:'original',title:'試験用',category:'民法',card_type:'規範',source_text:'本文',study_tags:['債権','契約'],
      study_version:'current',study_favorite:true}],
    cards:[card('variant1','original'),card('variant2','original','A'),card('variant3','other','C')],
    targets:[{id:'original',version:'current',next_review:'2099-01-01',interval:1,ease_factor:2.5,repetitions:0,seen_holes:[1,2]}],
    history:[attempt({1:4,2:2}),attempt({1:0,2:4}),attempt({2:4},'old')],
    presets:[],quota:15,
  };
  assert.equal(practiceCandidates(library,defaults).length,2);
  assert.equal(practiceCandidates(library,{...defaults,subjects:['民法'],tags:['契約','債権'],ranks:['A+'],favorite:true}).length,1);
  assert.equal(practiceCandidates(library,{...defaults,subjects:['刑法'],tags:['契約']}).length,0);
  const [item] = practiceCandidates(library,{...defaults,mode:'weak'});
  assert.deepEqual(holes(item.layout).map(hole => hole.hole),[2]);
  assert.equal(practiceCandidates(library,{...defaults,mode:'priority'}).length,1);
});

test('legacy backup imports knowlege-only rows and handles quoted CSV fields', () => {
  const result = prepareImport(JSON.stringify({
    version:'2.0', source_cards:[{export_id:'x',source_text:'長文',card_type:'知識'}],
    cards:[{source_export_id:'x',question:'長文',card_type:'知識',answer:'旧仕様',blank_count:1,interval:17}],
  }),false,[]);
  assert.equal(result.cards,1);
  assert.match(result.warnings[0],/未使用の答え/);
  assert.equal(result.payload.cards[0].answer,'');
  assert.equal(result.payload.cards[0].interval,17);
  assert.deepEqual(readCsv('question,answer\r\n"a,b","abc\ndef"\r\n'),[{question:'a,b',answer:'abc\ndef'}]);
  const legacy = {...card('legacy','original'),study_layout:null,answer:'甲 / 乙 / 丙'};
  assert.equal(holes(layoutFor(legacy)).length,0);
});
