# 暗記カード Web版

Vite・React・TypeScriptで画面を構成します。Cloudflare Workers Static Assetsが画面を配信し、Supabaseが本人確認・データの所有者判定・保存を担当します。

## ローカルで確認

Node.js 24を使用します。`web/` で以下を実行します。

```sh
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:browser
npm run dev
```

`npm test` は生成、自由演習、旧形式の取り込みに加え、隔離したPostgreSQL互換エンジンで移行SQLと復元を実行します。ブラウザテストは架空データを使い、390px幅とデスクトップで保存、途中再開、自己採点を確認します。既存Chromiumを使う場合は、実行ファイルを `STUDY_CHROMIUM_PATH` で指定できます。

Supabaseに接続する場合は `.env.example` を参照し、`.env.local` にSupabase URLと公開用キー（`sb_publishable_`）を設定します。管理者のキーは画面用の環境変数から分離し、移行CLIだけに渡します。

## 学習の流れ

- **本日のノルマ**は原文単位です。原文なしカードは単独で1件として扱います。1穴ずつ答えを表示して評価を保存し、当日中は別端末でも次の穴から続けられます。
- **自由演習**では科目、分野タグ、ランク、カードタイプなどを組み合わせます。条件を保存して次回も呼び出せます。ミニテストは全問の解答後に答えと照合します。
- **カード管理**は `【】` で指定した約半数を隠す組み合わせを作ります。プレビュー上部から全件を保存できます。再生成で置き換えたカードは参照用一覧で開けます。
- **統計**から完全バックアップ（JSON）を保存できます。CSVはカード一覧用の形式で、原文との紐づきや履歴を保全する場合はJSONを使います。

## 隔離環境の準備と公開の条件

1. 既存の基礎スキーマを隔離環境に復元し、`supabase/migrations` の未適用分を時系列に適用します。旧版の `daily_assignments` を残します。埋め込みDBの検証と別に、実際のSupabaseでAuth、API、Googleリダイレクトを検証します。
2. Supabase AuthでGoogleを有効化し、採用するWeb版のオリジンと固定ルートをリダイレクトの許可リストに登録します。新規登録時には `study_private.check_invitation` を Before User Created Hook に設定します。運用者が `study_private.invitations` に許可するメールアドレスを登録し、認証後に確認した `auth.users.id` と既存の `public.users.id` を `study_private.identities` で1対1につなぎます。招待解除は許可リストの登録を削除します。
3. 静的配信は `npm run build` の `dist/` と `wrangler.jsonc` を使います。既定のCSPは標準の `*.supabase.co` への接続を許可しています。配信前に設定済みURL、匿名アクセス、未招待、別利用者、2端末での保存を確認します。旧聞き流しURLは復習へ転送します。

## 全原文を移行

作業ファイルには本文、答え、履歴が含まれます。保存先はGit管理外の `../.states/` とします。次のコマンドは `web/` から実行します。`SUPABASE_URL` と `SUPABASE_SECRET_KEY` は管理者の実行環境だけに設定してください。

```sh
node scripts/migrate.ts snapshot <existing-user-id> ../.states/legacy.json
npm run prepare-migration -- ../.states/legacy.json ../.states/regeneration.json
```

- オフラインの計画生成で、新規・引き継ぎ・参照保管の件数と例外を出します。`reconciliation` を確認し、例外は旧カードで継続するか元の原文を直すかを判断します。手編集のカードは内容と履歴を保管します。次回期日が最も早いカードの進捗と当日の完了を、原文単位の状態に引き継ぎます。
- 空の隔離DBへ完全バックアップを復元し、所有者、原文、カード、履歴、保存条件、例外の内訳を照合します。旧Streamlit版と新Web版の同時書き込みを防ぎ、書き込み停止後の最新スナップショットから計画を作り直します。
- 公開とデータ変更の承認後に限り、最終計画を `node scripts/migrate.ts apply <existing-user-id> ../.states/regeneration.json --cutover-confirmed` で確定します。DBに渡した元スナップショットと現在の内容が異なる場合、処理全体が停止します。同一計画の再実行は記録済みの結果を返します。
- 本番にはGoogle認証付きのWeb版を使用します。旧Streamlit版の本番用URLはWeb版に案内します。障害時は新しい履歴を保全し、直前の互換Web版かメンテナンス表示を使って復旧します。


## 更新を公開する

1. Pythonの標準チェック、Webの型検査・ビルド・テスト、ブラウザーテストを実行する。WindowsでPlaywrightのサーバー終了に問題がある場合は、架空データ向けの環境変数でViteを起動し、`STUDY_REUSE_TEST_SERVER=1` で同じテストを実行する。
2. 追加DBマイグレーションを検証環境で適用する。バックアップの復元、認証、2端末の保存、旧版互換を確認する。
3. 配信先のURLと公開キーを設定してコミット済みの版をビルドする。`node scripts/prepare-release.ts` で直リンクと `release.json` を生成し、既存のWorkerへアップロードする。検証は `memorization-web-staging`、本番は `memorization-web` を使う。
4. 公開後は `APP_HEALTH_URL` を付けた `scripts/health_check.py` で公開ルート、ハッシュ、Googleログイン設定、匿名APIの拒否を確認する。本番のGoogleアカウントによるログインと、専用テスト用データでの実機試験は別に確認する。

Cloudflareの旧版を復元するときも追加マイグレーションを保つ。新版で作成された学習履歴を保全してから復旧する。Supabase停止時は、管理画面でプロジェクトを復元してからヘルスチェックとログインを確認する。

### 性能と復元の再検証

- `npm test` で架空の原文545件とカード2,727枚を読み込み、初回JSONサイズと演習の分割取得を確認する。検証用Supabaseで再計測する場合は `test/fixtures/measure-stage.sql` に同じ架空データを埋め込み、結果の取得後にロールバック済みであることを照合する。
- 架空の公開設定で生成した静的ビルドをプレビューし、`STUDY_BENCHMARK=1` と `STUDY_REUSE_TEST_SERVER=1` を指定して `npm run test:browser -- --project mobile -g "cold mobile"` を実行する。CDPと架空API応答の待ち時間で、390px・下り10 Mbps・上り2 Mbps・往復150ms・CPU 4倍低速を再現する。旧本番の静的ファイルを同じ方法で測る場合は、別ポートで配信して `STUDY_BASELINE=1` を指定する。
- 本番反映前の読み取り専用スナップショットをGit管理外へ保存する。利用者別の完全バックアップを `{"snapshots":[{"backup":{...}}]}` として渡し、`STUDY_BACKUP_AUDIT` にそのファイルを指定して `node --test --test-name-pattern="local preflight backup" test/database.test.ts` を実行する。復元先は、このテストが手元で作る空のDB。
