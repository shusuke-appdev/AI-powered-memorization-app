import {useState} from 'react';
import {api, message, StudyError} from './api.ts';
import {cardGrades, grades, holes, onlyHoles, sections, noBlanks} from './cards.ts';
import type {Assignment, Daily, Grade, PracticeItem, Segment, Source} from './cards.ts';

export function Highlight({text}: {text: string}) {
  return text.split(/(【[^【】]+】)/g).map((part,i) =>
    part.startsWith('【') && part.endsWith('】') ? <mark key={i}>{part.slice(1,-1)}</mark> : part,
  );
}

export function Prompt({layout, open, whole}: {layout: Segment[]; open: boolean; whole?: boolean}) {
  return <div className="prompt">{layout.map((item, i) => typeof item === 'string'
    ? (whole ? <Highlight key={i} text={item}/> : item)
    : <span key={i} className={open ? 'answer' : 'gap'}>
        <small>{item.hole}</small>{open && item.answer}
      </span>,
  )}</div>;
}

export type Scores = Record<string, Grade>;

export function Grader({layout, choices, onPick}: {layout: Segment[]; choices: Scores; onPick: (hole: number, grade: Grade) => void}) {
  const slots = holes(layout);
  return <div className="ratings">{(slots.length ? slots : [{hole: 0, answer: ''}]).map(slot =>
    <fieldset key={slot.hole}>
      <legend>{slot.hole ? `穴 ${slot.hole}　${slot.answer}` : 'カードの評価'}</legend>
      <div className="rating-options">{(slot.hole ? grades : cardGrades).map(({value, label}) =>
        <label key={value} className={choices[slot.hole] === value ? 'selected' : ''}>
          <input type="radio" name={`rating-${slot.hole}`} checked={choices[slot.hole] === value} onChange={() => onPick(slot.hole,value)}/>
          {label}
        </label>,
      )}</div>
    </fieldset>,
  )}</div>;
}

export function hasScores(layout: Segment[], values: Scores) {
  const ids = holes(layout).map(hole => hole.hole);
  return (ids.length ? ids : [0]).every(id => values[id] !== undefined);
}

function nextSection(all: Segment[][], saved: Scores) {
  const index = all.findIndex(part => !hasScores(part,saved));
  return index < 0 ? all.length - 1 : index;
}

function DailyCard({item, onSave, onRefresh, preview}: {
  item: Assignment; onSave: (item: Assignment) => void; onRefresh: () => Promise<void>;
  preview: (scores: Scores) => string | undefined;
}) {
  const all = sections(item.layout);
  const [section,setSection] = useState(() => nextSection(all,item.grades));
  const [values,setValues] = useState<Scores>(item.grades);
  const [open,setOpen] = useState(() => noBlanks(item.card_type));
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [stale,setStale] = useState(false);
  const part = all[section];
  const currentIds = holes(part).map(hole => hole.hole);
  const ready = hasScores(part,values);
  const changes = Object.fromEntries((currentIds.length ? currentIds : [0]).flatMap(
    id => values[id] === undefined ? [] : [[id,values[id]]],
  ));
  const merged = {...item.grades,...changes};
  const entire = all.every(sub => hasScores(sub,merged));
  const savedCount = Object.keys(item.grades).length;

  function move(index: number) {
    setSection(index);
    setOpen(noBlanks(item.card_type));
    window.scrollTo({top: 0});
  }

  async function save() {
    if (!ready || busy) return;
    setBusy(true);
    setError('');
    try {
      const response = await api<Assignment>('evaluate', {
        target_id: item.target_id, card_id:item.card_id, day:item.day, version:item.version,
        revision:item.revision, grades:changes, finish:entire,
      });
      onSave(response);
      if (!response.completed_at) {
        setValues(current => ({...current,...response.grades}));
        move(nextSection(all,response.grades));
      }
    } catch (err) {
      setError(message(err));
      setStale(err instanceof StudyError && err.code === '40001');
    } finally {
      setBusy(false);
    }
  }

  return <section aria-label="出題カード">
    <div className="card-heading">
      <div><span className="category">{item.category}</span><h2>{item.title || '無題'}</h2></div>
      <span className="rank">{item.rank}</span>
    </div>
    {all.length > 1 && <p className="muted">区切り {section+1} / {all.length} · {savedCount}穴 保存済み</p>}
    <Prompt layout={part} open={open} whole={noBlanks(item.card_type)}/>
    {open && !holes(item.layout).length && item.answer && <p className="plain-answer">{item.answer}</p>}
    {open && <Grader layout={part} choices={values} onPick={(id,value) => setValues(current => ({...current,[id]:value}))}/>}
    {error && <p role="alert" className="notice">{error}</p>}
    <div className="actions sticky">
      {section > 0 && <button onClick={() => move(section-1)} disabled={busy}>前の区切り</button>}
      {!open && <button className="primary" onClick={() => setOpen(true)}>答えを見る</button>}
      {open && <button className="primary" disabled={!ready || busy || stale} onClick={save}>
        {busy ? '保存中…' : entire ? '復習を確定' : '区切りを保存'}
      </button>}
      {stale && <button onClick={() => void onRefresh().catch(err => setError(message(err)))}>最新の内容を開く</button>}
      {open && entire && !stale && <span className="muted">次回予定 {preview(merged) ?? '保存時に決定'}</span>}
    </div>
  </section>;
}

export type Retry = {assignment: Assignment; hole: number; items: Segment[]};

