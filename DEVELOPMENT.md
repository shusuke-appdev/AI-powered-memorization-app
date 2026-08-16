# 開発ガイド

## 前提

- Python 3.12
- Supabaseプロジェクト
- Streamlit

## ローカル起動

```powershell
python -m pip install -r requirements.txt -c constraints.txt

$env:SUPABASE_URL = "https://xxx.supabase.co"
$env:SUPABASE_KEY = "eyJ..."

streamlit run app.py
```

## 環境変数

| 名前 | 必須 | 用途 |
| --- | --- | --- |
| `SUPABASE_URL` | 必須 | SupabaseプロジェクトURL |
| `SUPABASE_KEY` | 必須 | Supabase APIキー |
| `APP_TIMEZONE` | 任意 | アプリの日付基準。未指定時は `Asia/Tokyo` |
Streamlit Cloudでは `.streamlit/secrets.toml` 相当のSecretsに同名で設定します。

本番運用前に必要な作業:

- ログイン画面のユーザー一覧に、本番で使うユーザーだけが表示されるように整理する。
- 既存の `users.api_key` に値が残っている場合は不要なので削除する。

## データベース

新規変更はSupabase CLI管理の `supabase/migrations/` に加算的に追加します。ルート直下の
`migration_*.sql` はCLI導入前の履歴であり、適用済み環境へ再適用しません。

```powershell
supabase migration new <name>
supabase db push
```

現行のpublic schemaは、既存migrationより前に作られた基礎テーブルを含むため、通常の
`db pull` ではshadow DBへ履歴を再生できません。リモートのmigration履歴を修正せず、
宣言的スナップショットを更新するときは次を使います。出力先は `supabase/database/` です。

```powershell
supabase db pull --linked --schema public --declarative --yes
```

`supabase/database/` は現行スキーマの確認・基準化用です。新規変更の適用単位は引き続き
`supabase/migrations/` の加算的migrationとし、生成差分は必ずレビューしてから適用します。

2026-08-01時点では、日次割当同期、復習完了、原文カード一括保存・削除、バックアップ
インポートをRPC内の1トランザクションで処理します。RPCは `SECURITY INVOKER`、固定
`search_path`、完全修飾テーブル名を使い、実行権限は `service_role` のみに付与します。

CLI導入前の差分SQL:

- `migration_rls.sql`: RLSを有効化し、全テーブルをpublicから拒否する。
- `migration_data_api_grants.sql`: Supabase Data API向けに明示GRANTを設定する。現行運用では `service_role` のみに `users`, `sessions`, `cards`, `source_cards`, `daily_assignments` のCRUD権限を付与し、`anon` / `authenticated` には付与しない。
- `migration_type.sql`: `card_type` を追加する。
- `migration_rank.sql`: `rank`, `daily_quota`, `highlighted_keywords` を追加する。
- `migration_daily_assignments.sql`: 日次ノルマ割当をDB保存する `daily_assignments` を追加する。
- `migration_daily_assignment_index_and_policy_cleanup.sql`: `daily_assignments.source_id` の補助インデックスを追加し、現行運用で不要な古い `source_cards` RLSポリシーを削除する。

既存DBへの推奨適用順:

1. `migration_type.sql`
2. `migration_rank.sql`
3. `migration_daily_assignments.sql`
4. `migration_daily_assignment_index_and_policy_cleanup.sql`
5. `migration_rls.sql`
6. `migration_data_api_grants.sql`

Supabase Data APIの運用ルール:

- RLSは「行単位の可視性」、GRANTは「Data APIからテーブルへ到達できるか」を制御する別レイヤー。
- このアプリはStreamlitサーバー側からSupabase Python clientを使うため、`SUPABASE_KEY` は公開クライアント用のanon keyではなく、サーバー側だけで秘匿するservice role/secret系キーを使う。
- 新しいテーブルを追加するときは、テーブル作成SQL、RLS設定、必要最小限のGRANTを同じ変更に含める。
- ブラウザや外部クライアントからSupabaseへ直接アクセスする構成に変える場合は、`anon` / `authenticated` へのGRANTと所有者ベースのRLSポリシーを別途設計する。

今後の保留事項:

- ロール別RLSポリシー

## 品質確認

通常は次を実行します。

```powershell
.\.venv\Scripts\python.exe scripts\check.py
```

