# 開発ガイド

## 前提

- Python 3.10 以上
- Supabaseプロジェクト
- Streamlit

## ローカル起動

```powershell
pip install -r requirements.txt

$env:SUPABASE_URL = "https://xxx.supabase.co"
$env:SUPABASE_KEY = "eyJ..."

streamlit run app.py
```

## 環境変数

| 名前 | 必須 | 用途 |
| --- | --- | --- |
| `SUPABASE_URL` | 必須 | SupabaseプロジェクトURL |
| `SUPABASE_KEY` | 必須 | Supabase APIキー |
Streamlit Cloudでは `.streamlit/secrets.toml` 相当のSecretsに同名で設定します。

本番運用前に必要な作業:

- ログイン画面のユーザー一覧に、本番で使うユーザーだけが表示されるように整理する。
- 既存の `users.api_key` に値が残っている場合は不要なので削除する。

## データベース

現状のSQLは差分マイグレーションのみです。

- `migration_rls.sql`: RLSを有効化し、全テーブルをpublicから拒否する。
- `migration_type.sql`: `card_type` を追加する。
- `migration_rank.sql`: `rank`, `daily_quota`, `highlighted_keywords` を追加する。

不足しているもの:

- 初期スキーマ作成SQL
- 外部キー、NOT NULL、CHECK制約、インデックスの明文化
- マイグレーション適用順序の管理
- ロール別RLSポリシー

## 品質確認

通常は次を実行します。

```powershell
ruff check .
pytest tests
```

このワークスペースでは `ruff` と `pytest` がPATHに存在せず、同梱 `venv\Scripts\python.exe` も起動できませんでした。検証環境を再作成する場合は、新しい仮想環境を作って依存関係を入れ直してください。

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest tests
```

## テスト方針

現状のテストは `services.card_service` と `services.review_service` の純粋ロジックが中心です。

優先して追加すべきテスト:

- 認証/セッションの境界条件
- 日次ノルマ変更時の既レビュー済みカード保持
- `source_id` 単位の出題重複制御
- 知識/類型カードのハイライト
- JSON/CSVインポートの型変換と重複処理
- 管理画面の再生成時に原文と暗記カードの整合性が保たれること
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
