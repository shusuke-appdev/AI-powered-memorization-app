# 根本改修計画

目的は、現行機能の維持だけでなく、データ保全、将来の機能追加、障害予防を成立させることです。パスワード認証とGemini API利用は廃止し、ユーザー選択ログインと手動カード生成を前提にします。

## フェーズ0: 検証環境の復旧

- 新しい `.venv` を作成し、依存関係を再インストールする。
- `ruff check .` と `pytest tests` をローカルで通す。
- GitHub Actionsなどで同じ検証を自動化する。
- `scripts/check.py` の自動インストールと `shell=True` を見直し、CI向けの明示コマンドにする。

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

- JSONスキーマのバージョンを明文化する。
- エクスポートに `card_type`, `rank`, `highlighted_keywords`, `source_id` の扱いを明記する。
- インポート前にdry-run結果を表示する。
- `skip`, `create_duplicate`, `update_existing` を明確に分ける。
- 原文カードと暗記カードの紐づきを維持して復元する。
- 型変換エラーを行単位で報告する。

完了条件:

- エクスポート後に同一ユーザー/別ユーザーへ復元してもカード数と紐づきが一致する。
- 「上書き」の意味がUIと実装で一致する。

## フェーズ6: 日次ノルマと学習体験の安定化

- `daily_assignments` テーブルを検討する。
- 日付、ユーザー、カードID、出題順、完了状態を保存する。
- ノルマ変更時の補充ロジックをUse case化する。
- 複数デバイスで同じ当日ノルマを共有する。
- 穴埋め生成の乱数を排除またはseed化する。

## フェーズ7: テスト拡充

- 純粋ロジックテストを拡充する。
- RepositoryはSupabaseをmockする単体テストと、テストDBでの統合テストを分ける。
- Streamlit画面は主要フローをPlaywrightまたはStreamlit testingで確認する。
- HTMLエスケープ、インポート、ノルマ変更の回帰テストを追加する。

## すぐ着手すべき修正候補

1. Python検証環境を作り直し、テストを実行する。
2. `users.api_key` の既存値をSupabase上で削除する。
3. `pages/add_card_page.py` のプレビューHTMLもエスケープする。
4. 初期スキーマSQLを作り、外部キーとインデックスを追加する。
5. インポートのdry-runと本当の上書き処理を設計する。
