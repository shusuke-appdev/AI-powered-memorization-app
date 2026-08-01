# 根本改修計画

目的は、現行機能の維持だけでなく、データ保全、将来の機能追加、障害予防を成立させることです。パスワード認証とGemini API利用は廃止し、ユーザー選択ログインと手動カード生成を前提にします。

> 2026-08-01追記: この文書は旧計画の記録です。ユーザー分離、入力検証、主要な複数行更新のRPC化、インポートプレビュー、AppTestは完了しました。残件は `task.md` と `progress.md` を正とします。

## フェーズ0: 検証環境の復旧

- 完了: `.venv` で `ruff` / `pytest` を実行可能。
- 完了: GitHub Actionsで `ruff format --check .`, `ruff check .`, `pytest tests -p no:cacheprovider -q` を自動実行。
- 完了: `scripts/check.py` を自動インストール/自動修正なしの検証コマンドに変更。

完了条件:

- クリーン環境でセットアップからテストまで再現できる。
- 既存テストが全パスする。

## フェーズ1: 廃止済み機能の残骸整理

- パスワード認証コード、Gemini APIコード、APIキーUIを削除済み。
- 既存DBの `users.password_hash` と `users.api_key` はスキーマ互換用として残すが、アプリでは使わない。
- Supabase上で既存 `api_key` 値が残っている場合は削除する。

完了条件:

- 画面にパスワード欄、APIキー欄、ヘルプAIが表示されない。
- 依存関係に `google-genai` と `bcrypt` が残らない。

## フェーズ2: DBスキーマ整理

- 初期スキーマSQLを作成する。
- マイグレーションの適用順序を管理する。
- `cards`, `source_cards`, `users`, `sessions` の制約を明文化する。
- `cards.source_id` の外部キーを定義する。
- `rank`, `card_type`, `category` にCHECK制約を検討する。
- `user_id`, `next_review`, `source_id` に必要なインデックスを作る。
- 不要になった `users.password_hash` と `users.api_key` の削除マイグレーションを検討する。

完了条件:

- 新規DBをSQLだけで再現できる。
- 原文削除、カード削除、インポートで整合性が壊れない。

## フェーズ3: ドメインモデルとUse case層の導入

- `models.py` または `domain/` に型付きモデルを作る。
- `Card`, `SourceCard`, `UserSettings`, `ReviewProgress`, `DailyQuota` を定義する。
- `repositories/` にDBアクセスを集約する。
- `use_cases/` にカード作成、復習評価、原文再生成、インポートを分離する。
- UIはUse caseを呼び、DBテーブルを直接意識しないようにする。

完了条件:

- `pages/*` から `supabase.table(...)` 相当の知識が消える。
- 新しいカード属性を追加するときの変更箇所が明確になる。
- 型変換とバリデーションがテストされる。

## フェーズ4: HTML描画と入力安全性の完成

- `html.escape()` ベースの安全なカードレンダリング関数を全プレビューへ広げる。
- タイトル、カテゴリ、問題、答え、原文を必ずエスケープする。
- ハイライトはエスケープ済み文字列に対して安全にspanを挿入する。
- `unsafe_allow_html=True` の利用箇所を棚卸しし、必要箇所だけに限定する。
- `components.py` のJSON埋め込みとHTML構造をテストする。

完了条件:

- `<script>`, `<style>`, 壊れたHTMLをカードに入れても画面が壊れない。
- ハイライト表示が維持される。

## フェーズ5: インポート/エクスポートの仕様確定

- 完了: JSONスキーマを `2.0` にし、原文カードの `export_id` と暗記カードの `source_export_id` で紐づきを復元する。
- 完了: エクスポート/インポートで `card_type`, `rank`, `highlighted_keywords`, `source_id`, SM-2進捗を扱う。
- インポート前にdry-run結果を表示する。
- 完了: `skip`, `create_duplicate` を明確化。`update_existing` は未実装としてUI非表示を維持する。
- 完了: 原文カードと暗記カードの紐づきを維持して復元する。
- 型変換エラーを行単位で報告する。

完了条件:

- エクスポート後に同一ユーザー/別ユーザーへ復元してもカード数と紐づきが一致する。
- 「上書き」の意味がUIと実装で一致する。

## フェーズ6: 日次ノルマと学習体験の安定化

- 完了: `daily_assignments` テーブルを追加するマイグレーションを作成。
- 完了: 日付、ユーザー、カードID、出題順、完了状態を保存する。
- ノルマ変更時の補充ロジックをUse case化する。
- 完了: 適用済みDBでは複数セッションで同じ当日ノルマを共有する。
- 穴埋め生成の乱数を排除またはseed化する。

## フェーズ7: テスト拡充

- 純粋ロジックテストを拡充する。
- RepositoryはSupabaseをmockする単体テストと、テストDBでの統合テストを分ける。
- Streamlit画面は主要フローをPlaywrightまたはStreamlit testingで確認する。
- HTMLエスケープ、インポート、ノルマ変更の回帰テストを追加する。

## すぐ着手すべき修正候補

1. Streamlit実機で主要フローを確認する。
2. `users.api_key` の既存値をSupabase上で削除する。
3. `migration_daily_assignments.sql` を本番相当DBへ適用する。
4. 初期スキーマSQLを作り、外部キーとインデックスを追加する。
5. インポートのdry-runと本当の上書き処理を設計する。
