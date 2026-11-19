import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {generate,holes} from '../src/cards.ts';
import type {Assignment, Card, Library} from '../src/cards.ts';

const sourceText = Array.from({length:21},(_,i) => `確認文【正答-${i+1}】`).join('。');
const id = '00000000-0000-4000-8000-000000000001';
const cardId = '00000000-0000-4000-8000-000000000002';
const version = '00000000-0000-4000-8000-000000000003';
const [variant] = generate(sourceText,'規範');
const firstAnswer = holes(variant.layout)[0].answer;

async function fixture(page: Page, timing?: 'current'|'baseline') {
  const project = timing === 'baseline' ? 'zozsikyinpasapuxjbtg' : 'example';
  const sub = '00000000-0000-4000-8000-000000000004';
  const expires_at = Math.floor(Date.now()/1000)+3600;
  const encode = (part: object) => Buffer.from(JSON.stringify(part)).toString('base64url');
  const access_token = `${encode({alg:'HS256',typ:'JWT'})}.${encode({sub,exp:expires_at,role:'authenticated'})}.fixture`;
  await page.addInitScript(({project,...session}) => localStorage.setItem(`sb-${project}-auth-token`,JSON.stringify(session)),{
    project,access_token,refresh_token:'fixture',expires_at,expires_in:3600,token_type:'bearer',
    user:{id:sub,aud:'authenticated',email:'fixture@example.test',app_metadata:{provider:'google'},user_metadata:{},created_at:'2026-01-01T00:00:00Z'},
  });
  const day = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  let record: Assignment = {
    day,target_id:id,card_id:cardId,version,position:0,title:'確認用原文',category:'民法',card_type:'規範',rank:'A+',
    layout:variant.layout,answer:variant.answer,grades:{},revision:0,completed_at:null,next_review:null,retried:[],
  };
  const card: Card = {
    id:cardId,source_id:id,category:'民法',title:record.title,rank:'A+',card_type:'規範',
    question:variant.question,answer:variant.answer,blank_count:variant.blank_count,
    study_layout:variant.layout,study_version:version,study_tags:[],study_archived_at:null,is_favorite:true,
    ease_factor:2.5,interval:1,repetitions:0,next_review:day,
  };
  const library: Library = {
    sources:[{id,category:'民法',title:record.title,card_type:'規範',source_text:sourceText,
      study_tags:['債権'],study_version:version,study_favorite:true}],
    cards:[card],targets:[{id,version,next_review:day,interval:1,ease_factor:2.5,repetitions:0,seen_holes:[]}],
    history:[],presets:[],quota:1,
  };
  const key = (index:number) => `00000000-0000-4000-8000-${String(index).padStart(12,'0')}`;
  const ids = timing ? [id,...Array.from({length:544},(_,i) => key(i+100))] : [id];
  const baseline = timing === 'baseline' ? JSON.stringify({
    ...library,
    sources:ids.map((source,i) => ({...library.sources[0],id:source,title:`検証用の原文 ${i}`})),
    cards:[card,...Array.from({length:2726},(_,i) => ({
      ...card,id:key(i+10_000),source_id:ids[i%545],title:`検証用のカード ${i}`,
      question:'関連する事情を確認する。'.repeat(16)+'______と______を記憶する。',
      study_layout:['関連する事情を確認する。'.repeat(16),{hole:1,answer:'目的'},'と',{hole:2,answer:'要件'},'を記憶する。'],
      study_archived_at:i>=1630 ? '2026-01-01' : null,
    }))],
  }) : undefined;
  const calls: string[] = [];
  let failSave = false;
  let failRefresh = false;
  let failGrade = false;
  let saved = false;
  await page.route(`https://${project}.supabase.co/**`,async route => {
    const headers = {'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'POST, GET, OPTIONS'};
    if (route.request().method() === 'OPTIONS') {await route.fulfill({status:204,headers});return;}
    if (!route.request().url().endsWith('/rpc/study_api')) {await route.fulfill({json:{},headers});return;}
    const {p_action:action,p_payload:payload} = route.request().postDataJSON();
    calls.push(action);
    if (timing) {
      // Playwright-fulfilled responses bypass Chrome's network throttle.
      const responseBytes = action === 'library' && baseline ? Buffer.byteLength(baseline) :
        action === 'practice_search' ? 22_069 : 1_216;
      await new Promise(resolve => setTimeout(resolve,150+responseBytes/1_250));
    }
    if (action === 'library' && baseline) {
      await route.fulfill({body:baseline,contentType:'application/json',headers});return;
    }
    if (action === 'daily' && baseline) {
      await route.fulfill({json:{day,assignments:[record],unassigned:544},headers});return;
    }
    if (action === 'review_view') {
      const total = holes(record.layout).length;
      const remaining = total-Object.keys(record.grades).length;
      await route.fulfill({json:{day,total:1,completed:record.completed_at ? 1 : 0,holes:total,remaining,unassigned:0,
        current:record.completed_at ? null : record,next_review:record.next_review,
        retry_count:record.completed_at ? Object.entries(record.grades).filter(([key,value]) =>
          value===0 && !record.retried.includes(Number(key))).length : 0,reviewed_sources:[]},headers});return;
    }
    if (action === 'review_retry') {
      const hole = Object.entries(record.grades).find(([key,value]) => value===0 && !record.retried.includes(Number(key)));
      await route.fulfill({json:hole ? {assignment:record,hole:Number(hole[0]),items:record.layout} : null,headers});return;
    }
    if (action === 'practice_options') {await route.fulfill({json:{tags:[{category:'民法',tag:'債権'}],presets:[]},headers});return;}
    if (action === 'practice_search') {await route.fulfill({json:ids,headers});return;}
    if (action === 'practice_page') {await route.fulfill({json:library,headers});return;}
    if (action === 'manage_list') {
      if (saved && failRefresh) {
        failRefresh = false;
        await route.fulfill({status:503,json:{code:'503',message:'unavailable'},headers});return;
      }
      await route.fulfill({json:{total:1,archives:0,items:[{...library.sources[0],source:true,rank:'A+',favorite:true,card_count:1}]},headers});return;
    }
    if (action === 'manage_detail') {
      await route.fulfill({json:{source:library.sources[0],cards:library.cards},headers});return;
    }
    if (action === 'evaluate') {
      if (failGrade) {
        failGrade=false;
        await route.fulfill({status:503,json:{code:'503',message:'unavailable'},headers});return;
      }
      record = {...record,grades:{...record.grades,...payload.grades},revision:record.revision+1,
        completed_at:payload.finish ? new Date().toISOString() : null,next_review:payload.finish ? day : null};
      await route.fulfill({json:record,headers});
      return;
    }
    if (action === 'relearn') {
      record = {...record,retried:[...record.retried,payload.hole]};
      await route.fulfill({json:record,headers});
      return;
    }
    if (action === 'save_bundle' && failSave) {
      failSave = false;
      await route.fulfill({status:409,json:{code:'40001',message:'conflict'},headers});
      return;
    }
    if (action === 'save_bundle') saved = true;
    await route.fulfill({json:{ok:true},headers});
  });
  return {calls,markFailure:() => {failSave=true;},markRefreshFailure:() => {failRefresh=true;},markGradeFailure:() => {failGrade=true;}};
}

test('stores one hole, resumes at the next, and masks remaining answers', async ({page}) => {
  const {calls,markGradeFailure} = await fixture(page);
  const correct = page.getByRole('button',{name:'◯ 完全に覚えていた'});
  await page.goto('/review');
  await expect(page.getByRole('heading',{name:'本日のノルマ'})).toBeVisible();
  await expect(page.getByText(firstAnswer,{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'答えを見る'}).click();
  await expect(correct).toHaveCount(1);
  await expect(page.getByText(holes(variant.layout)[1].answer,{exact:true})).toHaveCount(0);
  markGradeFailure();
  await page.getByRole('button',{name:'× 忘れていた'}).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('button',{name:'× 忘れていた'})).toHaveAttribute('aria-pressed','true');
  await page.getByRole('button',{name:'× 忘れていた'}).click();
  await expect(page.getByText(/穴 2 \/ 11/)).toBeVisible();
  await expect(page.locator('.current-gap small')).toHaveText('2');
  await page.reload();
  await expect(page.getByText(/1件 保存済み/)).toBeVisible();
  for(let i=2;i<=11;i++) {
    await expect(page.getByText(new RegExp('穴 '+i+' / 11'))).toBeVisible();
    await page.getByRole('button',{name:'答えを見る'}).click();
    await correct.click();
  }
  await expect(page.getByRole('heading',{name:'本日のノルマ完了'})).toBeVisible();
  await page.getByRole('button',{name:/△・×を解き直す/}).click();
  await page.getByRole('button',{name:'答えを見る'}).click();
  await correct.click();
  await expect(page.getByText('解き直しが完了しました。')).toBeVisible();
  expect(calls.filter(action => action === 'evaluate')).toHaveLength(12);
});

test('mini test preserves omitted answers, and grades only after all holes are submitted', async ({page}) => {
  const {calls} = await fixture(page);
  await page.goto('/practice');
  await page.getByRole('button',{name:'ミニテスト'}).click();
  await page.getByText('詳細条件',{exact:true}).click();
  await page.getByRole('checkbox',{name:'債権'}).check();
  await expect(page.getByText('1件が該当')).toBeVisible();
  await page.getByRole('button',{name:'演習を開始'}).click();
  await expect(page.getByText(firstAnswer,{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'次の穴',exact:true}).click();
  await page.getByLabel('思い出した答え（任意）').fill('二番の解答');
  for(let i=2;i<11;i++) await page.getByRole('button',{name:'次の穴',exact:true}).click();
  await expect(page.getByText(firstAnswer,{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'全問の解答を確定'}).click();
  await page.getByRole('button',{name:'答えを見る'}).click();
  await expect(page.getByText('記入した答え　未記入')).toBeVisible();
  await page.getByRole('button',{name:'◯ 完全に覚えていた'}).click();
  await page.getByRole('button',{name:'答えを見る'}).click();
  await expect(page.getByText('記入した答え　二番の解答')).toBeVisible();
  expect(calls.every(action => ['practice_options','practice_page','practice_search'].includes(action))).toBeTruthy();
});

test('regeneration keeps the save control above edits and preserves the draft after failure', async ({page},info) => {
  const {markFailure} = await fixture(page);
  await page.goto('/manage');
  await page.getByRole('button',{name:'編集',exact:true}).click();
  await page.getByRole('textbox',{name:'原文',exact:true}).fill(sourceText+'。追記【最後】');
  await page.getByRole('button',{name:'再生成プレビュー'}).click();
  await expect(page.getByRole('heading',{name:'再生成プレビュー'})).toBeVisible();
  const save = page.getByRole('button',{name:'全4枚を保存'});
  const prompt = page.locator('.prompt');
  expect((await save.boundingBox())!.y).toBeLessThan((await prompt.boundingBox())!.y);
  const captures = process.env.STUDY_SCREENSHOT_PATH;
  if (captures) await page.screenshot({path:`${captures}/regenerate-${info.project.name}.png`});
  await page.getByRole('button',{name:'表示中のカードを編集'}).click();
  const answer = page.getByRole('textbox',{name:/穴 .* の答え/}).first();
  await answer.fill('編集した答え');
  markFailure();
  await save.click();
  await expect(page.getByRole('alert')).toContainText('変更された');
  await expect(answer).toHaveValue('編集した答え');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('a committed regeneration survives a failed list refresh without writing twice', async ({page}) => {
  const {calls,markRefreshFailure} = await fixture(page);
  await page.goto('/manage');
  await page.getByRole('button',{name:'編集',exact:true}).click();
  await page.getByRole('textbox',{name:'原文',exact:true}).fill(sourceText+'。追記【最後】');
  await page.getByRole('button',{name:'再生成プレビュー'}).click();
  markRefreshFailure();
  await page.getByRole('button',{name:'全4枚を保存'}).click();
  await expect(page.getByRole('alert')).toContainText('保存済み');
  await page.getByRole('button',{name:'再読み込み'}).click();
  await expect(page.getByRole('button',{name:'編集',exact:true})).toBeVisible();
  expect(calls.filter(action => action === 'save_bundle')).toHaveLength(1);
});

test('a bookmarked listen route resolves to review', async ({page}) => {
  await fixture(page);
  await page.goto('/listen');
  await expect(page).toHaveURL(/\/review$/);
  await expect(page.getByRole('heading',{name:'本日のノルマ'})).toBeVisible();
  await expect(page.getByRole('link',{name:'聞き流し'})).toHaveCount(0);
});

test('a cancelled Google login can be retried without exposing the workspace', async ({page}) => {
  await page.goto('/practice?error=access_denied');
  await expect(page.getByRole('alert')).toContainText('Google ログインを完了できませんでした');
  await expect(page.getByRole('button',{name:'Google でログイン'})).toBeEnabled();
  await expect(page.getByRole('button',{name:'演習を開始'})).toHaveCount(0);
});

test('cold mobile reads and grade acknowledgements meet the local transport budget', async ({browser,baseURL},info) => {
  test.skip(process.env.STUDY_BENCHMARK !== '1' || info.project.name !== 'mobile','Opt-in timing check');
  const baseline = process.env.STUDY_BASELINE === '1';
  test.setTimeout(baseline ? 360_000 : 120_000);
  const review: number[] = [];
  const practice: number[] = [];
  const grade: number[] = [];
  for (let sample=0;sample<20;sample++) {
    for (const path of ['/review','/practice']) {
      const context = await browser.newContext({baseURL,viewport:{width:390,height:844},isMobile:true,hasTouch:true});
      try {
        const page = await context.newPage();
        await fixture(page,baseline ? 'baseline' : 'current');
        const emulator = await context.newCDPSession(page);
        await emulator.send('Network.enable');
        await emulator.send('Network.setCacheDisabled',{cacheDisabled:true});
        await emulator.send('Network.emulateNetworkConditions',{
          offline:false,latency:150,downloadThroughput:10_000_000/8,uploadThroughput:2_000_000/8,
        });
        await emulator.send('Emulation.setCPUThrottlingRate',{rate:4});
        const started = performance.now();
        await page.goto(path,{waitUntil:'commit'});
        if (path === '/practice') {
          await expect(page.getByRole('button',{name:'演習を開始'})).toBeEnabled({timeout:15000});
          practice.push(performance.now()-started);
          continue;
        }
        await expect(page.getByRole('button',{name:'答えを見る'})).toBeEnabled({timeout:15000});
        review.push(performance.now()-started);
        if (baseline) continue;
        await page.getByRole('button',{name:'答えを見る'}).click();
        const correct = page.getByRole('button',{name:'◯ 完全に覚えていた'});
        await expect(correct).toBeEnabled();
        const saved = page.waitForResponse(response => response.request().method()==='POST'
          && response.url().endsWith('/rpc/study_api') && response.request().postDataJSON()?.p_action==='evaluate');
        const scoring = performance.now();
        await correct.click();
        expect((await saved).ok()).toBeTruthy();
        await expect(page.getByText(/穴 2 \/ 11/)).toBeVisible();
        grade.push(performance.now()-scoring);
      } finally {
        await context.close();
      }
    }
  }
  const p95 = (times:number[]) => Math.round([...times].sort((a,b) => a-b)[Math.ceil(times.length*.95)-1]);
  const milliseconds = {review:p95(review),practice:p95(practice),grade:baseline ? null : p95(grade)};
  console.log('Synthetic, cold browser p95 in milliseconds',milliseconds);
  if (baseline) return;
  expect(milliseconds.review).toBeLessThanOrEqual(3000);
  expect(milliseconds.practice).toBeLessThanOrEqual(3000);
  expect(milliseconds.grade).toBeLessThanOrEqual(1500);
});

test('primary mobile controls remain reachable with keyboard navigation', async ({page},info) => {
  await fixture(page);
  await page.goto('/review');
  const reveal = page.getByRole('button',{name:'答えを見る'});
  await expect(reveal).toBeVisible();
  expect((await reveal.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await reveal.focus();
  await page.keyboard.press('Enter');
  const rating = page.getByRole('button',{name:'◯ 完全に覚えていた'});
  await expect(rating).toBeVisible();
  await expect(rating).toBeFocused();
  expect((await rating.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  const captures = process.env.STUDY_SCREENSHOT_PATH;
  if (captures) await page.screenshot({path:`${captures}/review-${info.project.name}.png`});
  await page.getByRole('link',{name:'自由演習'}).click();
  await expect(page.getByRole('button',{name:'演習を開始'})).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  if (captures) await page.screenshot({path:`${captures}/practice-${info.project.name}.png`});
});
