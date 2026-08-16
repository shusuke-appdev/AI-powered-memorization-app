# Progress — AI暗記カードアプリ

## 最終更新: 2026-08-16

## 継続中

- なし

## 完了済み

### Supabase復元とHealth Check頻度変更（2026-08-16）
- **障害原因と復元**: 2026-08-13のGitHub Actions失敗は、repository secrets不足ではなく、Free PlanのSupabaseプロジェクトが `INACTIVE` となりDNS解決できなかったことが原因。project `zozsikyinpasapuxjbtg` を復元し、`ACTIVE_HEALTHY` とSupabase読み取り成功を確認した。
- **自動停止の軽減**: `.github/workflows/health.yml` の定期実行を3日に1回から8時間ごと（1日3回）へ変更。読み取りはFree Planの自動停止を避けるためのbest-effortであり、停止回避を保証せず、接続失敗も抑制しない。
- **運用文書**: `DEVELOPMENT.md` と `OPERATOR_ACTIONS.md` にJSTの実行時刻、保証範囲、失敗時の扱いを反映した。既存の `workflow_dispatch`、repository secrets名、読み取り専用チェックは維持した。
- **検証**: ローカルの `scripts/health_check.py` と `scripts/live_smoke.py` が成功。`scripts/check.py` は依存整合性、compileall、Ruff、pytest 76件がすべて成功。GitHub Actionsの手動run `31926236265` でもSupabase DNS・読み取り・GitHub CLI/API確認がすべて成功した。

### Supabase CLI基準化とFreeプラン用バックアップ（2026-08-01）
- **実行環境**: BIOSのSVM有効化後、Windows側で `VirtualizationFirmwareEnabled=True` を確認。WSL 2.7.11.0とDocker Desktop 4.84.0（Engine 29.6.2）を導入し、Supabase CLIが必要とするDocker実行環境を復旧した。
- **CLI基準化**: Supabase CLI 2.111.0でproject `zozsikyinpasapuxjbtg` をlinkし、`migration fetch` 後にローカル・リモート8件のmigration versionが完全一致することを `migration list --linked` で再確認した。通常のmigration式 `db pull` は履歴開始前に作られた基礎テーブルをshadow DBで再現できず安全に停止したため、remote migration履歴を変更せず `db pull --declarative` を使用し、現行public schemaを `supabase/database/` へ取得した。
- **バックアップ**: 対象organizationはFreeプランのためプラットフォーム管理の日次バックアップ一覧は提供対象外。公式CLI `db dump` で `.states/supabase_schema_20260801.sql`（29,056 bytes、SHA-256 `27935aa3812fd3235ca7792aad0fae10058acd4dd892c19563d5fd0e88660f6b`）、`.states/supabase_data_20260801.sql`（355,098 bytes、SHA-256 `a9bd382dd28c68ce5ddba8f3c41be9f4216dabf62128fe32dadcebc72a63e75f`）、`.states/supabase_roles_20260801.sql`（358 bytes、SHA-256 `4350a72b5ec109888e740c17f3eb4da2fcd95ab73af26499538ed0bf615db543`）を作成した。3ファイルはいずれも `.gitignore` の `.states/` 対象で、データダンプは機密情報を含み得るためローカル保管とする。
- **検証**: `db pull --declarative` の再実行は警告なしで成功し、`db lint --linked --schema public --level warning` は `No schema errors found`。`scripts/check.py` は依存整合性、compileall、Ruff、pytest 76件がすべて成功し、`git diff --check` も成功した。

### 全コードレビュー是正とトランザクション境界の導入（2026-08-01）
- **ユーザー分離**: ログアウトと別ユーザーへの切替前にユーザー依存のStreamlit状態を全消去し、原文取得を必ず所有者付きにした。ユーザー名の空白除去、長さ、予約名もDBアクセス前に検証する。
- **カード入力**: `CardDraft` / `SourceBundleCommand`、厳密な `【】` パーサー、決定的な5穴分割、カードごとの正しい `blank_count` を導入。穴埋め型をまたぐ直接変更は再生成プレビュー必須にした。
- **DB原子性**: `supabase/migrations/` を開始し、日次割当同期、復習完了、原文束の保存・削除、バックアップインポートを `SECURITY INVOKER` RPCでトランザクション化した。実行権限は `service_role` のみに限定し、所有者・属性・範囲制約と複合外部キー用インデックスを追加した。
- **インポートとエラー**: JSON v1/v2、参照、必須値、ファイル内重複、`reset_progress` を事前確認する `ImportPreview` を追加。0件更新/削除とmigration欠落を区別し、画面には安全な文言と参照番号だけを表示する。
- **移行前確認**: Supabaseを `ACTIVE_HEALTHY` へ復旧し、重複ユーザー名・異ユーザー参照・属性/進捗異常が0件であることを確認。既存の知識/類型カード4件に解答値が残る旧仕様データは自動修正せず保持した。秘密情報とセッションを除く論理バックアップを `.states/pre_migration_backup_20260801T021220Z.json` に作成（SHA-256 `8cc3d295ab21fcb917358ffba5a0a45ece31079912d642c4cb697c58e3fc3a03`）。
- **検証**: `scripts/check.py` は依存整合性、compileall、Ruff、pytest 76件が警告なしで成功。読み取り専用health check、`codex-maintenance` のlive smoke（失敗インポートの全件ロールバック・割当同期・2スレッド同時復習の原子性/冪等性・削除・残骸0件）、実ブラウザのログイン/本日のノルマ/カード管理/カード追加/ログアウトを確認した。

