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

async function fixture(page: Page) {
  const sub = '00000000-0000-4000-8000-000000000004';
  const expires_at = Math.floor(Date.now()/1000)+3600;
  const encode = (part: object) => Buffer.from(JSON.stringify(part)).toString('base64url');
  const access_token = `${encode({alg:'HS256',typ:'JWT'})}.${encode({sub,exp:expires_at,role:'authenticated'})}.fixture`;
  await page.addInitScript(session => localStorage.setItem('sb-example-auth-token',JSON.stringify(session)),{
    access_token,refresh_token:'fixture',expires_at,expires_in:3600,token_type:'bearer',
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
  const calls: string[] = [];
  let failSave = false;
  await page.route('https://example.supabase.co/**',async route => {
    const headers = {'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'POST, GET, OPTIONS'};
    if (route.request().method() === 'OPTIONS') {await route.fulfill({status:204,headers});return;}
    if (!route.request().url().endsWith('/rpc/study_api')) {await route.fulfill({json:{},headers});return;}
    const {p_action:action,p_payload:payload} = route.request().postDataJSON();
    calls.push(action);
    if (action === 'library') {await route.fulfill({json:library,headers});return;}
    if (action === 'daily') {await route.fulfill({json:{day,assignments:[record],unassigned:0},headers});return;}
    if (action === 'evaluate') {
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
    await route.fulfill({json:{ok:true},headers});
  });
  return {calls,markFailure:() => {failSave=true;}};
}

test('a long daily card stays masked and resumes after saving a section', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror',error => errors.push(error.message));
  await fixture(page);
  await page.goto('/review');
  await expect(page.getByRole('heading',{name:'本日のノルマ'})).toBeVisible();
  await expect(page.getByText(firstAnswer,{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'答えを見る'}).click();
  const correct = page.getByRole('radio',{name:'◯ 完全に覚えていた'});
  await expect(correct).toHaveCount(8);
  await page.getByRole('radio',{name:'× 忘れていた'}).first().check();
  for(let i=1;i<8;i++) await correct.nth(i).check();
  await page.getByRole('button',{name:'区切りを保存'}).click();
  await expect(page.getByText(/区切り 2 \/ 2/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/8穴 保存済み/)).toBeVisible();
  await page.getByRole('button',{name:'答えを見る'}).click();
  for(let i=0;i<3;i++) await correct.nth(i).check();
  await page.getByRole('button',{name:'復習を確定'}).click();
  await expect(page.getByRole('heading',{name:'本日のノルマ完了'})).toBeVisible();
  await page.getByRole('button',{name:/△・×を解き直す/}).click();
  await page.getByRole('button',{name:'答えを見る'}).click();
  await page.getByRole('button',{name:'解き直しを完了'}).click();
  await expect(page.getByText('解き直しが完了しました。')).toBeVisible();
  expect(errors).toEqual([]);
});

test('free mini test reveals answers only after completion and never writes study progress', async ({page}) => {
  const {calls} = await fixture(page);
  await page.goto('/practice');
  await expect(page.getByRole('heading',{name:'自由演習'})).toBeVisible();
  await page.getByLabel('演習の目的').selectOption('test');
  await page.getByRole('checkbox',{name:'債権'}).check();
  await expect(page.getByText('1件が該当')).toBeVisible();
  await page.getByRole('button',{name:'演習を開始'}).click();
  await expect(page.getByText(firstAnswer,{exact:true})).toHaveCount(0);
  await page.getByLabel('思い出した答え（任意）').fill('自分の解答');
  await page.getByRole('button',{name:'次の区切り'}).click();
  await expect(page.getByText(firstAnswer,{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'全問の解答を確定'}).click();
  await expect(page.getByText('記入した答え　自分の解答')).toBeVisible();
  await expect(page.getByRole('radio',{name:'◯ 完全に覚えていた'})).toHaveCount(8);
  expect(calls.every(action => action === 'library')).toBeTruthy();
});

test('regeneration keeps the save control above edits and preserves the draft after failure', async ({page}) => {
  const {markFailure} = await fixture(page);
  await page.goto('/manage');
  await page.getByRole('button',{name:'編集',exact:true}).click();
  await page.getByRole('textbox',{name:'原文',exact:true}).fill(sourceText+'。追記【最後】');
  await page.getByRole('button',{name:'再生成プレビュー'}).click();
  await expect(page.getByRole('heading',{name:'再生成プレビュー'})).toBeVisible();
  const save = page.getByRole('button',{name:'全4枚を保存'});
  const prompt = page.locator('.prompt');
  expect((await save.boundingBox())!.y).toBeLessThan((await prompt.boundingBox())!.y);
  await page.getByRole('button',{name:'表示中のカードを編集'}).click();
  const answer = page.getByRole('textbox',{name:/穴 .* の答え/}).first();
  await answer.fill('編集した答え');
  markFailure();
  await save.click();
  await expect(page.getByRole('alert')).toContainText('変更された');
  await expect(answer).toHaveValue('編集した答え');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
