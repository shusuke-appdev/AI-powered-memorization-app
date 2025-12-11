# 🧠 AI 暗記カード

AIを活用した穴埋め式フラッシュカードアプリ。Geminiが自動でテキストから暗記カードを生成し、SM-2アルゴリズムで効率的な復習スケジュールを管理します。

## ✨ 機能

### 📝 カード生成
- テキストを貼り付けるだけでAIが自動で穴埋め問題を生成
- 原文を維持したまま、重要語句のみを空欄化
- キーワード指定で特定の用語をターゲットにした問題作成

### 📚 復習システム
- **SM-2アルゴリズム**による科学的な復習スケジュール
- 4段階評価（忘れた/難しい/普通/簡単）で次回復習日を自動計算
- 今日の復習カードを優先表示

### 👥 マルチユーザー対応
- ユーザー登録・ログイン機能
- 各ユーザーの独立したカードデータベース
- 自動ログイン（30日間セッション保持）
- ユーザー別APIキー管理

### ☁️ クラウドデータ永続化
- **Supabase**（PostgreSQL）によるデータ保存
- アプリ再起動後もデータが維持
- 複数デバイスからアクセス可能

---

## 🚀 デプロイ済みアプリ

[アプリを開く](https://your-app-name.streamlit.app)

---

## 🛠️ ローカル開発

### 必要条件
- Python 3.9+
- Gemini API キー
- Supabase プロジェクト

### セットアップ

1. **リポジトリをクローン**
```bash
git clone https://github.com/your-username/memorization_app.git
cd memorization_app
```

2. **依存関係をインストール**
```bash
pip install -r requirements.txt
```

3. **環境変数を設定**
```bash
# PowerShell
$env:SUPABASE_URL = "https://xxx.supabase.co"
$env:SUPABASE_KEY = "eyJ..."
```

4. **アプリを起動**
```bash
streamlit run app.py
```

---

## ☁️ Streamlit Cloud へのデプロイ

### 1. GitHubにプッシュ
```bash
git add .
git commit -m "Deploy app"
git push
```

### 2. Streamlit Cloud で設定

1. [share.streamlit.io](https://share.streamlit.io) にログイン
2. 「New app」→ リポジトリを選択
3. **Settings** → **Secrets** に以下を追加:

```toml
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."
```

---

## 📁 ファイル構成

```
memorization_app/
├── app.py              # メインアプリケーション
├── auth.py             # ユーザー認証・セッション管理
├── storage.py          # カードデータ管理
├── database.py         # Supabase接続
├── gemini_client.py    # Gemini API連携
├── utils.py            # SM-2アルゴリズム
├── requirements.txt    # 依存関係
└── .gitignore
```

---

## 🗄️ データベース構造（Supabase）

### users テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | ユーザーID |
| username | TEXT | ユーザー名 |
| password_hash | TEXT | パスワード（ハッシュ） |
| api_key | TEXT | Gemini APIキー |
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

### sessions テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| token | UUID | セッショントークン |
| user_id | UUID | ユーザーID |
| expires_at | TIMESTAMP | 有効期限 |

---

## 📜 ライセンス

MIT License

---

## 🙏 謝辞

- [Streamlit](https://streamlit.io/) - Webアプリフレームワーク
- [Google Gemini](https://ai.google.dev/) - AI生成
- [Supabase](https://supabase.com/) - データベース
- SM-2 Algorithm - 復習スケジュール