### Codexリポジトリ指示の追加（2026-07-28）
- `AGENTS.md` を新設し、Streamlit/Python 3.12、Supabase秘密情報、読み取り専用ヘルスチェック、`codex-maintenance`、`daily_assignments`互換性、標準release gateだけをrepo固有ルールとして記録した。
- グローバルな作業手順やWindows実行環境の詳細は重複させず、Codex global guidanceと専用Skillsへ委ねた。
- 検証: Markdown差分の`git diff --check`に合格。実効指示の確認はCodex再起動後の新しいタスクで行う。

### GitHub/Supabase運用ヘルスチェック追加（2026-07-04）
- **GitHub Actions対策**: `Health Check` workflowを追加し、3日に1回と手動実行でGitHub CLI/APIとSupabase接続を読み取り専用で確認するようにした。`SUPABASE_URL` / `SUPABASE_KEY` はGitHub repository secretsから渡し、push/PRでは実行しない。
- **Supabase停止対策**: `scripts/health_check.py` を追加し、secrets未設定、Supabase DNS失敗、Supabase読み取り失敗、GitHub CLI未導入/未認証/API失敗を分類して表示するようにした。secret値は出力しない。
- **CI更新**: 既存CIの `actions/checkout` をv7、`actions/setup-python` をv6へ更新し、`compileall` 対象に `scripts` を追加した。`scripts/check.py` も同じく `scripts` を構文検証対象にした。
- **運用文書**: `DEVELOPMENT.md` と `OPERATOR_ACTIONS.md` に、GitHub secrets設定、手動ヘルスチェック、失敗時の見方、Supabase Free Plan停止時の復元後確認を追記した。
- **検証**: `pytest tests\test_health_check.py -q` は7件成功。`scripts/check.py` は依存整合性、compileall、Ruff format/lint、pytest（54件）すべて成功。`scripts/health_check.py` はローカルsecretsでSupabase DNS/読み取りとGitHub CLI/API確認に成功。`gh workflow run health.yml` はworkflow未pushのため未実行。

### カード管理ランク統合と整備用ユーザー整理（2026-07-01）
- **ランク統合**: カード管理画面で、原文カード配下の暗記カードごとの個別ランク選択をやめ、原文カードと紐づく暗記カードを1つの「重要度ランク」で扱うようにした。既存データでランクが混在する場合は最高ランクを代表値として表示し、保存時に全紐づきカードへ同期する。
- **再生成改善**: 原文を変更していない場合は「変更した原文からカードを再生成」を表示しないようにした。再生成カードは変更前グループのランクを引き継ぎ、保存ボタンは変更なしなら secondary 表示かつ非活性にした。
- **整備用ユーザー**: ライブDB上の空ユーザー `test_user_2cdaa6d9` を `codex-maintenance` に改名し、空の `testuser` とそのセッションを削除した。`Andy Jones` はテストユーザーと断定しないため残した。今後の `scripts/live_smoke.py` は `codex-maintenance` を固定で使い、ログイン画面には表示しない。
- **検証**: `pytest tests\test_auth.py tests\test_manage_page_sorting.py tests\test_card_workflows.py -q` は18件成功。`scripts/check.py` は依存整合性、compileall、Ruff format/lint、pytest（47件）すべて成功。`scripts/live_smoke.py` で `codex-maintenance` を使ったログイン、セッション、カード、原文、復習進捗、日次割当、削除を確認。Streamlitを一時起動し、`http://localhost:8502` のHTTP 200も確認。

