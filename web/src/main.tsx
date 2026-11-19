import {lazy, Suspense, useCallback, useEffect, useRef, useState} from 'react';
import type {MouseEvent} from 'react';
import {createRoot} from 'react-dom/client';
import {api, message, supabase} from './api.ts';
import {DailyPage} from './Study.tsx';
import type {ReviewView} from './Study.tsx';
import type {Assignment} from './cards.ts';
import {confirmDiscard, useDirtyScope} from './navigation.ts';
import {useStudyQuery} from './query.ts';
import './style.css';

const PracticePage = lazy(() => import('./Practice.tsx').then(module => ({default:module.PracticePage})));
const ManagePage = lazy(() => import('./Manage.tsx').then(module => ({default:module.ManagePage})));
const StatsPage = lazy(() => import('./Extras.tsx').then(module => ({default:module.StatsPage})));

const routes = [
  ['/review','本日のノルマ'], ['/practice','自由演習'], ['/manage','カード管理'],
  ['/add','カードを追加'], ['/stats','統計'],
] as const;
type Path = typeof routes[number][0];
const locationPath = () => routes.find(([path]) => path === window.location.pathname)?.[0] ?? '/review';

if (/^\/listen\/?$/.test(window.location.pathname)) {
  window.history.replaceState(null,'','/review'+window.location.search+window.location.hash);
}

function tokyoToday() {
  return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
}

function ReviewWorkspace({revision}: {revision:number}) {
  const [review,setReview] = useState<ReviewView>();
  const [error,setError] = useState('');
  const [advancing,setAdvancing] = useState(false);
  const controller = useRef<AbortController | undefined>(undefined);
  const load = useCallback(async () => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setError('');
    try {
      const response = await api<ReviewView>('review_view',{},request.signal);
      if (!request.signal.aborted) {setReview(response);setAdvancing(false);}
    } catch (err) {
      if (!request.signal.aborted) setError(message(err));
      throw err;
    }
  },[]);

  useEffect(() => {
    void load().catch(() => {});
    return () => controller.current?.abort();
  },[load,revision]);

  useEffect(() => {
    if (!review) return;
    const rollover = () => {
      if (tokyoToday() !== review.day) {
        setAdvancing(true);
        void load().catch(() => {});
      }
    };
    window.addEventListener('focus',rollover);
    const id = window.setInterval(rollover,15000);
    return () => {window.removeEventListener('focus',rollover);window.clearInterval(id);};
  },[load,review]);

  function saved(assignment: Assignment) {
    if (assignment.completed_at) {
      setAdvancing(true);
      void load().catch(() => {});
      return;
    }
    setReview(current => {
      if (!current?.current || current.day !== assignment.day || current.current.target_id !== assignment.target_id) return current;
      const delta = Object.keys(assignment.grades).length-Object.keys(current.current.grades).length;
      return {...current,current:assignment,remaining:Math.max(0,current.remaining-(assignment.layout.some(part => typeof part !== 'string') ? delta : 0))};
    });
  }

  return <>
    {error && <div role="alert" className="notice">
      <p>{advancing ? '復習の保存後に画面の更新が必要です。' : error}</p>
      <button onClick={() => void load().catch(() => {})}>再読み込み</button>
    </div>}
    {(!review || advancing) && !error && <p role="status">{advancing ? '次の出題を読み込み中…' : '本日のノルマを読み込み中…'}</p>}
    {review && !advancing && <DailyPage key={review.day} review={review} onSave={saved} load={load}/>}
  </>;
}

function Settings({close,saved}: {close: () => void; saved: () => void}) {
  const quota = useStudyQuery<number>('quota_view');
  const [value,setValue] = useState<number>();
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  async function save() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {await api('quota',{quota:value ?? quota.data});saved();close();}
    catch (err) {setError(message(err));}
    finally {setBusy(false);}
  }
  return <section className="settings" aria-label="設定">
    <h2>復習の設定</h2>
    {quota.loading && <p role="status">設定を読み込み中…</p>}
    {quota.error && <p role="alert">{quota.error} <button onClick={quota.refresh}>再読み込み</button></p>}
    {quota.data !== undefined && <form onSubmit={event => {event.preventDefault();void save();}}>
      <label className="field">1日の上限（原文・単独カード）
        <input required min={1} max={100} type="number" value={value ?? quota.data}
          onChange={event => setValue(Number(event.target.value))}/>
      </label>
      <button className="primary" disabled={busy}>上限を保存</button>
    </form>}
    {error && <p role="alert" className="notice">{error}</p>}
  </section>;
}

