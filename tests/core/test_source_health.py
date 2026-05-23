import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.source_health import SourceHealthTracker, APPROVED_RATE_THRESHOLD

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetch_one = AsyncMock()
    db.fetch_all = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_should_evict_protection_period(mock_db):
    """保护期内不应淘汰"""
    tracker = SourceHealthTracker(mock_db)
    mock_db.fetch_one.return_value = {"c": 2}  # 少于 3 次
    should, reason = await tracker.should_evict("test_source")
    assert should is False

@pytest.mark.asyncio
async def test_should_evict_low_approved_rate(mock_db):
    """approved 率低于阈值应淘汰"""
    tracker = SourceHealthTracker(mock_db)
    mock_db.fetch_one.return_value = {"c": 5}
    mock_db.fetch_all.return_value = [
        {"total_collected": 10, "approved": 1},
        {"total_collected": 10, "approved": 2},
        {"total_collected": 10, "approved": 1},
    ]
    should, reason = await tracker.should_evict("test_source")
    assert should is True
    assert "30.0%" in reason

@pytest.mark.asyncio
async def test_should_not_evict_healthy(mock_db):
    """approved 率正常不应淘汰"""
    tracker = SourceHealthTracker(mock_db)
    mock_db.fetch_one.return_value = {"c": 5}
    mock_db.fetch_all.return_value = [
        {"total_collected": 10, "approved": 7},
        {"total_collected": 10, "approved": 6},
        {"total_collected": 10, "approved": 8},
    ]
    should, reason = await tracker.should_evict("test_source")
    assert should is False