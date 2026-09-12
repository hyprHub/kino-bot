import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_movie_code_generation():
    from app.services.movie_service import MovieService
    repo=AsyncMock()
    repo.by_code.side_effect=[None]
    service=MovieService(repo,AsyncMock())
    code=await service.generate_code()
    assert 1000 <= code <= 9999
    repo.by_code.assert_awaited()

@pytest.mark.asyncio
async def test_movie_lookup_cache():
    from app.services.movie_service import MovieService
    repo=AsyncMock(); redis=AsyncMock()
    movie=object(); repo.by_code.return_value=movie
    service=MovieService(repo,redis)
    assert await service.get_by_code(1258) is movie
    redis.setex.assert_awaited_once()

@pytest.mark.asyncio
async def test_admin_id_is_numeric():
    from app.config.settings import Settings
    s=Settings(BOT_TOKEN="x",DATABASE_URL="postgresql://x",REDIS_URL="redis://x",ADMIN_IDS="1,2")
    assert s.admin_ids == [1,2]
