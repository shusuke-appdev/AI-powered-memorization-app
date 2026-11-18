import {useState} from 'react';
import {api, message} from './api.ts';
import {generate, matchesVariant, noBlanks, ranks, subjects, tagsFrom, types, variantFromLayout} from './cards.ts';
import type {Card, Library, Segment, Source, Variant} from './cards.ts';
import {Highlight, Prompt} from './Study.tsx';

const PAGE_SIZE = 20;

type Metadata = {title: string; category: string; card_type: string; rank: string; tags: string};
type Edit = {source?: Source; orphan?: Card};

function SelectField({label, choices, value, change}: {label: string; choices: string[]; value: string; change: (value:string) => void}) {
  return <label className="field">{label}
    <select value={value} onChange={event => change(event.target.value)}>
      {choices.map(option => <option key={option}>{option}</option>)}
    </select>
  </label>;
}

function metadata(edit: Edit, linked: Card[]): Metadata {
  const item = edit.source ?? edit.orphan;
  const rank = edit.orphan?.rank ?? ranks.find(rank => linked.some(card => rank === card.rank));
  return {
    title:item?.title ?? '', category:item?.category ?? 'その他', card_type:item?.card_type ?? '規範',
    rank:rank ?? 'B', tags:item?.study_tags.join('、') ?? '',
  };
}

