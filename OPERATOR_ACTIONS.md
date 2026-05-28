# 運用者が行う必要がある作業

このファイルは、コード変更だけでは完了できない設定・運用作業のチェックリストです。

## すぐ必要

- [ ] Streamlit Cloud または実行環境で `SUPABASE_URL` と `SUPABASE_KEY` を設定する。
- [ ] パスワード認証やGemini APIキーに関する古いSecretsが残っていれば削除する。
- [ ] ログイン画面のユーザー一覧に、本番で使うユーザーだけが表示されるように整理する。
- [ ] Python実行環境を作り直し、`ruff check .` と `pytest tests` を実行できる状態にする。

## Supabaseで確認すること

- [x] 現在使っているローカル `SUPABASE_KEY` の権限が `service_role` であることを確認する。
- [ ] Streamlit Cloudなど本番実行環境の `SUPABASE_KEY` がサーバー側だけで使われるservice role/secret系キーであり、ブラウザ、公開リポジトリ、ログ、画面共有に露出していないことを確認する。
- [x] Supabase Dashboard相当のSecurity Advisorで、Data APIに公開されているテーブルとRLS警告を確認する。
- [x] Supabase MCPで `migration_data_api_grants.sql` 相当を適用し、`users`, `sessions`, `cards`, `source_cards` が現行のサーバー側キーで読み書きできることを確認する。
- [ ] `supabase_admin` 所有のdefault privilegesはMCPの `postgres` 権限では変更できないため、新規テーブルをDashboard UI等で作る場合も必ず同じ変更内で明示GRANTを確認する。
- [ ] `cards.user_id`, `source_cards.user_id`, `sessions.user_id` のデータが想定ユーザーに紐づいていることを確認する。
- [ ] 既存の `users.api_key` に値が入っている場合、不要なので削除する。

## 変更後の確認観点

- [ ] ログイン画面でユーザー名ボタンからログインできる。
- [ ] 新規登録フォームにパスワード欄やGemini APIキー欄が表示されない。
- [ ] サイドバーにGemini APIキー設定やヘルプAIが表示されない。
- [ ] 通常の復習・カード追加・統計表示が使える。
- [x] `migration_data_api_grants.sql` 実行後も、サービス層経由でログイン相当、カード追加、復習更新、統計用読込、削除がそれぞれ1件ずつ成功する。
- [ ] カード本文に `<script>` や `<b>` のような文字列を入れてもHTMLとして実行・解釈されない。
- [ ] インポート画面の重複処理が「スキップ」「重複として追加」と表示される。
