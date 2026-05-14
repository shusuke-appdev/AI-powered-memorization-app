# コード総点検

調査日: 2026-05-14
対象: `app.py`, `auth.py`, `database.py`, `storage.py`, `services/*`, `pages/*`, `stats.py`, `export_import.py`, `components.py`, `styles/*`, `tests/*`, 既存ドキュメント

## 総評

アプリは Streamlit の単一アプリとして、ページ分割とサービス分割が進んでいます。ユーザー方針としてパスワード認証とGemini API利用は廃止し、ログイン画面でユーザーを選択する方式に統一しました。残る主要リスクは、DBアクセス境界、HTML描画、スキーマ管理、インポート復元、検証環境です。

## 重大度高

### 1. ユーザー選択ログインは厳密な個人認証ではない

該当: `pages/login_page.py`, `auth.py`

ログイン画面で登録済みユーザーを選ぶと、そのユーザーとしてログインします。これは今回の運用方針として採用した仕様です。

影響:

- 共有URLや公開デプロイでは、利用者が別ユーザーを選択できる。
- 厳密な本人確認や個人情報保護が必要な運用には向かない。

対応方針:

- このアプリは、信頼できる利用者だけがアクセスする環境で使う。
- ログイン画面に不要なユーザーが出ないよう、Supabaseの `users` を整理する。
- 将来、厳密な本人確認が必要になった場合だけ Supabase Auth などへ移行する。

### 2. RLS全拒否と強いSupabaseキー前提の設計

該当: `migration_rls.sql`, `database.py`, `auth.py`, `storage.py`

RLSは全拒否ポリシーで、コメント上はService Role Keyでバイパスする前提です。アプリコードは全テーブルに直接アクセスします。

影響:

- キー漏洩時の被害範囲が全データになる。
- DB側で「このユーザーは自分のカードだけ読める」という制御を使っていない。

根本対応:

- 現在の運用方針では、Supabaseキーを厳密に秘匿する。
- 将来、ブラウザや外部クライアントからSupabaseへ直接アクセスする構成にする場合は、所有者ベースのRLSを設計する。
- Service Role相当キーはサーバー側だけで扱う。

### 3. 未エスケープHTML描画にユーザー入力が混ざる

該当: `pages/review_page.py`, `pages/add_card_page.py`, `components.py`

`unsafe_allow_html=True` でHTMLを描画しています。カード表示とヘルプチャット周辺は安全化しましたが、追加画面のプレビューなど棚卸しが残っています。

実施済み:

- `services/html_rendering.py` にHTMLエスケープ関数を追加。
- 復習画面のタイトル、カテゴリ、問題、答え、原文をエスケープ。
- ハイライト処理をエスケープ済みHTML生成へ変更。
- 聞き流しコンポーネントのJSON埋め込みで `</` をエスケープ。

残る対応:

- `pages/add_card_page.py` のプレビューHTMLを同じ方針で安全化する。
- `unsafe_allow_html=True` の利用箇所を定期的に棚卸しする。

## 重大度中

### 4. インポートの「上書き」は未実装

該当: `export_import.py`, `pages/stats_page.py`

以前は「上書き」と表示しつつ、実態は重複追加でした。現在はUI文言を「重複として追加」に変更済みです。

残る対応:

- 本当に既存カードを更新する `update_existing` を実装するか、今後も未対応と明記する。
- インポート前にdry-run結果を表示する。

### 5. 原文カードと暗記カードの整合性がDB制約で守られていない

該当: `storage.py`, `migration_*.sql`

アプリ側は `source_id` で紐づけますが、初期スキーマや外部キー制約が資料化されていません。

根本対応:

- `cards.source_id -> source_cards.id` の外部キーを定義する。
- `user_id` の整合性を制約またはトリガーで守る。
- 原文削除時の方針を `CASCADE` か明示的削除に統一する。

### 6. `dict[str, Any]` 中心でドメイン不変条件が散らばっている

該当: `storage.py`, `services/review_service.py`, `pages/*`

カード種別、ランク、復習状態、日付文字列、ハイライト語などが辞書で受け渡されています。

根本対応:

- `dataclass` または Pydantic で `Card`, `SourceCard`, `ReviewStats` を定義する。
- DB行からドメイン型への変換をRepositoryに集約する。
- UI用ViewModelを別に作る。

### 7. 日次ノルマ選択に乱数とセッション状態が絡み、再現性が低い

該当: `services/card_service.generate_cards_from_selection()`, `pages/review_page.py`, `services/review_service.py`

6箇所以上の穴埋め生成で `random.shuffle()` を使います。日次ノルマは `session_state` に選出IDを保持します。

根本対応:

- カード生成は入力順ベースの決定的アルゴリズムにする、またはseedを注入する。
- 日次ノルマはDBに `daily_assignments` として保存する。

## 重大度低

### 8. 検証環境が壊れている

該当: `venv`, PATH

`ruff`, `pytest` はPATH上になく、`venv\Scripts\python.exe` も起動できませんでした。

根本対応:

- `.venv` を作り直す。
- CIで `ruff check .` と `pytest tests` を必須化する。

## 良い点

- `app.py` は薄い入口になっており、画面ごとの分割はできている。
- SM-2やカード生成の純粋ロジックにテストがある。
- DB読み込みに短いTTLキャッシュがあり、Streamlitの再実行コストを抑えている。
- カテゴリ、タイプ、ランクなどの定数が `config.py` に集約されている。

## 監査で確認した実行不可事項

- `ruff check .`: `ruff` がPATHにない。
- `pytest`: `pytest` がPATHにない。
- `venv\Scripts\python.exe -m pytest tests`: 同梱Pythonが起動不可。
