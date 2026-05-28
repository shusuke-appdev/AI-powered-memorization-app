"""アプリで使う日付を日本時間基準に統一するヘルパー."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Tokyo"


def get_app_timezone() -> ZoneInfo:
    """環境変数 APP_TIMEZONE または既定の日本時間を返す."""
    timezone_name = os.environ.get("APP_TIMEZONE", DEFAULT_TIMEZONE)
    return ZoneInfo(timezone_name)


def local_date_iso(now: datetime | None = None) -> str:
    """アプリ基準タイムゾーンでの今日の日付を ISO 文字列で返す."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(get_app_timezone()).date().isoformat()


def utc_now_iso() -> str:
    """DB保存用の現在UTC時刻を ISO 文字列で返す."""
    return datetime.now(timezone.utc).isoformat()
