import logging
from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramNetworkError
router=Router()
log=logging.getLogger(__name__)

@router.error()
async def global_error(event:ErrorEvent):
    exc=event.exception
    log.error("telegram_update_error",extra={"error":repr(exc)},exc_info=True)
    update=event.update
    msg=getattr(update,"message",None)
    if msg:
        try: await msg.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko‘ring.")
        except Exception: pass
    return True
