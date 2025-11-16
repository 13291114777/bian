from __future__ import annotations

from datetime import datetime, timezone, timedelta
from tzlocal import get_localzone


def local_midnight_utc_ms(now: datetime | None = None) -> int:
    """返回本地时区当天0点（本地）对应的UTC毫秒时间戳。
    
    - 若 now 未传，则以当前时间为基准；
    - 通过本地时区计算当天0点，再转换为UTC。
    """
    if now is None:
        now = datetime.now(get_localzone())
    else:
        if now.tzinfo is None:
            now = get_localzone().localize(now)
        else:
            now = now.astimezone(get_localzone())

    local_zero = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 转为UTC
    utc_dt = local_zero.astimezone(timezone.utc)
    return int(utc_dt.timestamp() * 1000)


def to_utc_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = get_localzone().localize(dt)
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def now_ms_utc() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
