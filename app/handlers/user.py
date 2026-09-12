import re
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from app.database.session import SessionLocal
from app.database.repositories import MovieRepository, ChannelRepository, StatsRepository
from app.database.redis import redis
from app.bot.keyboards import user_menu, subscription_keyboard
from app.services.movie_service import MovieService
from app.services.channel_service import ChannelService
from app.states import SearchStates
from aiogram.fsm.context import FSMContext
from app.database.models import Movie

router=Router()

def card(movie):
    return (f"🎬 <b>{movie.name}</b>\n\n🔑 Kod: <code>{movie.code}</code>\n"
            f"🎭 Janri: {movie.genre or '—'}\n🌍 Davlat: {movie.country or '—'}\n"
            f"📅 Yil: {movie.release_year or '—'}\n⬇️ Yuklab olingan: {movie.downloads_count:,}\n"
            f"📝 {movie.description or 'Tavsif mavjud emas.'}")

@router.message(CommandStart())
async def start(message:Message):
    await message.answer("🎬 <b>Kino bot</b>\nKino kodini yuboring yoki menyudan foydalaning.",reply_markup=user_menu())

@router.message(F.text=="🎬 Kino kodlari")
async def code_help(message:Message):
    await message.answer("🔑 Kino kodini yuboring.\nMasalan: <code>1258</code>")

@router.message(F.text=="🏆 TOP 10")
async def top10(message:Message):
    async with SessionLocal() as s:
        movies=await MovieRepository(s).top()
        text="🏆 <b>TOP 10 KINOLAR</b>\n\n"
        for i,m in enumerate(movies,1): text+=f"{i}. {m.name} — ⬇️ {m.downloads_count:,}\n"
        await message.answer(text if movies else "Hozircha statistika mavjud emas.")

@router.message(F.text=="🔥 Trending")
async def trending(message:Message):
    from datetime import datetime,timedelta,timezone
    async with SessionLocal() as s:
        rows=await StatsRepository(s).trending(datetime.now(timezone.utc)-timedelta(days=1))
        text="🔥 <b>BUGUN TRENDING</b>\n\n"
        for i,(m,c) in enumerate(rows,1): text+=f"{i}. {m.name} — {c:,}\n"
        await message.answer(text if rows else "Bugun trending ma'lumot yo‘q.")

@router.message(F.text=="ℹ️ Admin haqida")
async def admin_info(message:Message):
    async with SessionLocal() as s:
        from app.database.models import Setting
        obj=await s.get(Setting,"admin_info")
        data=obj.value if obj else {}
        await message.answer(f"ℹ️ <b>{data.get('username','Admin')}</b>\n{data.get('description','Bog‘lanish uchun admin bilan aloqaga chiqing.')}\n{data.get('contact_link','')}")

@router.message(F.text=="🔍 Qidirish")
async def search_start(message:Message,state:FSMContext):
    await state.set_state(SearchStates.waiting_query)
    await message.answer("🔍 Kino nomini yozing:")

@router.message(SearchStates.waiting_query)
async def search_finish(message:Message,state:FSMContext):
    async with SessionLocal() as s:
        movies=await MovieRepository(s).search(message.text.strip())
        if not movies: await message.answer("❌ Kino topilmadi.")
        else:
            await message.answer("\n\n".join(f"🎬 {m.name}\n🔑 <code>{m.code}</code>" for m in movies))
    await state.clear()

@router.callback_query(F.data=="sub:check")
async def check_sub(cb:CallbackQuery):
    async with SessionLocal() as s:
        missing=await ChannelService(ChannelRepository(s),cb.bot).missing_required(cb.from_user.id)
        if missing: await cb.answer("Hali barcha kanallarga obuna bo‘lmagansiz.",show_alert=True)
        else: await cb.message.edit_text("✅ Obuna tasdiqlandi. Endi kino kodini yuboring.")
    await cb.answer()

@router.message(F.text.regexp(r"^\d{1,8}$"))
async def movie_by_code(message:Message):
    code=int(message.text)
    async with SessionLocal() as s:
        channels=ChannelRepository(s)
        missing=await ChannelService(channels,message.bot).missing_required(message.from_user.id)
        if missing:
            await message.answer("🔒 Avval hamkor kanallarga obuna bo‘ling.",reply_markup=subscription_keyboard(missing)); return
        repo=MovieRepository(s)
        movie=await repo.by_code(code)
        if not movie: await message.answer("❌ Bunday kino kodi topilmadi."); return
        if movie.status!="ACTIVE": await message.answer("❌ Bu kino hozir mavjud emas."); return
        service=MovieService(repo,redis)
        await service.download(movie,(await repo.s.get_bind().run_sync(lambda _: None)) if False else message.from_user.id,message.message_id)
        await message.answer(card(movie),parse_mode="HTML")
        if movie.media_type=="video": await message.answer_video(movie.telegram_file_id)
        elif movie.media_type=="document": await message.answer_document(movie.telegram_file_id)
        elif movie.media_type=="animation": await message.answer_animation(movie.telegram_file_id)
        elif movie.media_type=="photo": await message.answer_photo(movie.telegram_file_id)
        elif movie.media_type=="audio": await message.answer_audio(movie.telegram_file_id)
        else: await message.answer_document(movie.telegram_file_id)

@router.message(Command("help"))
async def help_cmd(message:Message):
    await message.answer("🔑 Kino kodi yuboring yoki 🔍 qidirishdan foydalaning.")
