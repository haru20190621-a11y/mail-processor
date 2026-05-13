import logging
import requests

import config

LINE_API_URL = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

logger = logging.getLogger(__name__)


def send_notification(subject: str, sender: str, summary: str, category: str) -> bool:
    if not config.LINE_CHANNEL_ACCESS_TOKEN or not config.LINE_USER_ID:
        logger.warning("[LINE] トークン未設定のためスキップ")
        return False

    emoji = "📛" if category == "urgent" else "📄"
    text = (
        f"{emoji} 重要メール通知\n"
        f"件名: {subject}\n"
        f"送信者: {sender}\n"
        f"要約: {summary}"
    )

    headers = {
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": config.LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }

    resp = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)
    if resp.status_code == 200:
        logger.info(f"[LINE] 通知送信成功: {subject[:30]}")
        return True
    logger.error(f"[LINE] 送信失敗: {resp.status_code} {resp.text}")
    return False


def push_message(user_id: str, text: str) -> bool:
    """プッシュAPIで任意のテキストを送信する"""
    if not config.LINE_CHANNEL_ACCESS_TOKEN or not user_id:
        logger.warning("[LINE] トークンまたはUser ID未設定のためスキップ")
        return False

    headers = {
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id.strip(),
        "messages": [{"type": "text", "text": text[:5000]}],
    }

    resp = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)
    if resp.status_code == 200:
        logger.info("[LINE] プッシュ送信成功")
        return True
    logger.error(f"[LINE] プッシュ失敗: {resp.status_code} {resp.text}")
    return False


def reply_message(reply_token: str, text: str) -> bool:
    """LINEのreplyTokenを使ってユーザーに返信する"""
    if not config.LINE_CHANNEL_ACCESS_TOKEN:
        logger.warning("[LINE] トークン未設定のためスキップ")
        return False

    headers = {
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}],
    }

    resp = requests.post(LINE_REPLY_URL, headers=headers, json=payload, timeout=10)
    if resp.status_code == 200:
        logger.info("[LINE] 返信送信成功")
        return True
    logger.error(f"[LINE] 返信失敗: {resp.status_code} {resp.text}")
    return False
