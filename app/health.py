from aiohttp import web
from sqlalchemy import text
from app.database.session import engine
from app.database.redis import redis
from app.config.settings import get_settings

async def health(request):
    db="OK"; r="OK"
    try:
        async with engine.connect() as c: await c.execute(text("SELECT 1"))
    except Exception: db="ERROR"
    try: await redis.ping()
    except Exception: r="ERROR"
    status=200 if db=="OK" and r=="OK" else 503
    return web.json_response({"application":"OK","database":db,"redis":r},status=status)

async def start_health_server():
    app=web.Application()
    app.router.add_get("/health",health)
    runner=web.AppRunner(app); await runner.setup()
    site=web.TCPSite(runner,get_settings().health_host,get_settings().health_port)
    await site.start()
    return runner
