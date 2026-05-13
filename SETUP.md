# セットアップ手順

## 1. GCPでGmail APIを有効化

1. https://console.cloud.google.com にアクセス
2. 新プロジェクト作成（例: mail-processor）
3. 「APIとサービス」→「ライブラリ」→ **Gmail API** を有効化
4. 「認証情報」→「認証情報を作成」→「OAuth 2.0 クライアントID」
   - アプリの種類: **Webアプリケーション**
   - 承認済みリダイレクトURI: `http://localhost:5000/oauth/callback`
5. 取得した **クライアントID** と **クライアントシークレット** をメモ

## 2. Anthropic API キー取得

1. https://console.anthropic.com にアクセス
2. 「API Keys」→「Create Key」
3. キーをメモ

## 3. LINE Messaging API 設定

1. https://developers.line.biz にアクセス
2. プロバイダー作成 → チャネル作成（Messaging API）
3. 「チャネルシークレット」をメモ（セキュリティ > チャネルシークレット）
4. 「チャネルアクセストークン（長期）」を発行 → メモ
5. 自分のLINE User IDを確認（LINE Official Account Managerで確認可）

## 4. 環境変数ファイル作成

```bash
cp .env.example .env
# .env を編集して各キーを入力
```

## 5. 依存パッケージインストール

```bash
pip install -r requirements.txt
```

## 6. 起動

```bash
python app.py
```

ブラウザで http://localhost:5000 を開き、「Gmail と連携する」をクリック。
OAuth認証後、自動でポーリングが開始されます。

## 動作確認

- http://localhost:5000/process → 今すぐ仕分け実行
- http://localhost:5000/audit  → 監査バッチ手動実行
- http://localhost:5000/status → 設定確認

## ラベル構成（Gmail上に自動作成）

| ラベル | 意味 |
|--------|------|
| 📛重要・緊急 | 即日対応必要 → LINEに通知 |
| 📩返信必要 | 返信要・緊急でない |
| 📋確認のみ | 返信不要・既読化 |
| 📄請求書・契約 | 金銭関係 → LINEに通知 |
| 🗑営業・スパム | 不要メール・既読化 |
| ✅AI処理済み | 全処理済みメールに付与 |