export function CardEditor({edit, library, done, cancel}: {
  edit: Edit; library: Library; done: (notice: string) => Promise<void>; cancel: () => void;
}) {
  const {source,orphan} = edit;
  const linked = library.cards.filter(card => card.source_id === source?.id && !card.study_archived_at);
  const [meta,setMeta] = useState(() => metadata(edit,linked));
  const [text,setText] = useState(source?.source_text ?? orphan?.question ?? '');
  const [answer,setAnswer] = useState(orphan?.answer ?? '');
  const [draft,setDraft] = useState<Variant[]>([]);
  const [requestId,setRequestId] = useState('');
  const [index,setIndex] = useState(0);
  const [editing,setEditing] = useState(false);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [archive,setArchive] = useState(false);
  const tags = [...new Set([
    ...library.sources.filter(item => item.category === meta.category).flatMap(item => item.study_tags),
    ...library.cards.filter(card => !card.source_id && !card.study_archived_at && card.category === meta.category).flatMap(card => card.study_tags),
  ])].sort((a,b) => a.localeCompare(b,'ja'));

  function field<K extends keyof Metadata>(key: K,value: Metadata[K]) {
    setMeta(current => ({...current,[key]:value}));
  }

  function regenerate() {
    try {
      setDraft(generate(text,meta.card_type));
      setRequestId(crypto.randomUUID());
      setIndex(0);
      setEditing(false);
      setError('');
      window.scrollTo({top:0});
    } catch (err) {
      setError(message(err));
    }
  }

  function replacePart(position: number, part: Segment) {
    setDraft(list => list.map((card,i) => i === index
      ? variantFromLayout(card.layout.map((old,j) => j === position ? part : old)) : card));
  }

  async function save(mode: 'archive' | 'save_orphan' | 'save_bundle' | 'source_metadata') {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const item = source ?? orphan;
      const info = {...meta,tags:tagsFrom(meta.tags),id:item?.id,version:item?.study_version};
      if (mode === 'archive') {
        await api(mode,{...info,source:!!source});
      } else if (mode === 'save_orphan') {
        await api(mode,{...info,question:text,answer});
      } else if (mode === 'source_metadata') {
        await api(mode,info);
      } else {
        await api(mode,{...info,source_text:text,variants:draft,request_id:requestId});
      }
      await done(mode === 'archive' ? '参照用に保管しました。' : '保存しました。');
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  if (draft.length) {
    const used = new Set<string>();
    for (const variant of draft) {
      const same = linked.find(card => !used.has(card.id) && matchesVariant(card,variant,meta.card_type));
      if (same) used.add(same.id);
    }
    const current = draft[index];
    const editableLayout = current.layout.every(part => typeof part === 'string' || part.answer.trim());
    const canSave = editableLayout && draft.every(card => card.question.trim() && card.layout.every(part => typeof part === 'string' || part.answer.trim()));
    return <section>
      <header className="page-title"><div><h1>{source ? '再生成プレビュー' : 'カードのプレビュー'}</h1><p>{meta.title || '無題'}</p></div></header>
      <div className="actions top-actions">
        <button className="primary" disabled={!canSave || busy} onClick={() => void save('save_bundle')}>
          {busy ? '保存中…' : `全${draft.length}枚を保存`}
        </button>
        <button disabled={busy} onClick={() => {setDraft([]);setError('');}}>編集に戻る</button>
      </div>
      <p className="muted">引き継ぎ {used.size} · 新規 {draft.length-used.size} · 参照保管 {linked.length-used.size}</p>
      {error && <p role="alert" className="notice">{error}</p>}
      <div className="actions">
        <button disabled={!index} onClick={() => setIndex(index-1)}>前のカード</button>
        <span>{index+1} / {draft.length} 枚 · {current.blank_count}穴</span>
        <button disabled={index+1 === draft.length} onClick={() => setIndex(index+1)}>次のカード</button>
        <button onClick={() => setEditing(value => !value)}>{editing ? '編集欄を閉じる' : '表示中のカードを編集'}</button>
      </div>
      <Prompt layout={current.layout} open={true} whole={noBlanks(meta.card_type)}/>
      {editing && <div className="parts-editor">{current.layout.map((part,i) =>
        <label className="field" key={i}>{typeof part === 'string' ? `本文 ${i+1}` : `穴 ${part.hole} の答え`}
          <textarea rows={typeof part === 'string' ? 3 : 1} value={typeof part === 'string' ? part : part.answer}
            onChange={event => replacePart(i,typeof part === 'string' ? event.target.value : {...part,answer:event.target.value})}/>
        </label>,
      )}</div>}
    </section>;
  }

  const onlyMetadata = !!source && text === source.source_text && meta.card_type === source.card_type;
  return <section>
    <header className="page-title"><div><h1>{source || orphan ? 'カードを編集' : 'カードを追加'}</h1></div>
      <button disabled={busy} onClick={cancel}>一覧に戻る</button></header>
    <label className="field">タイトル<input value={meta.title} onChange={event => field('title',event.target.value)}/></label>
    <div className="fieldset-grid">
      <SelectField label="科目" choices={subjects} value={meta.category} change={value => field('category',value)}/>
      <SelectField label="タイプ" choices={types} value={meta.card_type} change={value => field('card_type',value)}/>
      <SelectField label="重要度" choices={ranks} value={meta.rank} change={value => field('rank',value)}/>
    </div>
    <label className="field">分野タグ（読点で区切る）
      <input value={meta.tags} onChange={event => field('tags',event.target.value)}/>
    </label>
    {!!tags.length && <div className="choices">
      {tags.map(tag => <button type="button" key={tag} onClick={() => field('tags',[...new Set([...tagsFrom(meta.tags),tag])].join('、'))}>{tag}</button>)}
    </div>}
    <label className="field">{orphan ? '問題・本文' : '原文'}
      <textarea rows={10} value={text} onChange={event => setText(event.target.value)}/>
    </label>
    {!orphan && <p className="muted">穴埋めにする語句を【】で囲みます。類型・知識では同じ記号で強調箇所を指定できます。</p>}
    {orphan && !noBlanks(meta.card_type) && <label className="field">答え
      <textarea rows={4} value={answer} onChange={event => setAnswer(event.target.value)}/>
    </label>}
    <div className="actions sticky">
      {orphan ? <button className="primary" disabled={busy} onClick={() => void save('save_orphan')}>保存</button>
        : <button className="primary" onClick={regenerate}>{source ? '再生成プレビュー' : 'カードを生成'}</button>}
      {onlyMetadata && <button disabled={busy} onClick={() => void save('source_metadata')}>分類・タイトルを保存</button>}
      {(orphan || source) && <button onClick={() => setArchive(value => !value)}>カードを保管</button>}
    </div>
    {archive && <div className="notice">
      <p>通常の演習から外し、内容と履歴を参照用に保管します。</p>
      <button disabled={busy} onClick={() => void save('archive')}>保管する</button>
    </div>}
    {error && <p role="alert" className="notice">{error}</p>}
  </section>;
}

export function ManagePage({library, reload, add}: {library: Library; reload: () => Promise<void>; add?: boolean}) {
  const [edit,setEdit] = useState<Edit | null>(add ? {} : null);
  const [query,setQuery] = useState('');
  const [subject,setSubject] = useState('');
  const [type,setType] = useState('');
  const [sort,setSort] = useState('title');
  const [page,setPage] = useState(0);
  const [archived,setArchived] = useState(false);
  const [notice,setNotice] = useState('');
  const [error,setError] = useState('');
  const [changing,setChanging] = useState('');
  const needle = query.trim().toLowerCase();
  const active = library.cards.filter(card => !card.study_archived_at);
  const groups = new Map<string, Card[]>();
  for (const card of active) {
    if (!card.source_id) continue;
    const group = groups.get(card.source_id) ?? [];
    group.push(card);
    groups.set(card.source_id,group);
  }
  const items = [
    ...library.sources.map(source => {
      const cards = groups.get(source.id) ?? [];
      const rank = ranks.find(rank => cards.some(card => card.rank === rank)) ?? 'B';
      return {
        item:source, source:true, content:source.source_text, count:cards.length, rank,
        favorite:source.study_favorite || cards.some(card => card.is_favorite),
        search:[source.title,source.source_text,...source.study_tags,...cards.flatMap(card => [card.question,card.answer])],
      };
    }),
    ...active.filter(card => !card.source_id).map(card => ({
      item:card, source:false, content:card.question, count:1, rank:card.rank ?? 'B', favorite:card.is_favorite,
      search:[card.title,card.question,card.answer,...card.study_tags],
    })),
  ].filter(row => (!subject || (row.item.category ?? 'その他') === subject) && (!type || row.item.card_type === type) &&
    (!needle || row.search.some(value => value?.toLowerCase().includes(needle))));
  const dates = new Map(library.targets.map(target => [target.id,target.next_review]));
  items.sort((a,b) => {
    const byTitle = (a.item.title ?? a.content).localeCompare(b.item.title ?? b.content,'ja');
    if (sort === 'rank') return ranks.indexOf(a.rank)-ranks.indexOf(b.rank) || byTitle;
    if (sort === 'favorite') return Number(b.favorite)-Number(a.favorite) || byTitle;
    if (sort === 'due') return (dates.get(a.item.id) ?? '9999').localeCompare(dates.get(b.item.id) ?? '9999') || byTitle;
    return byTitle;
  });
  const maxPage = Math.max(0,Math.ceil(items.length/PAGE_SIZE)-1);
  const currentPage = Math.min(page,maxPage);

  async function favorite(item: typeof items[number]) {
    setChanging(item.item.id);
    setError('');
    try {
      await api('favorite',{id:item.item.id,source:item.source,favorite:!item.favorite});
      await reload();
    } catch (err) {
      setError(message(err));
    } finally {
      setChanging('');
    }
  }

  if (edit) return <CardEditor edit={edit} library={library} cancel={() => setEdit(null)} done={async text => {
    await reload();
    setNotice(text);
    setEdit(null);
  }}/>;

  const archives = library.cards.filter(card => !!card.study_archived_at);
  return <>
    <header className="page-title"><div><h1>カード管理</h1><p>{items.length}件</p></div>
      <button className="primary" onClick={() => setEdit({})}>カードを追加</button></header>
    {notice && <p role="status" className="notice">{notice}</p>}
    {error && <p role="alert" className="notice">{error}</p>}
    <div className="fieldset-grid">
      <label className="field">キーワード<input type="search" value={query} onChange={event => {setQuery(event.target.value);setPage(0);}}/></label>
      <label className="field">科目<select value={subject} onChange={event => {setSubject(event.target.value);setPage(0);}}>
        <option value="">全科目</option>{subjects.map(value => <option key={value}>{value}</option>)}
      </select></label>
      <label className="field">タイプ<select value={type} onChange={event => {setType(event.target.value);setPage(0);}}>
        <option value="">全タイプ</option>{types.map(value => <option key={value}>{value}</option>)}
      </select></label>
      <label className="field">並び順<select value={sort} onChange={event => {setSort(event.target.value);setPage(0);}}>
        <option value="title">50音順</option><option value="favorite">お気に入り優先</option>
        <option value="rank">重要度順</option><option value="due">復習日が近い順</option>
      </select></label>
    </div>
    <ul className="library-list">
      {items.slice(currentPage*PAGE_SIZE,(currentPage+1)*PAGE_SIZE).map(row => <li key={row.item.id}>
        <div><span className="category">{row.item.category || 'その他'}</span>
          <h2>{row.item.title || row.content.slice(0,40) || '無題'}</h2>
          <p>{row.rank} · {row.item.card_type ?? '旧形式'} · {row.count}枚
            {row.item.study_tags.length > 0 && ` · ${row.item.study_tags.join('、')}`}</p>
        </div>
        <div className="actions">
          <button disabled={changing === row.item.id} onClick={() => void favorite(row)}>{row.favorite ? '★ お気に入り' : '☆ お気に入り'}</button>
          <button onClick={() => setEdit(row.source ? {source:row.item as Source} : {orphan:row.item as Card})}>編集</button>
        </div>
      </li>)}
    </ul>
    {items.length === 0 && <p>条件に一致するカードがありません。</p>}
    {maxPage > 0 && <div className="actions">
      <button disabled={!currentPage} onClick={() => setPage(currentPage-1)}>前のページ</button>
      <span>{currentPage+1} / {maxPage+1}</span>
      <button disabled={currentPage >= maxPage} onClick={() => setPage(currentPage+1)}>次のページ</button>
    </div>}
    {archives.length > 0 && <section className="secondary-section">
      <button onClick={() => setArchived(value => !value)}>参照用カード（{archives.length}枚）</button>
      {archived && archives.map(card => <ArchivedCard key={card.id} card={card}/>)}
    </section>}
  </>;
}

function ArchivedCard({card}: {card: Card}) {
  const [history,setHistory] = useState<{recent:{day:string;grades:Record<string,number>}[];
    legacy:{assignment_date:string;quality:number | null}[]} | null>(null);
  const [error,setError] = useState('');
  return <details onToggle={event => {
    if (!event.currentTarget.open || history) return;
    setError('');
    void api<NonNullable<typeof history>>('card_history',{id:card.id}).then(setHistory).catch(err => setError(message(err)));
  }}>
    <summary>{card.title || '無題'} · {card.rank ?? 'B'}</summary>
    <p className="preserve"><Highlight text={card.question}/></p>
    {card.answer && <p className="preserve">{card.answer}</p>}
    {error && <p role="alert">{error}</p>}
    {history && <ul>
      {history.recent.map(record => <li key={record.day}>{record.day}　
        {Object.entries(record.grades).map(([slot,grade]) => `${slot === '0' ? 'カード' : `穴${slot}`} ${grade === 0 ? '×' : grade < 4 ? '△' : '◯'}`).join('、')}
      </li>)}
      {history.legacy.filter(record => !history.recent.some(other => other.day === record.assignment_date))
        .map((record,i) => <li key={`${record.assignment_date}-${i}`}>{record.assignment_date}　旧形式の評価 {record.quality ?? '記録なし'}</li>)}
    </ul>}
  </details>;
}
