import {useEffect, useRef, useState} from 'react';
import {api, message} from './api.ts';
import {generate, matchesVariant, noBlanks, ranks, subjects, tagsFrom, types, variantFromLayout} from './cards.ts';
import type {Card, Segment, Source, Variant} from './cards.ts';
import {Highlight, Prompt} from './Study.tsx';
import {confirmDiscard} from './navigation.ts';
import {useStudyQuery} from './query.ts';

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

export function CardEditor({edit,cards,tagOptions,done,cancel,setDirty}: {
  edit: Edit; cards: Card[]; tagOptions: {category:string;tag:string}[]; done: (notice:string) => void;
  cancel: () => void; setDirty: (value:boolean) => void;
}) {
  const {source,orphan} = edit;
  const linked = source ? cards.filter(card => card.source_id === source.id && !card.study_archived_at) : [];
  const [meta,setMeta] = useState(() => metadata(edit,linked));
  const [text,setText] = useState(source?.source_text ?? orphan?.question ?? '');
  const [answer,setAnswer] = useState(orphan?.answer ?? '');
  const [draft,setDraft] = useState<Variant[]>([]);
  const [index,setIndex] = useState(0);
  const [editing,setEditing] = useState(false);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [archive,setArchive] = useState(false);
  const pending = useRef(false);
  const request = useRef<{signature:string;id:string} | undefined>(undefined);
  const dirty = draft.length > 0 || JSON.stringify(meta) !== JSON.stringify(metadata(edit,linked))
    || text !== (source?.source_text ?? orphan?.question ?? '') || answer !== (orphan?.answer ?? '');
  useEffect(() => {
    setDirty(dirty);
    return () => setDirty(false);
  },[dirty,setDirty]);
  const tags = tagOptions.filter(row => row.category === meta.category).map(row => row.tag);

  function field<K extends keyof Metadata>(key: K,value: Metadata[K]) {
    setMeta(current => ({...current,[key]:value}));
  }

  function regenerate() {
    try {
      setDraft(generate(text,meta.card_type));
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
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      const item = source ?? orphan;
      const info = {...meta,tags:tagsFrom(meta.tags),id:item?.id,version:item?.study_version};
      const payload = mode === 'archive' ? {...info,source:!!source}
        : mode === 'save_orphan' ? {...info,question:text,answer}
          : mode === 'source_metadata' ? info
            : {...info,source_text:text,variants:draft};
      const signature = JSON.stringify([mode,payload]);
      if (request.current?.signature !== signature) request.current={signature,id:crypto.randomUUID()};
      await api(mode,{...payload,request_id:request.current.id});
      setDirty(false);
      done(mode === 'archive' ? '参照用に保管しました。' : '保存しました。');
    } catch (err) {
      setError(message(err));
    } finally {
      pending.current = false;
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
          <textarea disabled={busy} rows={typeof part === 'string' ? 3 : 1} value={typeof part === 'string' ? part : part.answer}
            onChange={event => replacePart(i,typeof part === 'string' ? event.target.value : {...part,answer:event.target.value})}/>
        </label>,
      )}</div>}
    </section>;
  }

  const onlyMetadata = !!source && text === source.source_text && meta.card_type === source.card_type;
  return <section>
    <header className="page-title"><div><h1>{source || orphan ? 'カードを編集' : 'カードを追加'}</h1></div>
      <button disabled={busy} onClick={() => {if (!dirty || confirmDiscard()) cancel();}}>一覧に戻る</button></header>
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

type ManageRow = {
  id:string; source:boolean; title:string | null; category:string | null; card_type:string | null;
  study_tags:string[]; caption:string; card_count:number; rank:string; favorite:boolean;
};
type Listing = {total:number; archives:number; items:ManageRow[]};
type Detail = {source:Source | null; cards:Card[]};
type Archive = {id:string; title:string | null; rank:string | null};
type History = {recent:{day:string;grades:Record<string,number>}[];legacy:{assignment_date:string;quality:number | null}[]};

function Pages({page,total,change}: {page:number;total:number;change:(value:number) => void}) {
  const pages = Math.ceil(total/PAGE_SIZE);
  return pages > 1 && <div className="actions pagination">
    <button disabled={!page} onClick={() => change(page-1)}>前のページ</button>
    <span>{page+1} / {pages}</span>
    <button disabled={page+1 >= pages} onClick={() => change(page+1)}>次のページ</button>
  </div>;
}

