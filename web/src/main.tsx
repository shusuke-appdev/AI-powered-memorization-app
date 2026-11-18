import {useCallback, useEffect, useState} from 'react';
import type {MouseEvent} from 'react';
import {createRoot} from 'react-dom/client';
import {api, message, supabase} from './api.ts';
import {holes, layoutFor} from './cards.ts';
import type {Assignment, Daily, Library} from './cards.ts';
import {ListenPage, StatsPage, japanDate} from './Extras.tsx';
import {ManagePage} from './Manage.tsx';
import {PracticePage} from './Practice.tsx';
import {DailyPage} from './Study.tsx';
import type {Scores} from './Study.tsx';
import './style.css';

const routes = [
  ['/review','本日のノルマ'], ['/practice','自由演習'], ['/add','カードを追加'],
  ['/manage','カード管理'], ['/listen','聞き流し'], ['/stats','統計'],
] as const;
type Path = typeof routes[number][0];
const locationPath = () => routes.find(([path]) => path === window.location.pathname)?.[0] ?? '/review';

function nextDate(library: Library,item: Assignment,scores: Scores) {
  const state = library.targets.find(target => target.id === item.target_id);
  if (!state) return undefined;
  const worst = Math.min(...Object.values(scores));
  const current = state.repetitions === 0 ? 1 : state.repetitions === 1 ? 6
    : Math.max(1,Math.floor(Math.min(state.interval*state.ease_factor,36500)));
  let interval = worst === 0 ? 1 : worst === 2 ? Math.min(current,Math.max(1,Math.floor(state.interval/2))) : current;
  if (worst === 4 && holes(item.layout).length > 0) {
    const seen = new Set([...state.seen_holes,...holes(item.layout).map(hole => hole.hole)]);
    const all = library.cards.filter(card => (card.source_id ?? card.id) === item.target_id && !card.study_archived_at);
    if (all.some(card => holes(layoutFor(card)).some(hole => !seen.has(hole.hole)))) interval = Math.min(interval,6);
  }
  const date = new Date(item.day+'T00:00:00Z');
  date.setUTCDate(date.getUTCDate()+interval);
  return date.toISOString().slice(0,10);
}

