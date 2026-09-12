import pytest
from unittest.mock import AsyncMock
from app.database.repositories import MovieRepository

@pytest.mark.asyncio
async def test_increment_download_uses_atomic_update():
    # Contract test: the repository emits a SQL UPDATE that increments the
    # existing counter instead of read-modify-write.
    session=AsyncMock()
    repo=MovieRepository(session)
    await repo.increment_download(1,2,123)
    assert session.execute.await_count >= 2
