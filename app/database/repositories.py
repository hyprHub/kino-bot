from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Advertisement, AdvertisementDelivery, AuditLog, Ban, Channel, Movie, MovieDownload, User

class UserRepository:
    def __init__(self, session): self.s = session

    async def upsert(self, tg):
        stmt = insert(User).values(
            telegram_id=tg.id, username=tg.username, first_name=tg.first_name,
            last_name=tg.last_name, language=tg.language_code or "uz",
            is_active=True, last_seen_at=func.now()
        ).on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_=dict(username=tg.username, first_name=tg.first_name,
                      last_name=tg.last_name, last_seen_at=func.now(), is_active=True)
        ).returning(User)
        return (await self.s.execute(stmt)).scalar_one()

    async def by_tg(self, telegram_id):
        return (await self.s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()

    async def active_ids(self):
        return list((await self.s.scalars(select(User.telegram_id).where(User.is_active.is_(True), User.is_banned.is_(False)))).all())

class MovieRepository:
    def __init__(self, session): self.s = session

    async def by_code(self, code):
        return (await self.s.execute(select(Movie).where(Movie.code == code))).scalar_one_or_none()

    async def create(self, **data):
        movie = Movie(**data)
        self.s.add(movie)
        await self.s.flush()
        return movie

    async def update(self, movie_id, **data):
        await self.s.execute(update(Movie).where(Movie.id == movie_id).values(**data))
        return await self.s.get(Movie, movie_id)

    async def soft_delete(self, movie_id):
        return await self.update(movie_id, status="DELETED")

    async def restore(self, movie_id):
        return await self.update(movie_id, status="ACTIVE")

    async def search(self, q, limit=10):
        # PostgreSQL FTS + trigram are enabled by the migration; this expression
        # also remains usable when a deployment has not populated search_vector.
        stmt = select(Movie).where(
            Movie.status == "ACTIVE",
            text("search_vector @@ plainto_tsquery('simple', :q) OR similarity(name, :q) > 0.18")
        ).params(q=q).order_by(text("similarity(name, :q) DESC")).limit(limit)
        return list((await self.s.scalars(stmt)).all())

    async def top(self, limit=10):
        return list((await self.s.scalars(
            select(Movie).where(Movie.status=="ACTIVE").order_by(Movie.downloads_count.desc(), Movie.id).limit(limit)
        )).all())

    async def increment_download(self, movie_id, user_id, update_id=None):
        # Idempotent insert first; the unique update_id prevents duplicate updates.
        if update_id is not None:
            stmt = insert(MovieDownload).values(movie_id=movie_id, user_id=user_id, update_id=update_id)\
                .on_conflict_do_nothing(index_elements=[MovieDownload.update_id])
            result = await self.s.execute(stmt)
            if result.rowcount == 0:
                return False
        else:
            self.s.add(MovieDownload(movie_id=movie_id, user_id=user_id))
        await self.s.execute(update(Movie).where(Movie.id == movie_id).values(
            downloads_count=Movie.downloads_count + 1))
        return True

class ChannelRepository:
    def __init__(self, session): self.s = session
    async def active_required(self):
        return list((await self.s.scalars(select(Channel).where(Channel.active.is_(True), Channel.required.is_(True)))).all())
    async def all(self):
        return list((await self.s.scalars(select(Channel).order_by(Channel.id.desc()))).all())
    async def get(self, channel_id):
        return (await self.s.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    async def add(self, **data):
        obj = Channel(**data); self.s.add(obj); await self.s.flush(); return obj
    async def delete(self, db_id):
        await self.s.execute(delete(Channel).where(Channel.id == db_id))

class StatsRepository:
    def __init__(self, session): self.s = session
    async def snapshot(self):
        now = datetime.now(timezone.utc)
        day = now - timedelta(days=1)
        week = now - timedelta(days=7)
        month = now - timedelta(days=30)
        total_users = await self.s.scalar(select(func.count()).select_from(User))
        active_users = await self.s.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True), User.is_banned.is_(False)))
        banned = await self.s.scalar(select(func.count()).select_from(User).where(User.is_banned.is_(True)))
        movies = await self.s.scalar(select(func.count()).select_from(Movie).where(Movie.status=="ACTIVE"))
        downloads = await self.s.scalar(select(func.coalesce(func.sum(Movie.downloads_count),0)).select_from(Movie))
        today_downloads = await self.s.scalar(select(func.count()).select_from(MovieDownload).where(MovieDownload.downloaded_at >= day))
        week_downloads = await self.s.scalar(select(func.count()).select_from(MovieDownload).where(MovieDownload.downloaded_at >= week))
        month_downloads = await self.s.scalar(select(func.count()).select_from(MovieDownload).where(MovieDownload.downloaded_at >= month))
        today_users = await self.s.scalar(select(func.count()).select_from(User).where(User.joined_at >= day))
        return dict(total_users=total_users, active_users=active_users, banned=banned, movies=movies,
                    downloads=downloads, today_downloads=today_downloads, week_downloads=week_downloads,
                    month_downloads=month_downloads, today_users=today_users)

    async def trending(self, since, limit=10):
        stmt = select(Movie, func.count(MovieDownload.id).label("cnt")).join(
            MovieDownload, MovieDownload.movie_id == Movie.id
        ).where(Movie.status=="ACTIVE", MovieDownload.downloaded_at >= since).group_by(Movie.id).order_by(
            text("cnt DESC")).limit(limit)
        return [(m, c) for m,c in (await self.s.execute(stmt)).all()]

class AdminRepository:
    def __init__(self, session): self.s=session
    async def audit(self, admin_id, action, target=None, metadata=None):
        self.s.add(AuditLog(admin_id=admin_id, action=action, target=target, metadata_json=metadata or {}))

class BanRepository:
    def __init__(self, session): self.s=session
    async def ban(self, user_id, admin_id, reason):
        await self.s.execute(insert(Ban).values(user_id=user_id, created_by=admin_id, reason=reason)
                              .on_conflict_do_update(index_elements=[Ban.user_id],
                                                     set_={"reason": reason, "created_by": admin_id}))
        await self.s.execute(update(User).where(User.id==user_id).values(is_banned=True))
    async def unban(self, user_id):
        await self.s.execute(delete(Ban).where(Ban.user_id==user_id))
        await self.s.execute(update(User).where(User.id==user_id).values(is_banned=False))

class CampaignRepository:
    def __init__(self, session): self.s=session
    async def create(self, **data):
        c=Advertisement(**data); self.s.add(c); await self.s.flush(); return c
    async def get(self, cid): return await self.s.get(Advertisement,cid)
    async def pending_scheduled(self, now):
        return list((await self.s.scalars(select(Advertisement).where(
            Advertisement.status=="SCHEDULED", Advertisement.scheduled_at <= now))).all())
    async def set_status(self,cid,status):
        await self.s.execute(update(Advertisement).where(Advertisement.id==cid).values(status=status))
    async def seed_deliveries(self,cid,user_ids):
        if not user_ids: return
        await self.s.execute(insert(AdvertisementDelivery),
                              [{"campaign_id":cid,"user_id":uid} for uid in user_ids])
