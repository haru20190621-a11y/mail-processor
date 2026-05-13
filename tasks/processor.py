import logging
import time
from datetime import datetime

from gmail.client import (
    EmailMessage, fetch_unread_emails, fetch_emails_last_n_days,
    apply_label, mark_as_read, get_label_id_map,
)
from ai.classifier import classify_email
from line.notifier import send_notification
import config

logger = logging.getLogger(__name__)


def process_new_emails() -> dict:
    """リアルタイム仕分け：未読メールを全件処理"""
    emails = fetch_unread_emails()
    results = {"processed": 0, "errors": 0, "notified": 0}

    for msg in emails:
        try:
            result = classify_email(msg.subject, msg.sender, msg.body)

            apply_label(msg.id, result.label_name)
            apply_label(msg.id, config.LABELS["processed"])
            mark_as_read(msg.id)  # 全カテゴリ既読化（再通知防止）

            if result.notify_line:
                sent = send_notification(msg.subject, msg.sender, result.summary, result.category)
                if sent:
                    results["notified"] += 1

            results["processed"] += 1
            logger.info(f"[仕分け] {msg.subject[:40]} -> {result.label_name} ({result.reason})")

            # API レート制限対策
            time.sleep(0.5)

        except Exception as e:
            results["errors"] += 1
            logger.error(f"メール処理失敗 {msg.id}: {e}", exc_info=True)

    return results


def run_audit() -> dict:
    """監査バッチ：過去30日のメールを再チェック"""
    logger.info(f"[監査] 開始 {datetime.now().isoformat()}")
    emails = fetch_emails_last_n_days(config.AUDIT_DAYS)

    # 処理済みラベルのIDを取得して未処理メールを抽出
    processed_label_name = config.LABELS["processed"]
    label_id_map = get_label_id_map()
    processed_label_id = label_id_map.get(processed_label_name)

    if processed_label_id:
        unprocessed = [m for m in emails if processed_label_id not in m.labels]
    else:
        # ラベルIDが取得できない場合は全件対象
        unprocessed = emails

    logger.info(f"[監査] 対象: {len(unprocessed)}件（全{len(emails)}件中）")
    results = _process_emails_list(unprocessed)
    logger.info(f"[監査] 完了: {results}")
    return results


def _process_emails_list(emails: list[EmailMessage]) -> dict:
    results = {"processed": 0, "errors": 0, "notified": 0}
    for msg in emails:
        try:
            result = classify_email(msg.subject, msg.sender, msg.body)
            apply_label(msg.id, result.label_name)
            apply_label(msg.id, config.LABELS["processed"])
            if result.notify_line:
                sent = send_notification(msg.subject, msg.sender, result.summary, result.category)
                if sent:
                    results["notified"] += 1
            results["processed"] += 1
            time.sleep(0.3)
        except Exception as e:
            results["errors"] += 1
            logger.error(f"メール処理失敗 {msg.id}: {e}", exc_info=True)
    return results
