# Progress — AI暗記カードアプリ

## 最終更新: 2026-04-19

## 完了済み

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
