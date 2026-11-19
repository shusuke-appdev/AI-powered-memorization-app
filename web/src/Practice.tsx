import {useEffect, useRef, useState} from 'react';
import {api, message} from './api.ts';
import {defaults, holes, noBlanks, onlyHoles, practiceCandidates, ranks, shuffle, subjects, types} from './cards.ts';
import type {Filters, Library, PracticeItem, Preset} from './cards.ts';
import {contextFor, holeOrder, PracticeCard, Prompt} from './Study.tsx';
import type {Scores, Written} from './Study.tsx';
import {confirmDiscard} from './navigation.ts';
import {useStudyQuery} from './query.ts';

const modes = {range:'範囲指定', priority:'重要カード', weak:'苦手克服', test:'ミニテスト'} as const;
const batchSize = 20;

function FilterList({label, options, values, change}: {
  label:string; options:string[]; values:string[]; change:(values:string[]) => void;
}) {
  return <fieldset className="filter-list">
    <legend>{label}</legend>
    <div className="choices">{options.map(value => <label key={value}>
      <input type="checkbox" checked={values.includes(value)}
        onChange={event => change(event.target.checked ? [...values,value] : values.filter(old => old !== value))}/>
      {value}
    </label>)}</div>
  </fieldset>;
}

type PracticeOptions = {tags: {category:string;tag:string}[]; presets:Preset[]};
type Run = {
  ids:string[]; filters:Filters; phase:'answer'|'grade'|'results'|'retry'; index:number;
  written:Record<string,Written>; scores:Record<string,Scores>;
};
type SetDirty = (value:boolean) => void;

function TestQuestion({item,index,length,onNext}: {
  item:PracticeItem; index:number; length:number; onNext:(response:Written) => void;
}) {
  const order = holeOrder(item.layout);
  const [position,setPosition] = useState(0);
  const [responses,setResponses] = useState<Written>({});
  const hole = order[position];
  return <section aria-label="出題カード">
    <div className="card-heading">
      <div><span className="category">{item.category}</span><h2>{item.title}</h2></div>
      <span className="rank">{item.rank}</span>
    </div>
    {hole > 0 && <p className="step-line">穴 {position+1} / {order.length}</p>}
    <Prompt layout={contextFor(item.layout,hole)} open={false} active={hole} whole={noBlanks(item.cardType)} order={order}/>
    <label className="field">思い出した答え（任意）
      <textarea rows={3} value={responses[hole] ?? ''} onChange={event => {
        setResponses({...responses,[hole]:event.target.value});
      }}/>
    </label>
    <div className="actions sticky">
      {position > 0 && <button onClick={() => setPosition(position-1)}>前の穴</button>}
      <button className="primary" onClick={() => {
        if (position+1 === order.length) onNext(responses);
        else {setPosition(position+1);window.scrollTo({top:0});}
      }}>{position+1 < order.length ? '次の穴' : index+1 === length ? '全問の解答を確定' : '次の問題'}</button>
    </div>
  </section>;
}

