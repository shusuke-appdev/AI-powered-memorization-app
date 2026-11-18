import {useMemo, useState} from 'react';
import {api, message} from './api.ts';
import {defaults, holes, noBlanks, onlyHoles, practiceCandidates, ranks, sections, shuffle, subjects, types} from './cards.ts';
import type {Filters, Library, PracticeItem} from './cards.ts';
import {PracticeCard, Prompt} from './Study.tsx';
import type {Scores} from './Study.tsx';

const modes = {range:'範囲指定', priority:'重要カード', weak:'苦手克服', test:'ミニテスト'} as const;

function FilterList({label, options, values, change}: {
  label: string; options: string[]; values: string[]; change: (values: string[]) => void;
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

type Run = {
  items: PracticeItem[]; mode: Filters['mode']; phase: 'answer' | 'grade' | 'results' | 'retry';
  index: number; written: string[]; scores: Scores[];
};

function TestQuestion({item,index,length,onNext}: {
  item: PracticeItem; index: number; length: number; onNext: (response: string) => void;
}) {
  const parts = sections(item.layout);
  const [section,setSection] = useState(0);
  const [responses,setResponses] = useState<string[]>([]);
  return <section>
    <div className="card-heading"><div><span className="category">{item.category}</span><h2>{item.title}</h2></div><span className="rank">{item.rank}</span></div>
    {parts.length > 1 && <p className="muted">区切り {section+1} / {parts.length}</p>}
    <Prompt layout={parts[section]} open={false} whole={noBlanks(item.cardType)}/>
    <label className="field">思い出した答え（任意）
      <textarea rows={3} value={responses[section] ?? ''} onChange={event => {
        const next = [...responses];
        next[section] = event.target.value;
        setResponses(next);
      }}/>
    </label>
    <div className="actions sticky">
      {section > 0 && <button onClick={() => setSection(section-1)}>前の区切り</button>}
      <button className="primary" onClick={() => {
        if (section+1 === parts.length) onNext(responses.filter(Boolean).join('\n'));
        else {setSection(section+1);window.scrollTo({top:0});}
      }}>{section+1 < parts.length ? '次の区切り' : index + 1 === length ? '全問の解答を確定' : '次の問題'}</button>
    </div>
  </section>;
}

export function PracticePage({library, reload}: {library: Library; reload: () => Promise<void>}) {
  const [filters,setFilters] = useState<Filters>(defaults);
  const [preset,setPreset] = useState('');
  const [name,setName] = useState('');
  const [run,setRun] = useState<Run | null>(null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const candidates = useMemo(() => practiceCandidates(library,filters),[library,filters]);
  const selectedSubjects = new Set(filters.subjects);
  const tags = [...new Set([
    ...library.sources.filter(source => !selectedSubjects.size || selectedSubjects.has(source.category ?? 'その他')).flatMap(source => source.study_tags),
    ...library.cards.filter(card => !card.source_id && !card.study_archived_at &&
      (!selectedSubjects.size || selectedSubjects.has(card.category ?? 'その他'))).flatMap(card => card.study_tags),
    ...filters.tags,
  ])].sort((a,b) => a.localeCompare(b,'ja'));

  async function savePreset(remove = false) {
    setBusy(true);
    setError('');
    try {
      await api(remove ? 'delete_preset' : 'preset', {id:preset || undefined,name,filters});
      await reload();
      if (remove) {setPreset('');setName('');}
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  function filter<K extends keyof Filters>(key: K,value: Filters[K]) {
    setFilters(current => ({...current,[key]:value}));
  }

  function start() {
    const ordered = filters.mode === 'test' ? shuffle(candidates) : candidates;
    const items = filters.limit ? ordered.slice(0,filters.limit) : ordered;
    setRun({items,mode:filters.mode,phase:filters.mode === 'test' ? 'answer':'grade',index:0,written:[],scores:[]});
    window.scrollTo({top:0});
  }

  if (run) {
    const item = run.items[run.index];
    const weak = run.items.flatMap((row,i) => {
      const scores = run.scores[i];
      if (!scores) return [];
      const selected = holes(row.layout).filter(hole => [0,2].includes(scores[hole.hole])).map(hole => hole.hole);
      if (!selected.length && ![0,2,3].includes(scores[0])) return [];
      return [{...row,layout:selected.length ? onlyHoles(row.layout,selected) : row.layout}];
    });
    const tally = run.scores.flatMap(scores => Object.values(scores));

    return <>
      <header className="page-title"><div><h1>{modes[run.mode]}</h1>
        {run.phase !== 'results' && <p>{run.phase === 'retry' ? '解き直し' : run.phase === 'answer' ? '解答' : '自己採点'} · {run.index + 1} / {run.phase === 'retry' ? weak.length : run.items.length} 件</p>}
      </div><button onClick={() => setRun(null)}>条件に戻る</button></header>
      {run.phase === 'answer' && <TestQuestion key={item.id} item={item} index={run.index} length={run.items.length}
        onNext={response => {
          const written = [...run.written,response];
          setRun(run.index + 1 === run.items.length
            ? {...run,written,index:0,phase:'grade'} : {...run,written,index:run.index+1});
          window.scrollTo({top:0});
        }}/>}
      {run.phase === 'grade' && <PracticeCard key={`grade-${item.id}`} item={item}
        recorded={run.mode === 'test' ? run.written[run.index] : undefined}
        onGrade={scores => {
          const finished = run.index + 1 === run.items.length;
          setRun({...run,scores:[...run.scores,scores],phase:finished ? 'results':'grade',index:finished ? 0:run.index+1});
          window.scrollTo({top:0});
        }}/>}
      {run.phase === 'results' && <section>
        <h2>{run.items.length}件の演習が完了しました</h2>
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
      <div className="fieldset-grid">
        <label className="field">演習の目的
          <select value={filters.mode} onChange={event => filter('mode',event.target.value as Filters['mode'])}>
            {Object.entries(modes).map(([value,label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </label>
        <label className="field">出題数
          <select value={filters.limit} onChange={event => filter('limit',Number(event.target.value))}>
            {[5,10,20,0].map(value => <option key={value} value={value}>{value ? `${value}件` : '全件'}</option>)}
          </select>
        </label>
      </div>
      <FilterList label="科目" options={subjects} values={filters.subjects} change={value => filter('subjects',value)}/>
      {!!tags.length && <FilterList label="分野タグ" options={tags} values={filters.tags} change={value => filter('tags',value)}/>}
      <FilterList label="重要度" options={ranks} values={filters.ranks} change={value => filter('ranks',value)}/>
      <FilterList label="タイプ" options={types} values={filters.types} change={value => filter('types',value)}/>
      <label className="field">キーワード<input type="search" value={filters.query} onChange={event => filter('query',event.target.value)}/></label>
      <label className="flag"><input type="checkbox" checked={filters.favorite} onChange={event => filter('favorite',event.target.checked)}/>お気に入りだけ</label>
      <div className="actions sticky">
        <button className="primary" disabled={!candidates.length} onClick={start}>演習を開始</button>
        <span role="status">{candidates.length}件が該当</span>
        <button onClick={() => {setFilters(defaults);setPreset('');setName('');}}>条件をリセット</button>
      </div>
    </section>
    <section className="secondary-section">
      <h2>保存した条件</h2>
      <label className="field">呼び出す条件<select value={preset} onChange={event => {
        const value = library.presets.find(row => row.id === event.target.value);
        setPreset(value?.id ?? '');
        setName(value?.name ?? '');
        if (value) setFilters({...defaults,...value.filters});
      }}>
        <option value="">新しい条件</option>
        {library.presets.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>
      <label className="field">条件名<input maxLength={100} value={name} onChange={event => setName(event.target.value)}/></label>
      <div className="actions">
        <button disabled={busy || !name.trim()} onClick={() => void savePreset()}>条件を保存</button>
        {preset && <button disabled={busy} onClick={() => void savePreset(true)}>条件を削除</button>}
      </div>
      {error && <p role="alert" className="notice">{error}</p>}
    </section>
  </>;
}