function Workspace() {
  const [page,setPage] = useState(locationPath);
  const [library,setLibrary] = useState<Library | null>(null);
  const [daily,setDaily] = useState<Daily | null>(null);
  const [error,setError] = useState('');
  const [settings,setSettings] = useState(false);
  const [quota,setQuota] = useState(15);
  const [saving,setSaving] = useState(false);

  const reload = useCallback(async () => {
    const value = await api<Library>('library');
    setLibrary(value);
    setQuota(value.quota);
  },[]);
  const refreshDaily = useCallback(async () => {
    const value = await api<Daily>('daily');
    setDaily(value);
    await reload();
  },[reload]);
  const load = useCallback(async (route: Path) => {
    setError('');
    try {
      if (route === '/review') await refreshDaily();
      else await reload();
    } catch (err) {
      setError(message(err));
    }
  },[refreshDaily,reload]);

  useEffect(() => {
    const follow = () => setPage(locationPath());
    window.addEventListener('popstate',follow);
    return () => window.removeEventListener('popstate',follow);
  },[]);
  useEffect(() => {
    void load(page);
  },[load,page]);
  useEffect(() => {
    if (page !== '/review' || !daily?.day) return;
    const rollover = () => {if (japanDate() !== daily.day) void load(page);};
    const id = window.setInterval(rollover,30000);
    window.addEventListener('focus',rollover);
    return () => {window.clearInterval(id);window.removeEventListener('focus',rollover);};
  },[daily?.day,load,page]);

  function navigate(event: MouseEvent<HTMLAnchorElement>,path: Path) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    if (path !== page) {
      window.history.pushState(null,'',path);
      setPage(path);
      setSettings(false);
      window.scrollTo({top:0});
    }
  }

  async function saveQuota() {
    if (saving) return;
    setSaving(true);
    try {
      await api('quota',{quota});
      await load(page);
      setSettings(false);
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  }

  function updateAssignment(item: Assignment) {
    setDaily(value => value && value.day === item.day
      ? {...value,assignments:value.assignments.map(old => old.target_id === item.target_id ? item : old)}
      : value);
    if (item.completed_at) void reload().catch(err => setError(message(err)));
  }

  async function logout() {
    const response = await supabase?.auth.signOut({scope:'local'});
    if (response?.error) setError('ログアウトを完了できませんでした。もう一度お試しください。');
  }

  return <>
    <header className="shell">
      <div className="bar">
        <a className="brand" href="/review" onClick={event => navigate(event,'/review')}>暗記カード</a>
        <div className="account"><button onClick={() => setSettings(value => !value)} aria-expanded={settings}>設定</button>
          <button onClick={() => void logout()}>ログアウト</button></div>
      </div>
      <nav aria-label="メニュー">{routes.map(([path,label]) => <a href={path} key={path}
        aria-current={path === page ? 'page' : undefined} onClick={event => navigate(event,path)}>{label}</a>)}</nav>
    </header>
    <main>
      {settings && <section className="settings">
        <form onSubmit={event => {event.preventDefault();void saveQuota();}}>
          <label className="field">1日の上限（原文・単独カード）
            <input required min={1} max={100} type="number" value={quota || ''} onChange={event => setQuota(Number(event.target.value))}/>
          </label>
          <button className="primary" disabled={saving}>上限を保存</button>
        </form>
      </section>}
      {error && <div role="alert" className="notice"><p>{error}</p><button onClick={() => void load(page)}>再読み込み</button></div>}
      {!library && !error && <p role="status">カードを読み込み中…</p>}
      {library && page === '/review' && daily && <DailyPage daily={daily} sources={library.sources}
        valid={item => library.targets.some(target => target.id === item.target_id && target.version === item.version)
          && library.cards.some(card => card.id === item.card_id && !card.study_archived_at)}
        preview={(item,scores) => nextDate(library,item,scores)} onSave={updateAssignment} load={refreshDaily}/>}
      {library && page === '/practice' && <PracticePage library={library} reload={reload}/>}
      {library && page === '/manage' && <ManagePage key="manage" library={library} reload={reload}/>}
      {library && page === '/add' && <ManagePage key="add" library={library} reload={reload} add/>}
      {library && page === '/listen' && <ListenPage library={library}/>}
      {library && page === '/stats' && <StatsPage library={library} reload={reload}/>}
    </main>
  </>;
}

function App() {
  const [identity,setIdentity] = useState<string | null | undefined>(supabase ? undefined : null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  useEffect(() => {
    if (!supabase) return;
    const {data} = supabase.auth.onAuthStateChange((_event,session) => setIdentity(session?.user.id ?? null));
    return () => data.subscription.unsubscribe();
  },[]);

  async function login() {
    setBusy(true);
    setError('');
    try {
      const redirect = new URL(window.location.pathname,window.location.origin).href;
      const result = await supabase?.auth.signInWithOAuth({provider:'google',options:{redirectTo:redirect}});
      if (result?.error) throw result.error;
    } catch {
      setError('Google ログインを開始できませんでした。再度お試しください。');
      setBusy(false);
    }
  }
  if (identity) return <Workspace key={identity}/>;
  return <main className="login">
    <h1>暗記カード</h1>
    {identity === undefined ? <p role="status">ログイン状態を確認中…</p> : <>
      {supabase ? <><p>招待された Google アカウントで開けます。</p>
        <button className="primary" disabled={busy} onClick={login}>Google でログイン</button></>
        : <p>データベースが未接続です。利用環境の公開設定を指定してください。</p>}
      {error && <p role="alert" className="notice">{error}</p>}
    </>}
  </main>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing application root');
const app = createRoot(root);
app.render(<App/>);
if (import.meta.hot) import.meta.hot.dispose(() => app.unmount());
