# 🧠 AI 暗記カードアプリ

Google Gemini AIを使用してテキストから暗記カードを自動生成し、忘却曲線に基づいた復習スケジュールを管理できる学習支援Webアプリです。

## ✨ 特徴

- 🤖 **AI自動生成**: テキストを貼り付けるだけで、AIが自動的に暗記カードを作成
- 📅 **スマート復習**: 忘却曲線に基づいた最適な復習スケジュール
- 📱 **マルチデバイス対応**: スマホ・タブレット・PCからアクセス可能
- 🏷️ **カテゴリ管理**: 法律科目ごとにカードを分類・整理
- 💾 **自動保存**: データは自動的に保存され、いつでも続きから学習可能

## 🚀 使い方

### 1. アプリにアクセス
ブラウザでアプリのURLを開くだけ！インストール不要です。

### 2. APIキーの設定
初回のみ、Google Gemini APIキーをサイドバーに入力してください。

> 💡 **APIキーの取得方法**: [Google AI Studio](https://makersuite.google.com/app/apikey) から無料で取得できます

### 3. カードを作成
1. 「カードを追加」メニューを選択
2. カテゴリを選択（民法、商法、刑法など）
3. 学習したいテキストを貼り付け
4. 「✨ 生成する」ボタンをクリック
5. AIが自動的に問題と答えのペアを生成

### 4. 復習する
1. 「復習する」メニューを選択
2. その日に復習すべきカードが表示されます
3. 答えを確認して、記憶の定着度を選択
4. 次回の復習日が自動的に調整されます

### 5. カードを管理
「カード管理」メニューで、作成したカードを編集・削除できます。

## 🛠️ 技術スタック

- **フロントエンド**: Streamlit
- **AI**: Google Gemini 2.5 Flash API
- **データ保存**: JSON形式
- **ホスティング**: Streamlit Cloud

## 📂 プロジェクト構成

```
.
├── app.py              # メインアプリケーション
├── gemini_client.py    # Gemini API連携
├── storage.py          # データ保存・読み込み
├── utils.py            # 忘却曲線ロジック
└── requirements.txt    # 依存パッケージ
```

## 🔧 ローカル開発

このリポジトリをクローンしてローカルで実行することもできます：

```bash
# リポジトリをクローン
git clone https://github.com/あなたのユーザー名/memorization-app.git
cd memorization-app

# 依存パッケージをインストール
pip install -r requirements.txt

# 環境変数を設定
export GEMINI_API_KEY="your-api-key-here"

# アプリを起動
streamlit run app.py
```

## 📝 ライセンス

このプロジェクトは個人的な学習支援ツールとして開発されました。

## 🙏 謝辞

- [Google Gemini API](https://ai.google.dev/) - AI機能
- [Streamlit](https://streamlit.io/) - Webアプリフレームワーク