function RetryCard({row, onSave}: {row: Retry; onSave: (item: Assignment) => void}) {
  const [open,setOpen] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  async function finish() {
    setBusy(true);
    try {
      onSave(await api<Assignment>('relearn',{
        target_id: row.assignment.target_id, day: row.assignment.day,
        version: row.assignment.version, hole: row.hole,
      }));
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }
  return <section>
    <h2>{row.assignment.title || '無題'} · 穴 {row.hole}</h2>
    <Prompt layout={row.items} open={open}/>
    {error && <p role="alert" className="notice">{error}</p>}
    <div className="actions sticky">
      {open
        ? <button className="primary" disabled={busy} onClick={finish}>解き直しを完了</button>
        : <button className="primary" onClick={() => setOpen(true)}>答えを見る</button>}
    </div>
  </section>;
}

export function DailyPage({daily, sources, valid, preview, onSave, load}: {
  daily: Daily; sources: Source[]; valid: (assignment: Assignment) => boolean;
  preview: (item: Assignment, scores: Scores) => string | undefined;
  onSave: (item: Assignment) => void; load: () => Promise<void>;
}) {
  const [retry,setRetry] = useState(false);
  const [showSources,setShowSources] = useState(false);
  const [refresh,setRefresh] = useState(0);
  const completed = daily.assignments.filter(item => item.completed_at);
  const item = daily.assignments.find(assignment => !assignment.completed_at);
  const totalHoles = daily.assignments.reduce((count,item) => count+holes(item.layout).length,0);
  const remainingHoles = daily.assignments.reduce((count,item) => count+holes(item.layout)
    .filter(hole => !item.completed_at && item.grades[hole.hole] === undefined).length,0);
  const weak = completed.filter(valid).sort((a,b) => a.position - b.position).flatMap(assignment =>
    holes(assignment.layout).filter(hole => [0,2].includes(assignment.grades[hole.hole]) && !assignment.retried.includes(hole.hole))
      .map(hole => ({
        assignment,hole:hole.hole,
        items:onlyHoles(sections(assignment.layout).find(part => holes(part).some(item => item.hole === hole.hole)) ?? [],[hole.hole]),
      })),
  );
  const reviewedSources = new Set(completed.map(assignment => assignment.target_id));
  const last = completed.filter(item => item.next_review).sort((a,b) => (b.completed_at ?? '').localeCompare(a.completed_at ?? ''))[0];

  return <>
    <header className="page-title"><div><h1>本日のノルマ</h1><p>{daily.day}</p></div></header>
    <div className="progress-line">
      <progress value={completed.length} max={daily.assignments.length || 1}/>
      <span>{completed.length} / {daily.assignments.length} 件 · 残り {remainingHoles} / {totalHoles} 穴</span>
    </div>
    {last && <p className="muted">前回確定した原文の次回復習日 {last.next_review}</p>}
    {item ? <DailyCard key={`${item.day}:${item.card_id}:${item.version}:${refresh}`} item={item} onSave={onSave}
      onRefresh={async () => {await load();setRefresh(value => value+1);}}
      preview={scores => preview(item,scores)}/> : <>
      <h2>{daily.assignments.length ? '本日のノルマ完了' : '今日の割当はありません'}</h2>
      {daily.unassigned > 0 && <p>本日の割当に含まれていない期限到来済みの原文が {daily.unassigned} 件あります。</p>}
      <div className="actions">
        {weak.length > 0 && <button className="primary" onClick={() => setRetry(value => !value)}>
          {retry ? '解き直しを閉じる' : `△・×を解き直す（${weak.length}穴）`}
        </button>}
        {sources.some(source => reviewedSources.has(source.id)) && <button onClick={() => setShowSources(value => !value)}>
          {showSources ? '原文を閉じる' : '復習した原文を確認'}
        </button>}
      </div>
      {retry && weak.length > 0 && <RetryCard key={`${weak[0].assignment.target_id}:${weak[0].hole}`} row={weak[0]} onSave={onSave}/>}
      {retry && weak.length === 0 && <p role="status">解き直しが完了しました。</p>}
      {showSources && sources.filter(source => reviewedSources.has(source.id)).map(source =>
        <details key={source.id}><summary>{source.title || '無題'}</summary><p className="preserve"><Highlight text={source.source_text}/></p></details>,
      )}
    </>}
  </>;
}

export function PracticeCard({item, onGrade, recorded}: {item: PracticeItem; onGrade: (values: Scores) => void; recorded?: string}) {
  const [open,setOpen] = useState(recorded !== undefined || noBlanks(item.cardType));
  const [index,setIndex] = useState(0);
  const [values,setValues] = useState<Scores>({});
  const parts = sections(item.layout);
  return <section>
    <div className="card-heading"><div><span className="category">{item.category}</span><h2>{item.title}</h2></div><span className="rank">{item.rank}</span></div>
    {parts.length > 1 && <p className="muted">区切り {index + 1} / {parts.length}</p>}
    <Prompt layout={parts[index]} open={open} whole={noBlanks(item.cardType)}/>
    {recorded && <p className="plain-answer preserve">記入した答え　{recorded}</p>}
    {open && !holes(item.layout).length && item.answer && <p className="plain-answer">{item.answer}</p>}
    {open && <Grader layout={parts[index]} choices={values} onPick={(id,value) => setValues(current => ({...current,[id]:value}))}/>}
    <div className="actions sticky">
      {index > 0 && <button onClick={() => setIndex(index-1)}>前の区切り</button>}
      {!open ? <button className="primary" onClick={() => setOpen(true)}>答えを見る</button>
        : <button className="primary" disabled={!hasScores(parts[index],values)} onClick={() => {
          if (index + 1 === parts.length) onGrade(values);
          else {setIndex(index+1);setOpen(recorded !== undefined);window.scrollTo({top:0});}
        }}>{index + 1 === parts.length ? '評価を確定' : '次の区切り'}</button>}
    </div>
  </section>;
}
