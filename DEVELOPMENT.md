# 開発ガイド

## 前提

- Python 3.10 以上
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

現状のSQLは差分マイグレーションのみです。

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

不足しているもの:

- 初期スキーマ作成SQL
- 外部キー、NOT NULL、CHECK制約、インデックスの明文化
- マイグレーション適用順序の管理
- ロール別RLSポリシー

## 品質確認

通常は次を実行します。

```powershell
ruff format --check .
ruff check .
pytest tests -p no:cacheprovider -q
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

現状のテストは `services.card_service`, `services.review_service`, JSONバックアップ復元、書き込みユースケース、ページング、日付境界のロジックが中心です。

優先して追加すべきテスト:

- 認証/セッションの境界条件
- 日次ノルマ変更時の既レビュー済みカード保持
- `source_id` 単位の出題重複制御
- 知識/類型カードのハイライト
- SupabaseをmockしたRepository/Use case統合テスト
- Streamlit主要画面のE2Eまたはコンポーネントテスト
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
- `migration_daily_assignments.sql` と `migration_data_api_grants.sql` 実行後は、ログイン、カード追加、復習更新、統計表示、削除、同日再ログイン時のノルマ維持を本番相当データで1件ずつ確認する。ローカルSecretsがある環境では `python scripts/live_smoke.py` でサービス層の最小確認ができる。