### Supabase停止復旧とDNSエラー表示改善（2026-06-25）
- **障害原因**: FreeプランのSupabaseプロジェクトが `INACTIVE` になり、プロジェクト固有ホストをDNS解決できなくなっていた。プロジェクトを復元し、`ACTIVE_HEALTHY` とDNS応答を確認。
- **エラー表示**: DBクエリ時の例外チェーンから `socket.gaierror` を検出し、「Supabaseプロジェクトが停止している可能性があります」と案内する接続エラーへ変換。無関係な例外は従来の汎用表示を維持。
- **検証**: `scripts/check.py` の依存整合性、compileall、Ruff format/lint、pytest（41件）は全成功。`scripts/live_smoke.py` でログイン、セッション、カード、原文、復習進捗、日次割当、削除を確認し、StreamlitのローカルHTTP 200も確認。

### 開発環境・検証基盤のPython 3.12統一（2026-06-24）
- **依存再現性**: 検証済み直接依存を `constraints.txt` に固定し、ローカル・CI・devcontainerのインストールを同じ制約付きコマンドへ統一。
- **実行環境**: 文書とdevcontainerをPython 3.12へ揃え、参照されていないgit管理外の旧 `venv/`（Python 3.13.9）を削除して `.venv`（Python 3.12.10）へ一本化。
- **Windows/Codex安定性**: pytestとRuffのtemp/cacheを `.states/` 配下へ固定し、検証スクリプトへ依存整合性確認とcompileallを追加。
- **基準線**: 既存format checkで不合格だった4ファイルをRuffで機械整形し、挙動変更なしでCI基準線を正常化。
- **検証**: 現行 `.venv` とconstraintsから新規作成した使い捨てPython 3.12環境の両方で、pip check、compileall、Ruff format/lint、pytest（38件）に成功。Streamlit headless起動もHTTP 200を確認。

### カード管理画面の並び順改善（2026-06-18）
- **UI**: カード管理画面の検索/タイプ絞り込み行に「並び順」を追加し、初期値を「50音順」にした。選択肢は「50音順」「お気に入り優先」「重要度順」「復習日が近い順」。
- **仕様**: DB変更なしで、タイトル優先・未設定時は原文/問題文を使う表示名キーを NFKC 正規化、カタカナ→ひらがな化、空白整理して並べる。漢字タイトルは読み仮名ではなく表示文字順。
- **整理**: 原文カードと原文なし暗記カードの両方に同じ並び順を適用し、タイプ絞り込みも孤立カードへ適用。紐づきカードは `source_id` ごとの辞書で共有するようにした。
- **検証**: `ruff format --check pages\manage_page.py tests\test_manage_page_sorting.py`, `ruff check pages\manage_page.py tests\test_manage_page_sorting.py`, `pytest tests\test_manage_page_sorting.py -q`, `pytest tests -p no:cacheprovider -q` は成功。

### カード管理画面の共通タイトル編集対応（2026-05-30）
- **UI**: カード管理画面の原文カード編集に「タイトル」欄を追加。保存時は原文カードと紐づく暗記カードへ同じ共通タイトルを反映し、再生成上書きでも編集後タイトルを使う。
- **孤立カード**: 原文なし暗記カードでもタイトルを編集でき、タイトル検索にも対応。
- **検証**: `ruff format --check pages\manage_page.py`, `ruff check pages\manage_page.py`, `pytest tests -p no:cacheprovider -q` は成功。`scripts/check.py` は lint/test は成功したが、未編集の `pages\add_card_page.py`, `pages\review_page.py`, `services\card_service.py`, `tests\test_logic.py` の既存format差分で format check のみ失敗。

### 知識・類型カードの【】ハイライト指定化（2026-05-30）
- **仕様変更**: 知識・類型カードのハイライト指定を、別入力の「ハイライト語」から本文内の `【】` 指定へ変更。復習・プレビュー表示では `【】` を出さず、囲まれた箇所だけを赤下線で表示する。
- **互換性**: DBスキーマは変更せず、`highlighted_keywords` は新規カードでは `【】` から抽出して保存。本文に `【】` がない旧方式カードは既存の `highlighted_keywords` フォールバックで表示を維持する。
- **UI**: カード追加画面とカード管理画面の知識・類型フローから「ハイライト語」欄を外し、本文欄で `【】` を直接編集する方式に統一。孤立カード編集も同じ保存ルールに合わせた。
- **検証**: `ruff check services\card_service.py pages\add_card_page.py pages\manage_page.py pages\review_page.py tests\test_logic.py`, `pytest tests\test_logic.py -q`, `pytest tests -q` は成功。`streamlit run app.py --server.port 8501 --server.headless true` を起動し、`curl -I http://localhost:8501` でHTTP 200を確認。

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
