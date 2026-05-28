# Progress — AI暗記カードアプリ

## 最終更新: 2026-05-28

## 完了済み

### プロダクト改善ロードマップ実装（2026-05-28）
- **データ保全**: JSONバックアップをv2スキーマ化し、`source_cards` の `export_id` と `cards.source_export_id` の対応表で復元時の `source_id` を張り直すように変更。`rank`, `card_type`, `highlighted_keywords`, SM-2進捗, `blank_count`, `is_favorite` も維持する。
- **書き込み整合性**: `use_cases/card_workflows.py` を追加し、カード作成・再生成・インポートの複数DB書き込みを集約。作成途中で失敗した場合は作成済みカード/原文を削除し、再生成では新カード作成成功後に旧カードを削除する。
- **日次ノルマ永続化**: `migration_daily_assignments.sql` と `storage.py` の `daily_assignments` CRUDを追加。適用済みDBでは当日割当と完了状態を保存し、未適用DBでは従来のセッション状態へフォールバックする。
- **スケール/運用品質**: `storage.py` のカード/原文読み込みをページング化し、CI workflow と読み取り専用の `scripts/check.py` に更新。アプリ基準日は `services/time_service.py` で日本時間に統一。
- **検証**: `ruff format --check .`, `ruff check .`, `pytest tests -p no:cacheprovider -q` は25件成功、`compileall`, `python scripts/check.py` も成功。`streamlit run app.py --server.port 8501 --server.headless true` はHTTP 200応答、`python app.py` の直接実行もStreamlit bare mode警告のみで終了。in-app browser確認はCodex側sandboxで接続できず未実施。
- **ライブ確認**: Supabase MCPで `daily_assignments`, `daily_assignments_data_api_grants`, `daily_assignment_index_and_policy_cleanup` を適用。Security Advisorは警告0件。Performance Advisorは未使用インデックスINFOのみ。`scripts/live_smoke.py` でログイン相当、セッション作成/削除、一時カード追加、復習進捗更新、日次割当保存/完了、削除と残骸0件を確認。

### Supabase Data API明示GRANT対応（2026-05-28）
- **背景**: SupabaseのData API仕様変更により、`public` schemaの新規テーブルはPostgREST / GraphQL / Supabase clientから使う前に明示GRANTが必要になる。
- **方針**: 現行どおりStreamlitサーバー側でSupabaseキーを秘匿する運用を前提に、`anon` / `authenticated` ではなく `service_role` のみに既存4テーブルのData API権限を明示する。
- **修正**: `migration_data_api_grants.sql` を追加し、将来オブジェクトの自動公開default privilegesを取り消し、`users`, `sessions`, `cards`, `source_cards` への `service_role` CRUD権限を明示。`migration_rls.sql`, `DEVELOPMENT.md`, `OPERATOR_ACTIONS.md` にRLSとGRANTの役割分担、Security Advisor確認、SQL実行後の確認観点を追記。
- **本番適用**: Supabase project `zozsikyinpasapuxjbtg` に `data_api_explicit_grants` と `tighten_postgres_public_default_privileges` を適用。4テーブルの `anon` / `authenticated` 権限は消え、`service_role` はCRUDのみになった。Security Advisorは `lints: []`。
- **本番検証**: 一時データ `codex-grant-smoke-20260528` でログイン相当、原文追加、カード追加、復習更新、読込、削除を確認。件数は `users=4`, `sessions=102`, `source_cards=122`, `cards=189` に戻った。
- **残件**: `supabase_admin` 所有のdefault privilegesはMCPの `postgres` 権限では変更できないため、新規テーブルをDashboard UI等で作る場合も必ず同じ変更内で明示GRANTを確認する。

### 本日のノルマ初回1枚化バグ修正とアプリ本体点検（2026-05-20）
- **不具合**: アプリ起動直後、本日のノルマが20枚あるユーザーでも特定カード1枚だけが表示され、その1枚を消化すると正規の20枚分が現れる状態になっていた。
- **原因**: `select_hybrid_quota()` の穴埋め数調整で、同じ高blankカードが同一選定結果に何度も再投入され、20件の候補が同一ID20件になっていた。その後 `reconcile_daily_quota()` が重複IDを1件に畳むため、初回だけ1枚表示になっていた。
- **修正**: `_adjust_to_target_blanks()` をカードID一意性前提に直し、入れ替えごとに未選定候補を再計算し、戻り値直前にも一意IDで不足分を補充するように変更。回帰テストを追加し、アプリ本体の整形、型注釈、検証スクリプトの `shell=True` 排除も実施。
- **検証**: `pytest tests -p no:cacheprovider -q` は18件成功。`ruff check .`、`ruff format --check .`、`compileall` も成功。ライブDBのノルマ20ユーザーで due 178件から初回割当20件・一意20件を確認。

### ノルマカード選定の重複ID補正（2026-05-15）
- **不具合**: 本日のノルマ上限が20枚でも、セッション内の `quota_card_ids` に同一カードIDが重複して入ると、表示上は「0 / 20」なのに残りが1枚になる。
- **原因**: ノルマ選定結果のIDリストを正規化せず、表示時に `set` 化した結果、重複IDが1枚分に潰れていた。
- **修正**: `reconcile_daily_quota()` を追加し、重複ID・削除済みID・ノルマ変更後の既レビュー済みカードを補正してから、不足分だけdueカードで補充するように変更。重複候補が選定結果に混入しない回帰テストも追加。

