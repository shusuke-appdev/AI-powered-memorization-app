import {useRef, useState} from 'react';
import {api, message} from './api.ts';
import {exportCsv, prepareImport, writeDownload} from './backup.ts';
import type {Card} from './cards.ts';
import {useStudyQuery} from './query.ts';

type Stats = {
  active:number; reviewed:number; due:number; correct:number; partial:number; missed:number;
  weak:{title:string | null;category:string}[];
};

export function StatsPage() {
  const stats = useStudyQuery<Stats>('stats_view');
  const [backup,setBackup] = useState<{plan:ReturnType<typeof prepareImport>;id:string} | null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const pending = useRef(false);
  const today = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());

  async function operation(work: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError('');
    try {await work();}
    catch (err) {setError(message(err));}
    finally {pending.current = false;setBusy(false);}
  }

  function download(csv: boolean) {
    return operation(async () => {
      if (csv) {
        const cards = await api<Card[]>('csv_cards');
        writeDownload(`flashcards_${today}.csv`,exportCsv(cards),'text/csv;charset=utf-8');
      } else {
        const value = await api<Record<string, unknown>>('backup');
        writeDownload(`flashcards_${today}.json`,JSON.stringify(value,null,2),'application/json');
      }
    });
  }

  function upload(file: File) {
    return operation(async () => {
      setBackup(null);
      setNotice('');
      const text = await file.text();
      const csv = file.name.toLowerCase().endsWith('.csv');
      const preview = prepareImport(text,csv,[]);
      if (preview.mode === 'restore') {
        if (!await api<boolean>('restore_available')) {
          throw new Error('この学習領域にはデータがあります。完全バックアップは空の学習領域に復元できます。');
        }
        setBackup({plan:preview,id:crypto.randomUUID()});
        return;
      }
      const cards = preview.payload.cards.map((card: Pick<Card,'question'|'answer'>) => ({question:card.question,answer:card.answer}));
      const found = cards.length ? await api<Pick<Card,'question'|'answer'>[]>('import_matches',{cards}) : [];
      const existing = found.map(card => ({...card,study_archived_at:null}));
      setBackup({plan:prepareImport(text,csv,existing),id:crypto.randomUUID()});
    });
  }

  function importData() {
    if (!backup) return;
    return operation(async () => {
      await api(backup.plan.mode,{...backup.plan.payload,request_id:backup.id});
      setBackup(null);
      setNotice('バックアップを取り込みました。');
      stats.refresh();
    });
  }

  const value = stats.data;
  return <>
    <header className="page-title"><div><h1>統計</h1><p>直近30日の日次演習</p></div></header>
    {stats.loading && <p role="status">統計を読み込み中…</p>}
    {stats.error && <p role="alert">{notice ? '保存済みです。統計を更新してください。' : stats.error} <button onClick={stats.refresh}>再読み込み</button></p>}
    {value && <>
      <dl className="stats">
        <div><dt>原文と単独カード</dt><dd>{value.active}</dd></div>
        <div><dt>復習した原文・単独カード</dt><dd>{value.reviewed}</dd></div>
        <div><dt>期日を過ぎた対象</dt><dd>{value.due}</dd></div>
        <div><dt>評価した穴</dt><dd>{value.correct+value.partial+value.missed}</dd></div>
      </dl>
      <p>◯ {value.correct}　△ {value.partial}　× {value.missed}</p>
      {value.weak.length > 0 && <section className="secondary-section">
        <h2>最近の弱点</h2>
        <ul>{value.weak.map((row,index) => <li key={index}>{row.category} · {row.title || '無題'}</li>)}</ul>
      </section>}
    </>}
    <section className="secondary-section">
      <h2>バックアップ</h2>
      <div className="actions">
        <button disabled={busy} onClick={() => void download(false)}>完全バックアップ（JSON）</button>
        <button disabled={busy || !value?.active} onClick={() => void download(true)}>カード一覧（CSV）</button>
      </div>
      <label className="field">バックアップを選択<input type="file" accept=".json,.csv" disabled={busy}
        onChange={event => {const file = event.target.files?.[0];if (file) void upload(file);event.target.value='';}}/></label>
      {backup && <div className="notice">
        <p>原文 {backup.plan.sources} 件 · 暗記カード {backup.plan.cards} 枚</p>
        {backup.plan.warnings.map(warning => <p key={warning}>{warning}</p>)}
        <button className="primary" disabled={busy || (!backup.plan.cards && !backup.plan.sources && backup.plan.mode !== 'restore')}
          onClick={() => void importData()}>取り込む</button>
      </div>}
      {error && <p role="alert" className="notice">{error}</p>}
      {notice && <p role="status" className="notice">{notice}</p>}
    </section>
  </>;
}
