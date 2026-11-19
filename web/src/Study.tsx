import {useEffect, useRef, useState} from 'react';
import {api, message, StudyError} from './api.ts';
import {cardGrades, grades, holes, sections, noBlanks} from './cards.ts';
import type {Assignment, Grade, PracticeItem, Segment} from './cards.ts';

export function Highlight({text}: {text: string}) {
  return text.split(/(【[^【】]+】)/g).map((part,i) =>
    part.startsWith('【') && part.endsWith('】') ? <mark key={i}>{part.slice(1,-1)}</mark> : part,
  );
}

export function Prompt({layout, open, whole, active, order}: {
  layout: Segment[]; open: boolean; whole?: boolean; active?: number; order?: number[];
}) {
  return <div className="prompt">{layout.map((item, i) => {
    if (typeof item === 'string') return whole ? <Highlight key={i} text={item}/> : item;
    const revealed = open && (active === undefined || active === item.hole);
    const number = order ? order.indexOf(item.hole)+1 : item.hole;
    return <span key={i} className={revealed ? 'answer' : active === item.hole ? 'gap current-gap' : 'gap'}>
      <small aria-label={`穴 ${number}`}>{number}</small>{revealed && item.answer}
    </span>;
  })}</div>;
}

export type Scores = Record<string, Grade>;
export type Written = Record<string, string>;

export function holeOrder(layout: Segment[]): number[] {
  const keys = holes(layout).map(part => part.hole);
  return keys.length ? keys : [0];
}

export function contextFor(layout: Segment[], hole: number): Segment[] {
  return sections(layout).find(part => holes(part).some(slot => slot.hole === hole)) ?? layout;
}

function RatingButtons({number, disabled, selected, focusFirst, pick}: {
  number: number; disabled: boolean; selected?: Grade; focusFirst?: boolean; pick: (grade: Grade) => void;
}) {
  const first = useRef<HTMLButtonElement>(null);
  useEffect(() => {if (focusFirst) first.current?.focus({preventScroll:true});},[focusFirst]);
  return <fieldset className="rating-field" disabled={disabled}>
    <legend>{number ? `穴 ${number} の評価` : 'カードの評価'}</legend>
    <div className={number ? 'rating-options' : 'rating-options whole-ratings'}>
      {(number ? grades : cardGrades).map(({value,label},index) =>
        <button key={value} ref={index === 0 ? first : undefined} type="button"
          aria-pressed={selected === value} onClick={() => pick(value)}>{label}</button>)}
    </div>
  </fieldset>;
}

function Question({title,category,rank,layout,kind,answer,hole,open,heading}: {
  title: string; category: string; rank: string; layout: Segment[]; kind: string | null;
  answer: string; hole: number; open: boolean; heading: React.RefObject<HTMLHeadingElement | null>;
}) {
  return <>
    <div className="card-heading">
      <div><span className="category">{category}</span><h2 ref={heading} tabIndex={-1}>{title || '無題'}</h2></div>
      <span className="rank">{rank}</span>
    </div>
    <Prompt layout={contextFor(layout,hole)} open={open} active={hole} whole={noBlanks(kind)} order={holeOrder(layout)}/>
    {open && !hole && answer && <p className="plain-answer">{answer}</p>}
  </>;
}