export function ManagePage({add,setDirty}: {add?:boolean;setDirty:(value:boolean) => void}) {
  const [selection,setSelection] = useState<{id:string;source:boolean} | 'new' | null>(add ? 'new' : null);
  const [query,setQuery] = useState('');
  const [subject,setSubject] = useState('');
  const [type,setType] = useState('');
  const [sort,setSort] = useState('title');
  const [page,setPage] = useState(0);
  const [archivePage,setArchivePage] = useState(0);
  const [archived,setArchived] = useState(false);
  const [notice,setNotice] = useState('');
  const [error,setError] = useState('');
  const [changing,setChanging] = useState('');
  const pending = useRef(false);
  const list = useStudyQuery<Listing>('manage_list',{query,subject,type,sort,offset:page*PAGE_SIZE},!add,query ? 220 : 0);
  const archives = useStudyQuery<Archive[]>('archive_list',{offset:archivePage*PAGE_SIZE},archived && !selection);
  const detail = useStudyQuery<Detail>('manage_detail',{id:selection && selection !== 'new' ? selection.id : null},!!selection && selection !== 'new');
  const options = useStudyQuery<{tags:{category:string;tag:string}[]}>('practice_options',{},!!selection);
  const total = list.data?.total;
  useEffect(() => {
    if (total !== undefined && page > 0 && page*PAGE_SIZE >= total) {
      setPage(Math.max(0,Math.ceil(total/PAGE_SIZE)-1));
    }
  },[page,total]);

  async function favorite(item: ManageRow) {
    if (pending.current) return;
    pending.current = true;
    setChanging(item.id);
    setError('');
    try {
      await api('favorite',{id:item.id,source:item.source,favorite:!item.favorite,request_id:crypto.randomUUID()});
      list.refresh();
    } catch (err) {
      setError(message(err));
    } finally {
      pending.current = false;
      setChanging('');
    }
  }

  if (selection) {
    if (selection !== 'new' && !detail.data) return <>
      {detail.loading && <p role="status">原文とカードを読み込み中…</p>}
      {detail.error && <p role="alert">{detail.error} <button onClick={detail.refresh}>再読み込み</button></p>}
      <button onClick={() => setSelection(null)}>一覧に戻る</button>
    </>;
    const row = detail.data;
    const edit: Edit = selection === 'new' ? {} : selection.source
      ? {source:row?.source ?? undefined} : {orphan:row?.cards[0]};
    if (selection !== 'new' && !edit.source && !edit.orphan) return <p role="alert">このカードは変更されています。 <button onClick={() => {
      setSelection(null);list.refresh();
    }}>一覧に戻る</button></p>;
    return <CardEditor key={selection === 'new' ? 'new' : selection.id} edit={edit} cards={row?.cards ?? []}
      tagOptions={options.data?.tags ?? []} setDirty={setDirty} cancel={() => setSelection(null)} done={text => {
        setNotice(text);setSelection(null);list.refresh();archives.refresh();
      }}/>;
  }

  if (add) return <>
    <header className="page-title"><h1>カードを追加</h1></header>
    {notice && <p role="status" className="notice">{notice}</p>}
    <div className="actions"><button className="primary" onClick={() => setSelection('new')}>カードを追加</button>
      <a href="/manage">カード管理を開く</a></div>
  </>;

  return <>
    <header className="page-title"><div><h1>カード管理</h1>{total !== undefined && <p>{total}件</p>}</div>
      <button className="primary" onClick={() => setSelection('new')}>カードを追加</button></header>
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
        <option value="title">タイトル順</option><option value="favorite">お気に入り優先</option>
        <option value="rank">重要度順</option><option value="due">復習日が近い順</option>
      </select></label>
    </div>
    {list.loading && <p role="status">カードを読み込み中…</p>}
    {list.error && <p role="alert">{notice ? '保存済みです。表示を更新してください。' : list.error} <button onClick={list.refresh}>再読み込み</button></p>}
    <ul className="library-list">
      {list.data?.items.map(row => <li key={row.id}>
        <div><span className="category">{row.category || 'その他'}</span>
          <h2>{row.title || row.caption || '無題'}</h2>
          <p>{row.rank} · {row.card_type ?? '旧形式'} · {row.card_count}枚
            {row.study_tags.length > 0 && ` · ${row.study_tags.join('、')}`}</p>
        </div>
        <div className="actions">
          <button disabled={!!changing} aria-pressed={row.favorite} onClick={() => void favorite(row)}>
            {row.favorite ? '★ お気に入り' : '☆ お気に入り'}
          </button>
          <button onClick={() => setSelection({id:row.id,source:row.source})}>編集</button>
        </div>
      </li>)}
    </ul>
    {total === 0 && <p>条件に一致するカードがありません。</p>}
    {total !== undefined && <Pages page={page} total={total} change={setPage}/>}
    {!!list.data?.archives && <section className="secondary-section">
      <button aria-expanded={archived} onClick={() => setArchived(value => !value)}>参照用カード（{list.data.archives}枚）</button>
      {archived && <>
        {archives.loading && <p role="status">参照用カードを読み込み中…</p>}
        {archives.error && <p role="alert">{archives.error} <button onClick={archives.refresh}>再読み込み</button></p>}
        {archives.data?.map(card => <ArchivedCard key={card.id} card={card}/>)}
        <Pages page={archivePage} total={list.data.archives} change={setArchivePage}/>
      </>}
    </section>}
  </>;
}

function ArchivedCard({card}: {card:Archive}) {
  const [open,setOpen] = useState(false);
  const value = useStudyQuery<Card | null>('archive_detail',{id:card.id},open);
  const history = useStudyQuery<History>('card_history',{id:card.id},open);
  return <details onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{card.title || '無題'} · {card.rank ?? 'B'}</summary>
    {(value.loading || history.loading) && <p role="status">参照用の内容を読み込み中…</p>}
    {value.data && <>
      <p className="preserve"><Highlight text={value.data.question}/></p>
      {value.data.answer && <p className="preserve">{value.data.answer}</p>}
    </>}
    {value.error && <p role="alert">{value.error} <button onClick={value.refresh}>再読み込み</button></p>}
    {history.error && <p role="alert">{history.error} <button onClick={history.refresh}>履歴を再読み込み</button></p>}
    {history.data && <ul>
      {history.data.recent.map(record => <li key={record.day}>{record.day}　
        {Object.entries(record.grades).map(([slot,grade]) => `${slot === '0' ? 'カード' : `穴${slot}`} ${grade === 0 ? '×' : grade < 4 ? '△' : '◯'}`).join('、')}
      </li>)}
      {history.data.legacy.filter(record => !history.data?.recent.some(other => other.day === record.assignment_date))
        .map((record,i) => <li key={`${record.assignment_date}-${i}`}>{record.assignment_date}　旧形式の評価 {record.quality ?? '記録なし'}</li>)}
    </ul>}
  </details>;
}
