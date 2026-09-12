import asyncio, logging, signal
from app.config.logging import setup_logging
from app.config.settings import get_settings
from app.bot.bot import build_bot, build_dispatcher
from app.database.session import close_db
from app.database.redis import close_redis
from app.health import start_health_server

async def main():
    settings=get_settings(); setup_logging(settings.log_level)
    log=logging.getLogger(__name__)
    bot=build_bot(); dp=build_dispatcher()
    runner=await start_health_server()
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        loop.add_signal_handler(sig,stop.set)
    polling=asyncio.create_task(dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types()))
    await stop.wait()
    log.info("shutdown_started")
    polling.cancel()
    try: await polling
    except asyncio.CancelledError: pass
    await bot.session.close()
    await runner.cleanup()
    await close_db(); await close_redis()
    log.info("shutdown_complete")

if __name__=="__main__":
    asyncio.run(main())
