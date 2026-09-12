import asyncio, logging, signal
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramNetworkError
from sqlalchemy import select, update
from app.config.logging import setup_logging
from app.config.settings import get_settings
from app.database.redis import redis, close_redis
from app.database.session import SessionLocal, close_db
from app.database.models import AdvertisementDelivery, Advertisement, User
from app.database.repositories import CampaignRepository

log=logging.getLogger(__name__)

async def enqueue_scheduled():
    async with SessionLocal() as s:
        rows=await CampaignRepository(s).pending_scheduled(datetime.now(timezone.utc))
        for c in rows:
            await CampaignRepository(s).set_status(c.id,"QUEUED")
        if rows: await s.commit()
    for c in rows: await redis.rpush("broadcast:queue",str(c.id))

async def send_campaign(bot,cid):
    settings=get_settings()
    async with SessionLocal() as s:
        c=await s.get(Advertisement,cid)
        if not c or c.status not in {"QUEUED","RUNNING"}: return
        await CampaignRepository(s).set_status(cid,"RUNNING"); await s.commit()

    while True:
        async with SessionLocal() as s:
            deliveries=list((await s.scalars(
                select(AdvertisementDelivery).where(
                    AdvertisementDelivery.campaign_id==cid,
                    AdvertisementDelivery.status=="PENDING",
                    AdvertisementDelivery.attempts < settings.broadcast_retry_limit
                ).limit(settings.broadcast_batch_size)
            )).all())
            if not deliveries:
                await CampaignRepository(s).set_status(cid,"DONE")
                await s.commit(); return
            c=await s.get(Advertisement,cid)
            for d in deliveries:
                try:
                    await bot.copy_message(d.user_id,c.source_chat_id,c.source_message_id)
                    d.status="SENT"; c.sent_count += 1
                except TelegramRetryAfter as e:
                    await s.rollback()
                    await asyncio.sleep(e.retry_after)
                    continue
                except (TelegramForbiddenError,TelegramBadRequest) as e:
                    d.status="FAILED"; d.attempts += 1; d.last_error=type(e).__name__; c.failed_count += 1
                    await s.execute(update(User).where(User.id==d.user_id).values(is_active=False))
                except TelegramNetworkError as e:
                    d.attempts += 1; d.last_error=type(e).__name__
                    await s.commit(); await asyncio.sleep(min(2**d.attempts,60)); continue
                except Exception as e:
                    d.attempts += 1; d.last_error=type(e).__name__
            await s.commit()
        await asyncio.sleep(max(0.04,1.0/settings.broadcast_rate_limit))

async def main():
    setup_logging(get_settings().log_level)
    bot=Bot(get_settings().bot_token)
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM): loop.add_signal_handler(sig,stop.set)
    async def scheduler():
        while not stop.is_set():
            try: await enqueue_scheduled()
            except Exception: log.exception("scheduler_error")
            await asyncio.sleep(5)
    async def queue_worker():
        while not stop.is_set():
            try:
                item=await redis.blpop("broadcast:queue",timeout=2)
                if item: await send_campaign(bot,int(item[1]))
            except Exception: log.exception("broadcast_worker_error"); await asyncio.sleep(2)
    tasks=[asyncio.create_task(scheduler()),asyncio.create_task(queue_worker())]
    await stop.wait()
    for t in tasks: t.cancel()
    await bot.session.close(); await close_db(); await close_redis()

if __name__=="__main__": asyncio.run(main())