function Workspace() {
  const [page,setPage] = useState(locationPath);
  const [settings,setSettings] = useState(false);
  const [menu,setMenu] = useState(false);
  const [revision,setRevision] = useState(0);
  const [error,setError] = useState('');
  const {dirty,setDirty} = useDirtyScope();
  const main = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const follow = () => {
      const target = locationPath();
      if (target === page) return;
      if (dirty && !confirmDiscard()) {window.history.pushState(null,'',page);return;}
      setDirty(false);setMenu(false);setSettings(false);setPage(target);
    };
    window.addEventListener('popstate',follow);
    return () => window.removeEventListener('popstate',follow);
  },[dirty,page,setDirty]);

  function go(path: Path) {
    if (path === page) {setMenu(false);return;}
    if (dirty && !confirmDiscard()) return;
    window.history.pushState(null,'',path);
    setDirty(false);setPage(path);setMenu(false);setSettings(false);
    window.scrollTo({top:0});
    main.current?.focus({preventScroll:true});
  }

  function navigate(event: MouseEvent<HTMLAnchorElement>,path: Path) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();go(path);
  }

  async function logout() {
    if (dirty && !confirmDiscard()) return;
    const response = await supabase?.auth.signOut({scope:'local'});
    if (response?.error) setError('ログアウトを完了できませんでした。もう一度お試しください。');
  }

  const navLink = ([path,label]: typeof routes[number], short = false) => <a key={path} href={path}
    aria-current={path === page ? 'page' : undefined} onClick={event => navigate(event,path)}>
    {short && <i aria-hidden="true" className={`nav-icon nav-${path.slice(1)}`}/>}
    {short && path === '/review' ? '復習' : label}</a>;
  return <>
    <a className="skip-link" href="#workspace">本文へ移動</a>
    <header className="shell">
      <div className="bar">
        <a className="brand" href="/review" onClick={event => navigate(event,'/review')}>暗記カード</a>
        <div className="account"><button onClick={() => setSettings(value => !value)} aria-expanded={settings}>設定</button>
          <button onClick={() => void logout()}>ログアウト</button></div>
      </div>
      <nav className="desktop-nav" aria-label="メニュー">{routes.map(route => navLink(route))}</nav>
    </header>
    <nav className="mobile-nav" aria-label="モバイルメニュー">
      {routes.slice(0,3).map(route => navLink(route,true))}
      <button ref={menuButton} aria-expanded={menu} aria-controls="mobile-more" onClick={() => setMenu(value => !value)}>
        <i className="nav-icon nav-more" aria-hidden="true"/>その他</button>
    </nav>
    {menu && <div id="mobile-more" className="mobile-more" onKeyDown={event => {
      if (event.key === 'Escape') {setMenu(false);menuButton.current?.focus();}
    }}>
      {routes.slice(3).map(route => navLink(route))}
      <button onClick={() => {setMenu(false);setSettings(value => !value);window.scrollTo({top:0});}}>設定</button>
      <button onClick={() => void logout()}>ログアウト</button>
    </div>}
    <main id="workspace" ref={main} tabIndex={-1}>
      {settings && <Settings close={() => setSettings(false)} saved={() => setRevision(value => value+1)}/>}
      {error && <p role="alert" className="notice">{error}</p>}
      <Suspense fallback={<p role="status">画面を読み込み中…</p>}>
        {page === '/review' && <ReviewWorkspace revision={revision}/>}
        {page === '/practice' && <PracticePage setDirty={setDirty}/>}
        {page === '/manage' && <ManagePage key="manage" setDirty={setDirty}/>}
        {page === '/add' && <ManagePage key="add" add setDirty={setDirty}/>}
        {page === '/stats' && <StatsPage/>}
      </Suspense>
    </main>
  </>;
}

function App() {
  const [identity,setIdentity] = useState<string | null | undefined>(supabase ? undefined : null);
  const [error,setError] = useState(() => {
    const query = new URLSearchParams(window.location.search);
    return query.has('error') ? 'Google ログインを完了できませんでした。招待されたアカウントで再試行してください。' : '';
  });
  const [busy,setBusy] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    const {data} = supabase.auth.onAuthStateChange((_event,session) => {
      setIdentity(session?.user.id ?? null);
      setBusy(false);
    });
    return () => data.subscription.unsubscribe();
  },[]);

  async function login() {
    if (!supabase || busy) return;
    setBusy(true);
    setError('');
    try {
      const redirect = new URL(window.location.pathname,window.location.origin).href;
      const result = await supabase.auth.signInWithOAuth({provider:'google',options:{redirectTo:redirect,queryParams:{prompt:'select_account'}}});
      if (result.error) throw result.error;
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
