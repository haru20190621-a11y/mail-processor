import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

import config
from tasks.processor import process_new_emails, run_audit

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="Asia/Tokyo")


def _job_error_listener(event):
    if event.exception:
        logger.error(f"スケジュールジョブエラー [{event.job_id}]: {event.exception}", exc_info=event.traceback)


def _job_missed_listener(event):
    logger.warning(f"スケジュールジョブスキップ [{event.job_id}]: 実行時間を超過")


def start():
    if _scheduler.running:
        return  # 二重起動防止

    _scheduler.add_listener(_job_error_listener, EVENT_JOB_ERROR)
    _scheduler.add_listener(_job_missed_listener, EVENT_JOB_MISSED)

    # リアルタイム仕分け：ポーリング（N秒ごと）
    _scheduler.add_job(
        process_new_emails,
        trigger=IntervalTrigger(seconds=config.POLLING_INTERVAL),
        id="polling",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 監査バッチ：毎日 AM 3:00
    _scheduler.add_job(
        run_audit,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_audit",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(f"スケジューラ起動（ポーリング: {config.POLLING_INTERVAL}秒, 監査: 毎日AM3時）")


def stop():
    if _scheduler.running:
        _scheduler.shutdown()