GitHub CLI と Supabase の運用ヘルスチェックは次で実行できます。`SUPABASE_URL` /
`SUPABASE_KEY` は環境変数または `.streamlit/secrets.toml` から読み込まれます。値は
出力されません。

```powershell
.\.venv\Scripts\python.exe scripts\health_check.py
```

DBマイグレーション前には、対象環境の復元可能なバックアップを確認します。ローカルの
論理バックアップは秘密列とセッションを除外して次で作成できます。

```powershell
.\.venv\Scripts\python.exe scripts\backup_user_data.py
```

Supabase Free Planでは管理された日次バックアップを利用できないため、完全なローカル論理
バックアップが必要な場合は、Docker Engineを起動して公式CLIでschema、data、rolesを別々に
保存します。データダンプは秘密列を含み得るので、Git管理外の `.states/` に保存し、内容を
ログへ出力しないでください。

```powershell
supabase db dump --linked --schema public --file .states\supabase_schema.sql
supabase db dump --linked --data-only --use-copy --schema public --file .states\supabase_data.sql
supabase db dump --linked --role-only --file .states\supabase_roles.sql
```

資格情報を使う公開前確認は、通常のrelease gateと分離して実行します。

```powershell
.\.venv\Scripts\python.exe scripts\live_smoke.py
```

検証環境を再作成する場合は、新しい仮想環境を作って依存関係を入れ直してください。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c constraints.txt
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider -q
```

## テスト方針

現状のテストはカード生成、復習、セッション分離、JSON/CSVインポート、書き込み
ユースケース、Repository契約、Streamlit AppTest、ページング、日付境界を対象にします。

優先して追加すべきテスト:

- `source_id` 単位の出題重複制御
- 知識/類型カードのハイライト
- 実PostgreSQLでの同時実行競合テスト
- HTMLエスケープ

## 実装ルール

- UI、ユースケース、DB操作を混ぜない。
- 新しいDB項目を追加するときは、マイグレーション、DTO変換、インポート/エクスポート、統計、テストを同時に確認する。
- Streamlitの `unsafe_allow_html=True` にユーザー入力を渡す場合は必ずHTMLエスケープする。
- 既存データを壊す変更は、移行手順とロールバック手順を書く。
- 乱数を使うロジックはテストでseedまたは注入可能にする。

## 運用メモ

- Supabaseキーは公開リポジトリ、ログ、スクリーンショットに出さない。
- RLS全拒否 + 強いキーでのアプリ操作は、アプリサーバーが完全に信頼できる場合の暫定設計として扱う。
- Streamlit CloudのSecrets設定とSupabaseのキー権限を定期確認する。
- Supabase DashboardのSecurity Advisorで、Data APIに公開されているテーブルとRLS警告を定期確認する。
- migration適用後は、`scripts/live_smoke.py` で一時データの作成・割当同期・復習二重送信・削除と残骸ゼロを確認する。

GitHub Actions の `Health Check` workflow は、UTCの0時・8時・16時台
（JSTの1時17分・9時17分・17時17分ごろ）と手動実行時に
`scripts/health_check.py` を実行します。1日3回の読み取りはFree Planの
自動停止を避けるためのbest-effortであり、停止しないことを保証するものではありません。

- GitHub repository secrets に `SUPABASE_URL` と `SUPABASE_KEY` を設定する。
- `GH_TOKEN` は workflow 内で `${{ github.token }}` を使うため、手動設定しない。
- workflow はpush/PRでは動かさず、外部PRへSupabase secretsを渡さない。
- `SUPABASE_URL または SUPABASE_KEY が未設定` はGitHub secrets不足。
- `DNS 解決できません` はSupabase Free Planのプロジェクト停止、URL誤り、または一時DNS障害を疑う。
- `Supabase の読み取り確認に失敗` はキー権限、RLS/GRANT、テーブル到達性を確認する。
- `GitHub CLI/API` の失敗はGitHub Actions runner、`github.token` 権限、またはGitHub側障害を切り分ける。

Supabase Free Planでは低活動プロジェクトが停止されることがあります。定期ヘルスチェックが
失敗した場合もエラーを抑制せず、プロジェクト状態と接続障害を確認します。停止を保証付きで
避ける必要がある場合は、有料Planを検討してください。
