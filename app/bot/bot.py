from aiogram import Bot, Dispatcher
from app.config.settings import get_settings
from app.handlers.user import router as user_router
from app.handlers.admin import router as admin_router
from app.handlers.errors import router as error_router
from app.bot.middlewares import RateLimitMiddleware, UserContextMiddleware

def build_dispatcher():
    dp=Dispatcher()
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())
    dp.message.outer_middleware(UserContextMiddleware())
    dp.callback_query.outer_middleware(UserContextMiddleware())
    dp.include_router(error_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    return dp

def build_bot():
    return Bot(get_settings().bot_token)
