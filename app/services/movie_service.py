import secrets
from sqlalchemy import select
from app.database.models import Movie

class MovieService:
    def __init__(self, repo, redis, cache_ttl=300):
        self.repo, self.redis, self.cache_ttl = repo, redis, cache_ttl

    async def generate_code(self):
        for _ in range(20):
            code = secrets.randbelow(9000) + 1000
            if not await self.repo.by_code(code):
                return code
        raise RuntimeError("Unable to generate unique movie code")

    async def get_by_code(self, code):
        key=f"movie:code:{code}"
        cached=await self.redis.get(key)
        if cached:
            return await self.repo.by_code(code)
        movie=await self.repo.by_code(code)
        if movie:
            await self.redis.setex(key,self.cache_ttl,"1")
        return movie

    async def invalidate(self, code):
        await self.redis.delete(f"movie:code:{code}")

    async def create(self, **data):
        data["code"] = await self.generate_code()
        movie = await self.repo.create(**data)
        await self.repo.s.commit()
        return movie

    async def download(self, movie, user_id, update_id):
        ok=await self.repo.increment_download(movie.id,user_id,update_id)
        await self.repo.s.commit()
        if ok:
            await self.invalidate(movie.code)
        return ok
