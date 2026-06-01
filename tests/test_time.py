from datetime import timedelta

from src.core.time import now_bj, parse_bj_datetime


def test_now_bj_uses_beijing_timezone():
    assert now_bj().utcoffset() == timedelta(hours=8)


def test_parse_bj_datetime_converts_old_utc_values():
    assert parse_bj_datetime("2026-06-01T16:30:00Z").isoformat() == "2026-06-02T00:30:00"


def test_parse_bj_datetime_keeps_new_beijing_values():
    assert parse_bj_datetime("2026-06-02T00:30:00").isoformat() == "2026-06-02T00:30:00"
