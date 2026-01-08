# AI 暗記カード

AIを活用した穴埋め式フラッシュカードアプリ。Gemini APIでカードを自動生成し、SM-2アルゴリズムで効率的な復習スケジュールを管理します。

## 機能

### 基本機能
- **AI穴埋め生成** - テキストを貼り付けるだけでAIが自動で穴埋め問題を生成
- **SM-2復習システム** - 科学的な復習スケジュールで効率的に暗記
- **本日のノルマ機能** - 1日の復習上限を設定（デフォルト15枚）
- **ハイブリッド最適化** - 苦手カードと期限カードをバランスよく出題
- **原文カード保存** - 穴埋めカードの元テキストを別途保存・レビュー可能
- **マルチユーザー対応** - ユーザー登録・ログイン、自動ログイン（30日間）
- **クラウド保存** - Supabase（PostgreSQL）によるデータ永続化

### 新機能（v2.0）
- **📊 統計ダッシュボード** - 学習進捗の可視化（習得率、カテゴリ別統計）
- **📦 エクスポート/インポート** - JSON/CSV形式でデータバックアップ・移行
- **⭐ お気に入り機能** - 重要なカードにスターを付けて管理
- **🔊 音声読み上げ** - カードと原文を音声で確認（Web Speech API）
- **🌙 ダークモード** - 目に優しいダークテーマ
- **📱 モバイル対応強化** - スマホでも快適に操作

---

## ローカル開発

### 必要条件
- Python 3.9+
- Gemini API キー
- Supabase プロジェクト

### セットアップ

```bash
# 依存関係をインストール
pip install -r requirements.txt

# 環境変数を設定（PowerShell）
$env:SUPABASE_URL = "https://xxx.supabase.co"
$env:SUPABASE_KEY = "eyJ..."

# アプリを起動
streamlit run app.py
```

---

## Streamlit Cloud へのデプロイ

1. GitHubにプッシュ
2. [share.streamlit.io](https://share.streamlit.io) でリポジトリを選択
3. **Settings** → **Secrets** に以下を追加:

```toml
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."
```

---

## ファイル構成

```
memorization_app/
├── app.py              # メインアプリケーション
├── auth.py             # ユーザー認証・セッション管理（bcrypt対応）
├── storage.py          # カード・原文カードデータ管理
├── database.py         # Supabase接続（リトライ機能付き）
├── gemini_client.py    # Gemini API連携
├── utils.py            # SM-2アルゴリズム・ハイブリッド最適化
├── stats.py            # 学習統計計算・表示
├── export_import.py    # エクスポート/インポート機能
├── requirements.txt    # 依存関係
├── USER_GUIDE.md       # ユーザーガイド
├── HELP_AI_CONTEXT.md  # ヘルプAI用コンテキスト
└── .gitignore
```

---

## データベース構造（Supabase）

### users テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | ユーザーID |
| username | TEXT | ユーザー名 |
| password_hash | TEXT | パスワード（bcryptハッシュ） |
| api_key | TEXT | Gemini APIキー |
| daily_quota_limit | INT | 1日のノルマ上限 |
| created_at | TIMESTAMP | 登録日時 |

### cards テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | カードID |
| user_id | UUID | 所有者のユーザーID |
| question | TEXT | 問題文（穴埋め） |
| answer | TEXT | 答え |
| title | TEXT | カードのタイトル |
| category | TEXT | カテゴリ |
| ease_factor | FLOAT | 難易度係数 |
| interval | INT | 復習間隔（日） |
| repetitions | INT | 連続正解回数 |
| next_review | DATE | 次回復習日 |
| source_id | UUID | 原文カードへの参照 |
| blank_count | INT | 穴埋め箇所数 |
| **is_favorite** | BOOL | お気に入りフラグ（新規） |

### source_cards テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | 原文カードID |
| user_id | UUID | 所有者のユーザーID |
| source_text | TEXT | 原文テキスト |
| title | TEXT | タイトル |
| category | TEXT | カテゴリ |
| created_at | TIMESTAMP | 作成日時 |

### sessions テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| token | UUID | セッショントークン |
| user_id | UUID | ユーザーID |
| expires_at | TIMESTAMP | 有効期限 |

---

## ライセンス

MIT License

---

## 謝辞

- [Streamlit](https://streamlit.io/) - Webアプリフレームワーク
- [Google Gemini](https://ai.google.dev/) - AI生成
- [Supabase](https://supabase.com/) - データベース
- SM-2 Algorithm - 復習スケジュール
