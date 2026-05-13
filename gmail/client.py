import base64
import email as email_lib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

import config
from gmail.auth import load_credentials

# ラベル名→IDのインメモリキャッシュ（API呼び出し削減）
_label_id_cache: dict[str, str] = {}


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str
    snippet: str
    body: str
    date: datetime
    labels: list[str] = field(default_factory=list)
    is_unread: bool = True


def get_service():
    creds = load_credentials()
    if not creds:
        raise RuntimeError("Gmail認証が必要です。/auth にアクセスしてください。")
    return build("gmail", "v1", credentials=creds)


def fetch_unread_emails(max_results: int = 50) -> list[EmailMessage]:
    service = get_service()
    results = service.users().messages().list(
        userId="me",
        q="is:unread",
        maxResults=max_results,
    ).execute()
    messages = results.get("messages", [])
    return [_fetch_message(service, m["id"]) for m in messages]


def search_emails(query: str, max_results: int = 5) -> list[EmailMessage]:
    """任意のGmail検索クエリでメールを取得する"""
    service = get_service()
    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()
    messages = results.get("messages", [])
    return [_fetch_message(service, m["id"]) for m in messages]


def fetch_emails_last_n_days(days: int = 30) -> list[EmailMessage]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    service = get_service()
    results = service.users().messages().list(
        userId="me",
        q=f"after:{since}",
        maxResults=500,
    ).execute()
    messages = results.get("messages", [])
    return [_fetch_message(service, m["id"]) for m in messages]


def apply_label(message_id: str, label_name: str) -> None:
    service = get_service()
    label_id = _get_or_create_label(service, label_name)
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]},
    ).execute()


def mark_as_read(message_id: str) -> None:
    service = get_service()
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def ensure_labels_exist() -> None:
    service = get_service()
    for label_name in config.LABELS.values():
        _get_or_create_label(service, label_name)


def get_label_id_map() -> dict[str, str]:
    """ラベル名 -> ラベルID のマッピングを返す"""
    service = get_service()
    result = service.users().labels().list(userId="me").execute()
    return {label["name"]: label["id"] for label in result.get("labels", [])}


def _fetch_message(service, message_id: str) -> EmailMessage:
    msg = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    subject = headers.get("Subject", "(件名なし)")
    sender = headers.get("From", "")
    date_str = headers.get("Date", "")
    try:
        date = email_lib.utils.parsedate_to_datetime(date_str)
    except Exception:
        date = datetime.now(timezone.utc)

    body = _extract_body(msg["payload"])
    label_ids = msg.get("labelIds", [])

    return EmailMessage(
        id=message_id,
        thread_id=msg["threadId"],
        subject=subject,
        sender=sender,
        snippet=msg.get("snippet", ""),
        body=body[:3000],  # Claude APIへの送信は3000文字まで
        date=date,
        labels=label_ids,
        is_unread="UNREAD" in label_ids,
    )


def _extract_body(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload["parts"]:
            result = _extract_body(part)
            if result:
                return result
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def _get_or_create_label(service, label_name: str) -> str:
    """ラベルIDを取得（キャッシュ付き）。存在しない場合は作成する。"""
    if label_name in _label_id_cache:
        return _label_id_cache[label_name]

    labels_result = service.users().labels().list(userId="me").execute()
    for label in labels_result.get("labels", []):
        _label_id_cache[label["name"]] = label["id"]  # まとめてキャッシュ
        if label["name"] == label_name:
            return label["id"]

    created = service.users().labels().create(
        userId="me",
        body={"name": label_name, "labelListVisibility": "labelShow",
              "messageListVisibility": "show"},
    ).execute()
    _label_id_cache[label_name] = created["id"]
    return created["id"]
