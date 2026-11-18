import {useEffect, useState} from 'react';
import {api, message} from './api.ts';
import {exportCsv, prepareImport, writeDownload} from './backup.ts';
import {defaults, holes, practiceCandidates, subjects} from './cards.ts';
import type {Library} from './cards.ts';
import {Highlight} from './Study.tsx';

export const japanDate = () => new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());

export function StatsPage({library,reload}: {library: Library; reload: () => Promise<void>}) {
  const [backup,setBackup] = useState<ReturnType<typeof prepareImport> | null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const today = japanDate();
  const active = new Set(library.cards.filter(card => !card.study_archived_at).map(card => card.source_id ?? card.id));
  const due = library.targets.filter(target => active.has(target.id) && target.next_review < today).length;
  const grades = library.history.flatMap(row => holes(row.layout).flatMap(hole =>
    row.grades[hole.hole] === undefined ? [] : [row.grades[hole.hole]]));
  const weak = practiceCandidates(library,{...defaults,mode:'weak'}).slice(0,10);

  async function download() {
    setBusy(true);
    setError('');
    try {
      const value = await api<Record<string, unknown>>('backup');
      writeDownload(`flashcards_${today}.json`,JSON.stringify(value,null,2),'application/json');
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setBackup(null);
    setNotice('');
    setError('');
    try {
      setBackup(prepareImport(await file.text(),file.name.toLowerCase().endsWith('.csv'),library.cards));
    } catch (err) {
      setError(message(err));
    }
  }

  async function importData() {
    if (!backup || busy) return;
    setBusy(true);
    setError('');
    try {
      await api(backup.mode,backup.payload);
      setBackup(null);
      setNotice('バックアップを取り込みました。');
      await reload();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return <>
    <header className="page-title"><div><h1>統計</h1><p>直近30日の日次演習</p></div></header>
    <dl className="stats">
      <div><dt>原文と単独カード</dt><dd>{active.size}</dd></div>
      <div><dt>復習した原文・単独カード</dt><dd>{new Set(library.history.map(row => row.target_id)).size}</dd></div>
      <div><dt>期日を過ぎた対象</dt><dd>{due}</dd></div>
      <div><dt>評価した穴</dt><dd>{grades.length}</dd></div>
    </dl>
    <p>◯ {grades.filter(grade => grade===4).length}　△ {grades.filter(grade => grade===2).length}　× {grades.filter(grade => grade===0).length}</p>
    {weak.length > 0 && <section className="secondary-section">
      <h2>最近の弱点</h2>
      <ul>{weak.map(row => <li key={row.id}>{row.category} · {row.title}</li>)}</ul>
    </section>}
    <section className="secondary-section">
      <h2>バックアップ</h2>
      <div className="actions">
        <button disabled={busy} onClick={download}>完全バックアップ（JSON）</button>
        <button disabled={!active.size} onClick={() => writeDownload(`flashcards_${today}.csv`, exportCsv(library.cards),'text/csv;charset=utf-8')}>カード一覧（CSV）</button>
      </div>
      <label className="field">バックアップを選択<input type="file" accept=".json,.csv" disabled={busy}
        onChange={event => {const file = event.target.files?.[0];if (file) void upload(file);event.target.value='';}}/></label>
      {backup && <div className="notice">
        <p>原文 {backup.sources} 件 · 暗記カード {backup.cards} 枚</p>
        {backup.warnings.map(warning => <p key={warning}>{warning}</p>)}
        <button className="primary" disabled={busy || (!backup.cards && !backup.sources && backup.mode !== 'restore')} onClick={importData}>取り込む</button>
      </div>}
      {error && <p role="alert" className="notice">{error}</p>}
      {notice && <p role="status" className="notice">{notice}</p>}
    </section>
  </>;
}

export function ListenPage({library}: {library: Library}) {
  const [category,setCategory] = useState(subjects[0]);
  const [index,setIndex] = useState(0);
  const [playing,setPlaying] = useState(false);
  const [error,setError] = useState('');
  const queue = library.sources.filter(source => (source.category ?? 'その他') === category);
  const current = queue[index];
  useEffect(() => () => window.speechSynthesis?.cancel(),[]);

  function stop() {
    window.speechSynthesis?.cancel();
    setPlaying(false);
  }

  function play(position: number) {
    if (!queue[position] || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    setIndex(position);
    setPlaying(true);
    setError('');
    const phrase = new SpeechSynthesisUtterance(queue[position].source_text.replace(/[【】]/g,''));
    phrase.lang = 'ja-JP';
    phrase.onend = () => position + 1 === queue.length ? setPlaying(false) : play(position+1);
    phrase.onerror = event => {
      if (event.error !== 'interrupted' && event.error !== 'canceled') {
        setPlaying(false);
        setError('読み上げを開始できませんでした。端末の音声設定を確認してください。');
      }
    };
    window.speechSynthesis.speak(phrase);
  }

  return <>
    <header className="page-title"><div><h1>聞き流し</h1></div></header>
    <label className="field">科目<select value={category} onChange={event => {stop();setIndex(0);setCategory(event.target.value);}}>
      {subjects.map(value => <option key={value}>{value}</option>)}
    </select></label>
    {current ? <section>
      <h2>{current.title || '無題'}</h2>
      <p className="preserve"><Highlight text={current.source_text}/></p>
      <div className="actions sticky">
        <button disabled={!index} onClick={() => playing ? play(index-1) : setIndex(index-1)}>前へ</button>
        <button className="primary" disabled={!window.speechSynthesis} onClick={() => playing ? stop() : play(index)}>{playing ? '停止' : '読み上げ'}</button>
        <button disabled={index+1 >= queue.length} onClick={() => playing ? play(index+1) : setIndex(index+1)}>次へ</button>
        <span>{index+1} / {queue.length} 件</span>
      </div>
      {!window.speechSynthesis && <p>このブラウザでは読み上げを利用できません。</p>}
      {error && <p role="alert" className="notice">{error}</p>}
    </section> : <p>この科目に原文カードはありません。</p>}
  </>;
}
