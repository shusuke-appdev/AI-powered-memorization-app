import {createClient} from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL?.trim();
const publishable = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
// The static bundle is public. Reject server keys even if entered by mistake.
const publicKey = publishable?.startsWith('sb_publishable_') ? publishable : undefined;
export const supabase = url && publicKey
  ? createClient(url, publicKey, {auth: {flowType: 'pkce'}})
  : null;

export class StudyError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

const messages: Record<string, string> = {
  '42501': 'このアカウントの招待と利用者の紐づけを確認してください。',
  '40001': '別の画面で変更されたか、日付が変わりました。画面を更新して確認してください。',
  '22023': '入力内容を確認してください。',
  '55000': '完全バックアップは空のデッキに復元してください。',
  '23505': '同じ名前または識別子のデータがすでにあります。',
  'PGRST202': 'データベースの更新が必要です。',
};

export async function api<T>(action: string, payload: object = {}, signal?: AbortSignal): Promise<T> {
  if (!supabase) throw new Error('Supabase の公開設定が必要です。');
  const request = supabase.rpc('study_api', {p_action: action, p_payload: payload});
  const {data, error} = await (signal ? request.abortSignal(signal) : request);
  if (error) {
    throw new StudyError(error.code, messages[error.code] ?? '接続または保存に失敗しました。時間をおいて再試行してください。');
  }
  return data as T;
}

export const message = (error: unknown): string =>
  error instanceof Error ? error.message : '処理を完了できませんでした。';
