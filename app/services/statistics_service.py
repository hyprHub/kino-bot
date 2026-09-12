from datetime import datetime, timedelta, timezone
class StatisticsService:
    def __init__(self, repo): self.repo=repo
    async def snapshot(self): return await self.repo.snapshot()
    async def trending(self, period="day"):
        days=1 if period=="day" else 7
        return await self.repo.trending(datetime.now(timezone.utc)-timedelta(days=days))