### ログイン・カード生成機能のシンプル化＆管理画面の利便性向上（2026-05-13）
- **ログイン画面**: パスワード機能を廃止。登録ユーザー一覧からのワンクリックログインに変更。
- **カード生成（AI廃止）**: 自動文節分割・穴埋め提案を廃止。手動（【】指定）による作成フローに一本化し操作を簡略化。
- **管理画面の保存ボタン制御**: 変更がない場合は「保存」ボタンを非活性化。保存時には「原文、カード1の問題」など変更箇所を詳細にフィードバック。
- **カード再生成（上書き）**: 管理画面上で原文を編集し、「カードを再生成」してプレビュー表示・一括上書きするフローを追加。

### カード生成アルゴリズム全面修正 & UI二重rerunの完全排除（2026-05-01）
- **カード生成アルゴリズム全面修正（正しい仕様に準拠）**: 旧ロジックではユーザーが指定した穴埋め箇所が5個未満の場合に、アルゴリズム側で勝手に非選択文節をフィラーとして追加選定していた。これは仕様に反するため、フィラー追加ロジック（`_get_filler_groups`, `_get_adjacent_indices`）を全面削除。正しい仕様: ①穴埋め箇所5個以下→指定箇所のみで1枚生成 ②穴埋め箇所6個以上→ceil(N/5)枚のカードを生成し、各カードにユーザー指定の穴埋め箇所から5箇所ずつ割り当て（最後のカードが5箇所未満の場合は他カードの穴埋め箇所から重複補充）。また `build_card_from_groups` を `idx_to_group` マッピング方式に改修し、隣接グループが正しく独立した穴埋めとして描画されるようにした。

- **UI二重rerun排除**: `pages/add_card_page.py`にて、「AIに提案させる」ボタンおよび文節のトグルボタンで意図せず発生していた不要な`st.rerun()`を削除。とくにトグルボタンは状態更新を`on_click`コールバック（`_toggle_phrase`）に移行し、スクリプト実行前に状態を反映させることで、UIの「謎の画面更新（チラつき・二重リロード）」を完全に排除。

### カード生成ロジック修正 & ページ更新バグ修正（2026-04-28）
- **穴埋め5箇所保証**: `generate_cards_from_selection` で穴埋め箇所が5未満の場合、非選択の実質的文節からランダムにフィラーを追加して必ず5箇所にする。フィラー同士・既存穴埋めとの隣接を回避する逐次選択方式を実装
- **謎のページ更新修正**: 
  - `CookieController` を `st.session_state` にシングルトン化し、毎rerunでの再インスタンス化による予期しないrerunを防止
  - `add_card_page.py` のテキスト入力ウィジェットで `value=` + `key=` の二重指定パターンを排除。`key` によるsession_stateの自動管理 + `on_change` コールバック方式に統一
  - `sidebar.py` のログアウト処理でも `CookieController` のシングルトンを再利用し、クッキー削除後に `time.sleep(0.5)` で反映を待機


### ノルマ数変更バグ修正（2026-04-27）
- **不具合**: ノルマ数を変更すると既達成分がリセットされ残ノルマが不正になる
- **原因**: `quota_card_ids`をNullリセット→再選択時に既レビュー済みカードを考慮していなかった
- **修正**: ノルマ変更時は既レビュー済みカードを維持し、不足分のみ新規選択する方式に変更。進捗表示も`quota_card_ids ∩ reviewed_card_ids`で正確に算出するように修正

### UI改善および出題メカニズム改修（2026-04-19）
- **UI修正**: Streamlitのネイティブサイドバー用メニュー（ページ選択）をCSSで完全に非表示化
- **復習ロジック改善**: 科目（カテゴリ）間の偏りをなくすため、1日の出題カードを各科目から均等に選定する「ラウンドロビン方式」を導入。暗記カードが0枚の科目も安全にスキップする仕様に修正

### コードベース総合改善（2026-04-13）
- **app.py 分割**: 2595行 → ~100行。pages/ + services/ の3層アーキテクチャに
- **CSS外部化**: styles/ ディレクトリに base.css / dark_mode.css / mobile.css
- **サービス層**: ai_service.py（Geminiシングルトン）、review_service.py（SM-2）、card_service.py（カード生成）
- **品質改善**: Type Hints全面導入、エラーハンドリング共通化（QuotaExceededError）
- **バグ修正**: 円グラフ色分け、統計重複排除、N+1クエリ修正
- **パフォーマンス**: setベース比較（O(n²)→O(n)）
- **テスト**: tests/ ディレクトリ化、6件全パス
- **検証**: ruff All checks passed

## 今後の課題
- [ ] APIキー暗号化（Fernet対称暗号）
- [ ] auth.py / storage.py のType Hints追加
- [ ] DB操作・エクスポートの統合テスト追加
- [ ] Streamlit実機での全タブ動作確認
