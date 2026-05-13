import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/oauth/callback")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = (os.getenv("LINE_USER_ID") or "").strip()

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

TARGET_EMAIL = os.getenv("TARGET_EMAIL")
try:
    POLLING_INTERVAL = max(10, int(os.getenv("POLLING_INTERVAL", "60")))
except ValueError:
    POLLING_INTERVAL = 60

# Geminiモデル（無料枠）
GEMINI_MODEL = "models/gemini-2.5-flash-lite"

# Gmailラベル定義
LABELS = {
    "urgent":    "📛重要・緊急",
    "reply":     "📩返信必要",
    "fyi":       "📋確認のみ",
    "contract":  "📄請求書・契約",
    "sales":     "🗑営業・スパム",
    "processed": "✅AI処理済み",
}

# 監査バッチ対象日数
AUDIT_DAYS = 30
