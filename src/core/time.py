from datetime import datetime, timedelta, timezone


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now_bj() -> datetime:
    """返回带时区的北京时间。"""
    return datetime.now(BEIJING_TZ)


def now_bj_iso() -> str:
    """返回 SQLite 友好的北京时间字符串，不带 offset，便于按日期字符串过滤。"""
    return now_bj().replace(tzinfo=None).isoformat(timespec="seconds")


def today_bj() -> str:
    return now_bj().date().isoformat()


def run_id_bj(prefix: str = "run") -> str:
    return f"{prefix}_{now_bj().strftime('%Y%m%d_%H%M%S')}"


def parse_bj_datetime(value: str) -> datetime:
    """解析项目时间；旧 UTC 字符串会转换为北京时间，新无 offset 字符串按北京时间处理。"""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(BEIJING_TZ).replace(tzinfo=None)