export function PracticePage({setDirty}: {setDirty:SetDirty}) {
  const [filters,setFilters] = useState<Filters>(defaults);
  const [preset,setPreset] = useState('');
  const [name,setName] = useState('');
  const [run,setRun] = useState<Run | null>(null);
  const [items,setItems] = useState<Record<string,PracticeItem>>({});
  const [loaded,setLoaded] = useState<number[]>([]);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [busy,setBusy] = useState(false);
  const presetRequest = useRef<{payload:string;key:string} | undefined>(undefined);
  const saving = useRef(false);
  const options = useStudyQuery<PracticeOptions>('practice_options');
  const search = useStudyQuery<string[]>('practice_search',filters,!run,filters.query ? 220 : 0);
  const batch = Math.floor((run?.index ?? 0)/batchSize);
  const reading = !!run && (run.phase === 'answer' || run.phase === 'grade') && !loaded.includes(batch);
  const page = useStudyQuery<Library>('practice_page',{
    ids:run?.ids.slice(batch*batchSize,(batch+1)*batchSize) ?? [],filters:run?.filters ?? defaults,
  },reading);

  useEffect(() => {
    if (!page.data || !run) return;
    const results = practiceCandidates(page.data,run.filters);
    setItems(old => ({...old,...Object.fromEntries(results.map(item => [item.id,item]))}));
    setLoaded(old => old.includes(batch) ? old : [...old,batch]);
  },[batch,page.data,run]);

  useEffect(() => {
    setDirty(!!run && run.phase !== 'results');
    return () => setDirty(false);
  },[run?.phase,setDirty]);

  const tags = [...new Set([
    ... (options.data?.tags ?? []).filter(row => !filters.subjects.length || filters.subjects.includes(row.category)).map(row => row.tag),
    ...filters.tags,
  ])].sort((a,b) => a.localeCompare(b,'ja'));

  async function savePreset(remove = false) {
    if (saving.current) return;
    saving.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const payload = {id:preset || undefined,name,filters};
      const signature = JSON.stringify([remove,payload]);
      if (presetRequest.current?.payload !== signature) {
        presetRequest.current={payload:signature,key:crypto.randomUUID()};
      }
      await api(remove ? 'delete_preset' : 'preset',{...payload,request_id:presetRequest.current.key});
      presetRequest.current=undefined;
      options.refresh();
      setNotice(remove ? '条件を削除しました。' : '条件を保存しました。');
      if (remove) {setPreset('');setName('');}
    } catch (err) {
      setError(message(err));
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  function filter<K extends keyof Filters>(key: K,value: Filters[K]) {
    setFilters(current => ({...current,[key]:value}));
  }

  function start() {
    if (!search.data?.length) return;
    const ordered = filters.mode === 'test' ? shuffle(search.data) : search.data;
    const ids = filters.limit ? ordered.slice(0,filters.limit) : ordered;
    setLoaded([]);
    setItems({});
    setRun({ids,filters,phase:filters.mode === 'test' ? 'answer':'grade',index:0,written:{},scores:{}});
    window.scrollTo({top:0});
  }

  if (run) {
    const rowId = run.ids[run.index];
    const item = items[rowId];
    const weak = run.ids.flatMap(id => {
      const row = items[id];
      const scores = run.scores[id];
      if (!row || !scores) return [];
      const selected = holes(row.layout).filter(hole => [0,2].includes(scores[hole.hole])).map(hole => hole.hole);
      if (!selected.length && ![0,2,3].includes(scores[0])) return [];
      return [{...row,layout:selected.length ? onlyHoles(row.layout,selected) : row.layout}];
    });
    const tally = Object.values(run.scores).flatMap(scores => Object.values(scores));

    function proceed(next: Run) {
      const last = next.index+1 >= next.ids.length;
      setRun(last ? {...next,index:0,phase:next.phase === 'answer' ? 'grade':'results'} : {...next,index:next.index+1});
      window.scrollTo({top:0});
    }

    return <>
      <header className="page-title"><div><h1>{modes[run.filters.mode]}</h1>
        {run.phase !== 'results' && <p>{run.phase === 'retry' ? '解き直し' : run.phase === 'answer' ? '解答' : '自己採点'} · {run.index+1} / {run.phase === 'retry' ? weak.length : run.ids.length} 件</p>}
      </div><button onClick={() => {
        if (run.phase === 'results' || confirmDiscard()) setRun(null);
      }}>条件に戻る</button></header>
      {reading && !page.error && <p role="status">出題を読み込み中…</p>}
      {page.error && <p role="alert">{page.error} <button onClick={page.refresh}>再読み込み</button></p>}
      {!reading && !item && (run.phase === 'answer' || run.phase === 'grade') &&
        <p role="status">このカードは別の画面で変更されました。 <button onClick={() => proceed(run)}>次へ</button></p>}
      {!reading && item && run.phase === 'answer' && <TestQuestion key={rowId} item={item} index={run.index} length={run.ids.length}
        onNext={response => proceed({...run,written:{...run.written,[rowId]:response}})}/>}
      {!reading && item && run.phase === 'grade' && <PracticeCard key={`grade-${rowId}`} item={item}
        recorded={run.filters.mode === 'test' ? run.written[rowId] : undefined}
        onGrade={scores => proceed({...run,scores:{...run.scores,[rowId]:scores}})}/>}
      {run.phase === 'results' && <section>
        <h2>{Object.keys(run.scores).length}件の演習が完了しました</h2>
        <p>◯ {tally.filter(grade => grade >= 4).length}　△ {tally.filter(grade => grade === 2 || grade === 3).length}　× {tally.filter(grade => grade === 0).length}</p>
        {weak.length > 0 && <>
          <h3>今回の弱点</h3>
          <ul>{weak.map(row => <li key={row.id}>{row.title}{holes(row.layout).length > 0 && ` · 穴 ${holes(row.layout).map(part => part.hole).join('、')}`}</li>)}</ul>
          <button className="primary" onClick={() => setRun({...run,phase:'retry',index:0})}>今回の弱点を解き直す</button>
        </>}
      </section>}
      {run.phase === 'retry' && weak[run.index] && <PracticeCard key={`retry-${weak[run.index].id}`} item={weak[run.index]}
        onGrade={() => {
          const finished = run.index+1 === weak.length;
          setRun({...run,phase:finished ? 'results':'retry',index:finished ? 0:run.index+1});
          window.scrollTo({top:0});
        }}/>}
    </>;
  }

  return <>
    <header className="page-title"><div><h1>自由演習</h1><p>復習日や日次ノルマを変えずに練習します。</p></div></header>
    <section>
      <fieldset className="mode-switch"><legend>演習の目的</legend><div className="mode-options">
        {Object.entries(modes).map(([value,label]) => <button key={value} aria-pressed={filters.mode === value}
          onClick={() => filter('mode',value as Filters['mode'])}>{label}</button>)}
      </div></fieldset>
      <details className="preset-panel">
        <summary>保存した条件</summary>
        <label className="field">呼び出す条件<select value={preset} onChange={event => {
          const value = options.data?.presets.find(row => row.id === event.target.value);
          setPreset(value?.id ?? '');
          setName(value?.name ?? '');
          if (value) setFilters({...defaults,...value.filters});
        }}>
          <option value="">新しい条件</option>
          {options.data?.presets.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label>
        <label className="field">条件名<input value={name} onChange={event => setName(event.target.value)} maxLength={80}/></label>
        <div className="actions">
          <button disabled={busy || !name.trim()} onClick={() => void savePreset()}>条件を保存</button>
          {preset && <button disabled={busy} onClick={() => void savePreset(true)}>条件を削除</button>}
        </div>
        {options.error && <p role="alert">{options.error} <button onClick={options.refresh}>再読み込み</button></p>}
        {error && <p role="alert" className="notice">{error}</p>}
        {notice && <p role="status">{notice}</p>}
      </details>
      <label className="field">出題数
        <select value={filters.limit} onChange={event => filter('limit',Number(event.target.value))}>
          {[5,10,20,0].map(value => <option key={value} value={value}>{value ? `${value}件` : '全件'}</option>)}
        </select>
      </label>
      <FilterList label="科目" options={subjects} values={filters.subjects} change={value => filter('subjects',value)}/>
      <FilterList label="重要度" options={ranks} values={filters.ranks} change={value => filter('ranks',value)}/>
      <details className="advanced-filters">
        <summary>詳細条件</summary>
        {tags.length > 0 && <FilterList label="分野タグ" options={tags} values={filters.tags} change={value => filter('tags',value)}/>}
        <FilterList label="タイプ" options={types} values={filters.types} change={value => filter('types',value)}/>
        <label className="field">キーワード<input type="search" value={filters.query} onChange={event => filter('query',event.target.value)}/></label>
        <label className="flag"><input type="checkbox" checked={filters.favorite} onChange={event => filter('favorite',event.target.checked)}/>お気に入りだけ</label>
      </details>
      {search.error && <p role="alert" className="notice">{search.error} <button onClick={search.refresh}>再読み込み</button></p>}
      <div className="actions sticky practice-start">
        <span role="status">{search.loading ? '該当件数を確認中…'
          : search.data?.length ? `${search.data.length}件が該当` : search.error ? '' : '該当なし · 条件を緩めてください'}</span>
        <button className="primary" disabled={!search.data?.length} onClick={start}>演習を開始</button>
        <button onClick={() => {setFilters(defaults);setPreset('');setName('');}}>条件をリセット</button>
      </div>
    </section>
  </>;
}
