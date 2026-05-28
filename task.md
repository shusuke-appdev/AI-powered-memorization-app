# Tasks

- [x] 検証環境を再作成し、`ruff check .` と `pytest tests` を実行可能にする <!-- id: 1 -->
- [x] パスワード認証とGemini/APIキー関連機能を撤去する <!-- id: 2 -->
- [ ] Supabase上の既存 `users.api_key` 値を削除する <!-- id: 3 -->
- [ ] Supabase初期スキーマSQLを作成し、既存 `migration_*.sql` を整理する <!-- id: 4 -->
- [ ] 不要になった `users.password_hash` / `users.api_key` の削除マイグレーションを検討する <!-- id: 5 -->
- [ ] `Card` / `SourceCard` / `UserSettings` などの型付きモデルを導入する <!-- id: 6 -->
- [ ] DB操作をRepository層に集約する <!-- id: 7 -->
- [ ] カード作成、復習評価、再生成、インポートをUse case層へ分離する <!-- id: 8 -->
- [x] HTML描画に入るユーザー入力をエスケープする共通レンダリング関数を作る <!-- id: 9 -->
- [x] ハイライト処理を安全なHTML生成方式に置き換える <!-- id: 10 -->
- [x] インポートの `skip` / `create_duplicate` 仕様を実装する。`update_existing` は未対応としてUI非表示を維持する <!-- id: 11 -->
- [x] JSONエクスポート/インポートで原文カードと暗記カードの紐づきを復元する <!-- id: 12 -->
- [x] 日次ノルマをDB保存する設計を実装し、セッション依存を減らす <!-- id: 13 -->
- [ ] 穴埋め生成の乱数を排除またはseed注入にする <!-- id: 14 -->
- [x] インポート、HTMLエスケープ、ノルマ変更のテストを追加する <!-- id: 15 -->
- [ ] Streamlit主要フローの手動/自動E2E検証手順を作る <!-- id: 16 -->
- [x] GitHub Actionsでruffとpytestを実行する <!-- id: 17 -->
