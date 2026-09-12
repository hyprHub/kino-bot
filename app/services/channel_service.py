from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

class ChannelService:
    def __init__(self, repo, bot):
        self.repo, self.bot = repo, bot

    async def missing_required(self, user_id):
        missing=[]
        for ch in await self.repo.active_required():
            try:
                member=await self.bot.get_chat_member(ch.channel_id,user_id)
                if member.status in {"left","kicked"}:
                    missing.append(ch)
            except (TelegramBadRequest, TelegramForbiddenError):
                missing.append(ch)
        return missing