function DailyCard({item,onSave,onRefresh}: {
  item: Assignment; onSave: (value: Assignment) => void; onRefresh: () => Promise<void>;
}) {
  const order = holeOrder(item.layout);
  const first = order.findIndex(hole => item.grades[hole] === undefined);
  const [position,setPosition] = useState(first < 0 ? order.length - 1 : first);
  const [open,setOpen] = useState(() => noBlanks(item.card_type));
  const [selected,setSelected] = useState<Grade>();
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [stale,setStale] = useState(false);
  const pending = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const active = order[position];

  function move(index: number) {
    setPosition(index);
    setSelected(undefined);
    setOpen(noBlanks(item.card_type));
    setError('');
    heading.current?.focus({preventScroll:true});
    window.scrollTo({top:0});
  }

  async function save(grade: Grade) {
    if (pending.current || stale) return;
    pending.current = true;
    setSelected(grade);
    setBusy(true);
    setError('');
    try {
      const response = await api<Assignment>('evaluate',{
        target_id:item.target_id, card_id:item.card_id, day:item.day, version:item.version,
        revision:item.revision, grades:{[active]:grade},
        finish:order.every(hole => hole === active || item.grades[hole] !== undefined),
      });
      onSave(response);
      if (!response.completed_at) {
        const next = order.findIndex(hole => response.grades[hole] === undefined);
        move(next < 0 ? position : next);
      }
    } catch (err) {
      setError(message(err));
      setStale(err instanceof StudyError && err.code === '40001');
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return <section aria-label="出題カード">
    <p className="step-line">{active ? `穴 ${position+1} / ${order.length}` : 'カード単位'} · {order.filter(key => item.grades[key] !== undefined).length}件 保存済み</p>
    <Question title={item.title} category={item.category} rank={item.rank} layout={item.layout}
      kind={item.card_type} answer={item.answer} hole={active} open={open} heading={heading}/>
    {error && <p role="alert" className="notice">{error}</p>}
    <div className="actions sticky assessment">
      {!open && <button className="primary" onClick={() => setOpen(true)}>答えを見る</button>}
      {open && <RatingButtons number={active ? position+1 : 0} selected={selected ?? item.grades[active]} disabled={busy || stale}
        focusFirst={!noBlanks(item.card_type)} pick={save}/>}
      {busy && <span role="status">保存中…</span>}
      {position > 0 && <button disabled={busy || stale} onClick={() => move(position-1)}>前の穴</button>}
      {stale && <button onClick={() => void onRefresh().catch(err => setError(message(err)))}>最新の内容を開く</button>}
    </div>
  </section>;
}

export type ReviewView = {
  day: string; total: number; completed: number; holes: number; remaining: number; unassigned: number;
  current: Assignment | null; next_review: string | null; retry_count: number; reviewed_sources: {id:string; title:string | null}[];
};
export type Retry = {assignment: Assignment; hole: number; items: Segment[]};

function RetryCard({row,done}: {row: Retry; done: () => Promise<void>}) {
  const [open,setOpen] = useState(false);
  const [error,setError] = useState('');
  const [stored,setStored] = useState(false);
  const [busy,setBusy] = useState(false);
  const pending = useRef(false);
  const order = holeOrder(row.items);
  const number = order.indexOf(row.hole)+1;
  async function finish() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      if (!stored) {
        await api('relearn',{target_id:row.assignment.target_id,day:row.assignment.day,
          version:row.assignment.version,hole:row.hole});
        setStored(true);
      }
      await done();
    } catch (err) {
      setError(message(err));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return <section>
    <h2>{row.assignment.title || '無題'} · 穴 {number}</h2>
    <Prompt layout={contextFor(row.items,row.hole)} open={open} active={row.hole} order={order}/>
    {error && <p role="alert" className="notice">{error}</p>}
    <div className="actions sticky assessment">
      {stored
        ? <button onClick={finish} disabled={busy}>保存済みの内容を更新</button>
        : open ? <RatingButtons number={number} disabled={busy} focusFirst pick={finish}/>
          : <button className="primary" onClick={() => setOpen(true)}>答えを見る</button>}
    </div>
  </section>;
}

function ReviewedSource({id,title}: {id:string;title:string | null}) {
  const [text,setText] = useState<string>();
  const [error,setError] = useState('');
  async function load() {
    setError('');
    try {
      const value = await api<string | null>('review_source',{id});
      if (value === null) throw new Error('この原文は現在参照できません。');
      setText(value);
    }
    catch (err) {setError(message(err));}
  }
  return <details onToggle={event => {if (event.currentTarget.open && text === undefined) void load();}}>
    <summary>{title || '無題'}</summary>
    {text !== undefined && <p className="preserve"><Highlight text={text}/></p>}
    {error && <p role="alert">{error} <button onClick={load}>再読み込み</button></p>}
  </details>;
}

export function DailyPage({review,onSave,load}: {
  review: ReviewView; onSave: (item: Assignment) => void; load: () => Promise<void>;
}) {
  const [retry,setRetry] = useState<Retry | null>();
  const [retryError,setRetryError] = useState('');
  const [fetching,setFetching] = useState(false);
  const [showSources,setShowSources] = useState(false);
  const [refresh,setRefresh] = useState(0);
  const item = review.current;

  async function openRetry() {
    setFetching(true);
    setRetryError('');
    try {setRetry(await api<Retry | null>('review_retry'));}
    catch (err) {setRetryError(message(err));}
    finally {setFetching(false);}
  }

  return <>
    <header className="page-title"><div><h1>本日のノルマ</h1><p>{review.day}</p></div></header>
    <div className="progress-line">
      <progress aria-label="本日の復習進捗" value={review.completed} max={review.total || 1}/>
      <span>{review.completed} / {review.total} 件 · 残り {review.remaining} / {review.holes} 穴</span>
    </div>
    {review.next_review && <p className="muted">前回確定した原文の次回復習日 {review.next_review}</p>}
    {item ? <DailyCard key={`${item.day}:${item.card_id}:${item.version}:${refresh}`} item={item} onSave={onSave}
      onRefresh={async () => {await load();setRefresh(value => value+1);}}/> : <>
      <h2>{review.total ? '本日のノルマ完了' : '今日の割当はありません'}</h2>
      {review.unassigned > 0 && <p>本日の割当に含まれていない期限到来済みの原文が {review.unassigned} 件あります。</p>}
      <div className="actions">
        {(review.retry_count > 0 || retryError) && <button className="primary" disabled={fetching} onClick={() => void openRetry()}>
          △・×を解き直す（{review.retry_count}穴）
        </button>}
        {review.reviewed_sources.length > 0 && <button onClick={() => setShowSources(value => !value)}>
          {showSources ? '原文を閉じる' : '復習した原文を確認'}
        </button>}
      </div>
      {retryError && <p role="alert">{retryError}</p>}
      {retry && <RetryCard key={`${retry.assignment.target_id}:${retry.hole}`} row={retry} done={async () => {
        await load();
        setRetry(await api<Retry | null>('review_retry'));
      }}/>}
      {retry === null && <p role="status">解き直しが完了しました。</p>}
      {showSources && review.reviewed_sources.map(source => <ReviewedSource key={source.id} {...source}/>)}
    </>}
  </>;
}

export function PracticeCard({item,onGrade,recorded}: {item: PracticeItem; onGrade: (values: Scores) => void; recorded?: Written}) {
  const [open,setOpen] = useState(() => noBlanks(item.cardType));
  const [index,setIndex] = useState(0);
  const [values,setValues] = useState<Scores>({});
  const busy = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const order = holeOrder(item.layout);
  const current = order[index];

  useEffect(() => {busy.current = false;},[index]);

  function move(next: number) {
    setIndex(next);
    setOpen(noBlanks(item.cardType));
    heading.current?.focus({preventScroll:true});
    window.scrollTo({top:0});
  }

  function choose(grade: Grade) {
    if (busy.current) return;
    busy.current = true;
    const next = {...values,[current]:grade};
    setValues(next);
    if (index+1 === order.length) onGrade(next);
    else move(index+1);
  }

  return <section aria-label="出題カード">
    <p className="step-line">{current ? `穴 ${index+1} / ${order.length}` : 'カード単位'}</p>
    <Question title={item.title} category={item.category} rank={item.rank} layout={item.layout}
      kind={item.cardType} answer={item.answer} hole={current} open={open} heading={heading}/>
    {open && recorded && <p className="plain-answer preserve">記入した答え　{recorded[current] || '未記入'}</p>}
    <div className="actions sticky assessment">
      {open ? <RatingButtons number={current ? index+1 : 0} disabled={false} selected={values[current]}
        focusFirst={!noBlanks(item.cardType)} pick={choose}/>
        : <button className="primary" onClick={() => setOpen(true)}>答えを見る</button>}
      {index > 0 && <button onClick={() => move(index-1)}>前の穴</button>}
    </div>
  </section>;
}
