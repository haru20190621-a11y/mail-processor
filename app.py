import sys
import secrets
import logging
import threading
from functools import wraps

from flask import Flask, redirect, request, jsonify, url_for, abort, session

import config
from gmail.auth import get_auth_url, exchange_code, load_credentials
from gmail.client import ensure_labels_exist
from tasks.processor import process_new_emails, run_audit
from ai.mail_assistant import answer_question
from line.notifier import reply_message, push_message
from tasks.scheduler import start as start_scheduler, stop as stop_scheduler

# ── UTF-8出力の強制（Windows cp932対策）────────────────────
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── ロギング設定 ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── 起動時バリデーション ──────────────────────────────────
def _validate_config():
    errors = []
    if not config.GOOGLE_CLIENT_ID:
        errors.append("GOOGLE_CLIENT_ID が未設定")
    if not config.GOOGLE_CLIENT_SECRET:
        errors.append("GOOGLE_CLIENT_SECRET が未設定")
    if not config.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY が未設定")
    if config.POLLING_INTERVAL <= 0:
        errors.append("POLLING_INTERVAL は1以上の整数にしてください")
    if config.FLASK_SECRET_KEY == "dev-secret-change-me":
        logger.warning("警告: FLASK_SECRET_KEY がデフォルト値のままです。.envで変更してください。")
    if errors:
        for e in errors:
            logger.error(f"設定エラー: {e}")
        sys.exit(1)

_validate_config()

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY


# ── セキュリティ：ローカルホスト限定ガード ────────────────
def localhost_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@app.route("/")
@localhost_only
def index():
    creds = load_credentials()
    if not creds:
        return (
            "<h2>Gmail メール処理ツール</h2>"
            "<p>まず Gmail 認証が必要です。</p>"
            '<a href="/auth">Gmail と連携する</a>'
        )
    return (
        "<h2>Gmail メール処理ツール ✅</h2>"
        "<ul>"
        "<li><a href='/process'>今すぐ仕分け実行</a></li>"
        "<li><a href='/audit'>監査バッチ実行</a></li>"
        "<li><a href='/status'>ステータス確認</a></li>"
        "</ul>"
    )


# ── 認証フロー（CSRF対策: stateパラメータ付き）────────────
@app.route("/auth")
@localhost_only
def auth():
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    return redirect(get_auth_url(state=state))


@app.route("/oauth/callback")
@localhost_only
def oauth_callback():
    # Googleからのエラーチェック
    error = request.args.get("error")
    if error:
        logger.error(f"OAuth エラー: {error}")
        return f"認証エラー: {error}", 400

    # CSRF対策: stateパラメータ検証
    returned_state = request.args.get("state")
    expected_state = session.pop("oauth_state", None)
    if not expected_state or returned_state != expected_state:
        logger.warning("OAuth stateパラメータ不一致 - CSRF攻撃の可能性")
        abort(403)

    code = request.args.get("code")
    if not code:
        return "認証コードが取得できませんでした", 400

    exchange_code(code)
    ensure_labels_exist()
    start_scheduler()
    logger.info("Gmail認証完了 - スケジューラ起動")
    return redirect(url_for("index"))


# ── LINE Webhook（双方向対応） ────────────────────────────
@app.route("/line/webhook", methods=["POST"])
def line_webhook():
    body = request.get_json(silent=True) or {}
    for event in body.get("events", []):
        # User ID取得
        user_id = event.get("source", {}).get("userId", "")
        if user_id:
            logger.info(f"[LINE] User ID: {user_id}")

        # テキストメッセージへの返信
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            reply_token = event.get("replyToken")
            question = event["message"]["text"].strip()
            logger.info(f"[LINE] 質問受信: {question[:50]}")

            # ① 即座に「確認中」と返信（replyTokenは30秒で失効するため）
            reply_message(reply_token, "確認いたします。少々お待ちください！🔍")

            # ② バックグラウンドで調査して push で送信
            def process_and_push(q=question, uid=user_id):
                try:
                    answer = answer_question(q)
                except Exception as e:
                    logger.error(f"[LINE] 回答生成エラー: {e}", exc_info=True)
                    answer = "申し訳ありません。処理中にエラーが発生しました。"
                push_message(uid, answer)

            threading.Thread(target=process_and_push, daemon=True).start()

    return "OK", 200


# ── 手動トリガー ──────────────────────────────────────────
@app.route("/process")
@localhost_only
def manual_process():
    creds = load_credentials()
    if not creds:
        return redirect(url_for("auth"))
    results = process_new_emails()
    return jsonify({"status": "ok", "results": results})


@app.route("/audit")
@localhost_only
def manual_audit():
    creds = load_credentials()
    if not creds:
        return redirect(url_for("auth"))
    results = run_audit()
    return jsonify({"status": "ok", "results": results})


@app.route("/status")
@localhost_only
def status():
    creds = load_credentials()
    return jsonify({
        "authenticated": creds is not None,
        "polling_interval_sec": config.POLLING_INTERVAL,
        "audit_days": config.AUDIT_DAYS,
    })


# ── 起動（127.0.0.1 のみ） ────────────────────────────────
if __name__ == "__main__":
    if load_credentials():
        ensure_labels_exist()
        start_scheduler()

    try:
        app.run(host="127.0.0.1", port=5000, debug=False)
    finally:
        stop_scheduler()
