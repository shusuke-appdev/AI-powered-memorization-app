# AI 暗記カード

法律学習向けの穴埋め式フラッシュカードアプリです。Streamlit で画面を構成し、Supabase PostgreSQL にユーザー、原文カード、暗記カード、セッションを保存します。カード生成は、ユーザーが `【】` で穴埋め箇所を指定する手動フローです。Gemini API とアプリ内AI機能は使用しません。

## 主な機能

- ログイン画面で登録済みユーザーを選択するログイン
- `【】` マーカーによる穴埋めカード生成
- 規範、判例、類型、知識のカードタイプ管理
- 民法、商法、刑法、憲法、行政法、民事訴訟法、刑事訴訟法、その他のカテゴリ管理
- A+ から C までの重要度ランク
- SM-2 ベースの復習間隔計算
- 日次ノルマ、科目ラウンドロビン、重要度、苦手度、期限を考慮した出題選択
- 日次ノルマ割当のDB保存（`daily_assignments` 適用後）
- 原文カードと暗記カードの紐づけ管理
- 原文単位のお気に入り
- カード編集、削除、原文からの再生成
- 統計表示とJSON/CSVエクスポート/インポート
- Web Speech API を使った原文聞き流し
- ダークモードとモバイル向けCSS

## 技術スタック

- Python 3.12
- Streamlit
- Supabase Python client
- PostgreSQL on Supabase
- Plotly / pandas
- pytest / ruff

## セットアップ

```powershell
python -m pip install -r requirements.txt -c constraints.txt

$env:SUPABASE_URL = "https://xxx.supabase.co"
$env:SUPABASE_KEY = "eyJ..."

streamlit run app.py
```

Streamlit Cloud では `Settings` から次のSecretsを設定します。

```toml
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."
```

## 主要ファイル

```text
app.py                     Streamlitアプリの入口、認証判定、タブ構成
auth.py                    ユーザー、ノルマ、セッション管理
database.py                Supabase接続と接続エラー処理
storage.py                 単一行CRUDとトランザクションRPC呼び出し
components.py              聞き流し用HTML/JavaScriptコンポーネント
config.py                  カテゴリ、カードタイプ、ランク、アルゴリズム定数
export_import.py           JSON/CSVの変換ロジック
stats.py                   学習統計の計算
pages/                     Streamlit画面
use_cases/                 複数DB書き込みをまとめるユースケース
services/review_service.py SM-2と日次出題選択
services/card_service.py   穴埋めカード生成とハイライト
services/time_service.py   日本時間基準の日付ヘルパー
styles/                    CSS
tests/                     ロジックテスト
.github/workflows/ci.yml   ruff / pytest のCI
scripts/live_smoke.py      Supabase接続のサービス層スモークテスト
scripts/backup_user_data.py 秘密情報を除いた移行前論理バックアップ
supabase/migrations/       Supabase CLI管理の差分マイグレーション
migration_*.sql            CLI移行前から存在する旧差分SQL（再適用しない）
```

## データモデル概要

### users

| カラム | 用途 |
| --- | --- |
| id | ユーザーID |
| username | 表示名、ログイン選択名 |
| password_hash | 既存DBスキーマ互換用。アプリでは使用しない |
| api_key | 既存DBスキーマ互換用。アプリでは使用しない |
| daily_quota | 1日の復習上限 |
| created_at | 作成日時 |

### sessions

| カラム | 用途 |
| --- | --- |
| token | Cookieに保存するセッショントークン |
| user_id | ユーザーID |
| expires_at | 有効期限 |

### source_cards

| カラム | 用途 |
| --- | --- |
| id | 原文カードID |
| user_id | 所有者 |
| source_text | 元テキスト |
| title | タイトル |
| category | 科目 |
| card_type | 規範、判例、類型、知識 |
| created_at | 作成日時 |

### cards

| カラム | 用途 |
| --- | --- |
| id | 暗記カードID |
| user_id | 所有者 |
| source_id | 原文カードID |
| question | 問題文 |
| answer | 答え |
| title | タイトル |
| category | 科目 |
| card_type | 規範、判例、類型、知識 |
| rank | 重要度 |
| highlighted_keywords | 知識、類型カードのハイライト語 |
| ease_factor | SM-2難易度係数 |
| interval | 復習間隔 |
| repetitions | 連続正解回数 |
| next_review | 次回復習日 |
| blank_count | 穴埋め量の目安 |
| is_favorite | お気に入り |

### daily_assignments

| カラム | 用途 |
| --- | --- |
| id | 割当ID |
| user_id | 所有者 |
| assignment_date | ノルマ対象日 |
| card_id | 割当カード |
| source_id | 原文確認用の原文カードID |
| position | 当日の出題順 |
| completed_at | 完了時刻 |
| quality | 自己評価 |

## 検証

通常は次を使います。

```powershell
ruff format --check .
ruff check .
pytest tests -p no:cacheprovider -q
```

環境構築と既知の検証課題は `DEVELOPMENT.md` と `CODE_AUDIT.md` を参照してください。

## 関連資料

- `USER_GUIDE.md`: 利用者向け操作ガイド
- `ARCHITECTURE.md`: 構造、責務、データフロー
- `DEVELOPMENT.md`: 開発、設定、検証、運用メモ
- `CODE_AUDIT.md`: 総点検結果
- `IMPROVEMENT_PLAN.md`: 根本改修計画
- `OPERATOR_ACTIONS.md`: 運用者が実施する設定・確認作業
- `task.md`: 実行タスク一覧
