import json
class SettingsService:
    def __init__(self, redis, repo=None, ttl=60):
        self.redis,self.repo,self.ttl=redis,repo,ttl
    async def get(self,key,default=None):
        value=await self.redis.get(f"setting:{key}")
        if value is not None:
            return json.loads(value)
        if self.repo:
            from sqlalchemy import select
            from app.database.models import Setting
            obj=await self.repo.scalar(select(Setting).where(Setting.key==key))
            if obj:
                await self.redis.setex(f"setting:{key}",self.ttl,json.dumps(obj.value))
                return obj.value
        return default
    async def set(self,key,value):
        if self.repo:
            from sqlalchemy.dialects.postgresql import insert
            from app.database.models import Setting
            await self.repo.execute(insert(Setting).values(key=key,value=value).on_conflict_do_update(
                index_elements=[Setting.key],set_={"value":value}))
            await self.repo.commit()
        await self.redis.setex(f"setting:{key}",self.ttl,json.dumps(value))
