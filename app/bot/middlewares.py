from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from app.database.repositories import UserRepository
from app.database.session import SessionLocal
from app.database.models import User
from sqlalchemy import select
from app.database.redis import redis
from app.config.settings import get_settings

class RateLimitMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid=getattr(getattr(event,"from_user",None),"id",None)
        if not uid: return await handler(event,data)
        settings=get_settings()
        is_admin=uid in settings.admin_ids
        limit=settings.admin_rate_limit if is_admin else settings.user_rate_limit
        window=settings.admin_rate_window if is_admin else settings.user_rate_window
        key=f"rl:{uid}"
        count=await redis.incr(key)
        if count==1: await redis.expire(key,window)
        if count>limit:
            if isinstance(event,Message): await event.answer("⏳ Juda ko‘p so‘rov. Birozdan keyin urinib ko‘ring.")
            elif isinstance(event,CallbackQuery): await event.answer("⏳ Juda ko‘p so‘rov.",show_alert=True)
            return
        return await handler(event,data)

class UserContextMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        tg=getattr(event,"from_user",None)
        if tg:
            async with SessionLocal() as s:
                user=await UserRepository(s).upsert(tg)
                await s.commit()
                if user.is_banned and not (tg.id in get_settings().admin_ids):
                    if isinstance(event,Message): await event.answer("🚫 Siz botdan foydalanish huquqidan mahrumsiz.")
                    elif isinstance(event,CallbackQuery): await event.answer("🚫 Siz bloklangansiz.",show_alert=True)
                    return
                data["db_user"]=user
        return await handler(event,data)
