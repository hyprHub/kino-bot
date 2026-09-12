import json, logging
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.config.settings import get_settings
from app.database.session import SessionLocal
from app.database.repositories import MovieRepository, ChannelRepository, StatsRepository, AdminRepository, BanRepository, UserRepository, CampaignRepository
from app.database.models import Movie, User, Channel
from app.bot.keyboards import admin_menu, content_menu, confirm
from app.states import MovieAddStates, BanStates, BroadcastStates
from app.services.movie_service import MovieService
from app.database.redis import redis

router=Router()
log=logging.getLogger(__name__)

def is_admin(uid): return uid in get_settings().admin_ids

def admin_only(handler):
    async def wrapped(event,*args,**kwargs):
        uid=getattr(getattr(event,"from_user",None),"id",None)
        if uid not in get_settings().admin_ids:
            if isinstance(event,Message): await event.answer("⛔ Ruxsat yo‘q.")
            else: await event.answer("⛔ Ruxsat yo‘q.",show_alert=True)
            return
        return await handler(event,*args,**kwargs)
    return wrapped

@router.message(Command("admin"))
@admin_only
async def admin_cmd(message:Message): await message.answer("👑 <b>ADMIN PANEL</b>",reply_markup=admin_menu(),parse_mode="HTML")

@router.callback_query(F.data=="adm:home")
@admin_only
async def admin_home(cb:CallbackQuery): await cb.message.edit_text("👑 <b>ADMIN PANEL</b>",reply_markup=admin_menu(),parse_mode="HTML")

@router.callback_query(F.data=="adm:content")
@admin_only
async def content(cb:CallbackQuery): await cb.message.edit_text("🎬 <b>KONTENT</b>",reply_markup=content_menu(),parse_mode="HTML")

@router.callback_query(F.data=="cnt:add")
@admin_only
async def add_start(cb:CallbackQuery,state:FSMContext):
    await state.clear()
    await state.set_state(MovieAddStates.waiting_name)
    pending=await redis.get(f"pending_movie:{cb.from_user.id}")
    if not pending:
        await cb.message.answer("Database kanaliga video yuboring. Bot sizga tayyor media uchun davom ettirish oynasini beradi.")
    else:
        await cb.message.answer("🎬 Kino nomini kiriting:")
    await cb.answer()

async def save_audit(s,uid,action,target=None,meta=None):
    await AdminRepository(s).audit(uid,action,target,meta)

@router.message(MovieAddStates.waiting_name)
async def movie_name(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text.strip()); await state.set_state(MovieAddStates.waiting_genre)
    await message.answer("🎭 Janrini kiriting:")

@router.message(MovieAddStates.waiting_genre)
async def movie_genre(message:Message,state:FSMContext):
    await state.update_data(genre=message.text.strip()); await state.set_state(MovieAddStates.waiting_country)
    await message.answer("🌍 Davlatini kiriting:")

@router.message(MovieAddStates.waiting_country)
async def movie_country(message:Message,state:FSMContext):
    await state.update_data(country=message.text.strip()); await state.set_state(MovieAddStates.waiting_year)
    await message.answer("📅 Chiqqan yilini kiriting:")

@router.message(MovieAddStates.waiting_year)
async def movie_year(message:Message,state:FSMContext):
    try: year=int(message.text.strip())
    except ValueError: await message.answer("❌ Yil raqam bo‘lishi kerak."); return
    if not 1888<=year<=2100: await message.answer("❌ Yil noto‘g‘ri."); return
    await state.update_data(release_year=year); await state.set_state(MovieAddStates.waiting_description)
    await message.answer("📝 Tavsifini kiriting:")

@router.message(MovieAddStates.waiting_description)
async def movie_desc(message:Message,state:FSMContext):
    await state.update_data(description=message.text.strip())
    data=await state.get_data()
    pending=await redis.get(f"pending_movie:{message.from_user.id}")
    if not pending:
        await message.answer("❌ Media topilmadi. Avval database kanalidan video yuboring."); await state.clear(); return
    media=json.loads(pending)
    text=(f"🎬 <b>TASDIQLASH</b>\n\n<b>{data['name']}</b>\n"
          f"🎭 {data['genre']}\n🌍 {data['country']}\n📅 {data['release_year']}\n📝 {data['description']}\n\nTasdiqlaysizmi?")
    await state.update_data(media=media); await state.set_state(MovieAddStates.confirm)
    from app.bot.keyboards import confirm
    await message.answer(text,reply_markup=confirm("movie:create"),parse_mode="HTML")

@router.callback_query(MovieAddStates.confirm,F.data=="confirm:movie:create")
@admin_only
async def movie_confirm(cb:CallbackQuery,state:FSMContext):
    data=await state.get_data(); media=data["media"]
    async with SessionLocal() as s:
        service=MovieService(MovieRepository(s),redis)
        movie=await service.create(name=data["name"],genre=data["genre"],country=data["country"],
            release_year=data["release_year"],description=data["description"],
            telegram_channel_id=media["channel_id"],telegram_message_id=media["message_id"],
            telegram_file_id=media["file_id"],telegram_file_unique_id=media["file_unique_id"],
            media_type=media["media_type"],status="ACTIVE")
        await save_audit(s,cb.from_user.id,"movie.create",str(movie.id),{"code":movie.code})
        await s.commit()
    await redis.delete(f"pending_movie:{cb.from_user.id}")
    await state.clear()
    await cb.message.edit_text(f"✅ Kino muvaffaqiyatli qo‘shildi.\n🔑 Kino kodi: <code>{movie.code}</code>",parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data=="cnt:delete")
@admin_only
async def delete_prompt(cb:CallbackQuery): await cb.message.answer("🗑 O‘chirish uchun: /kino_delete CODE")

@router.message(Command("kino_delete"))
@admin_only
async def delete_movie(message:Message):
    parts=message.text.split()
    if len(parts)!=2 or not parts[1].isdigit(): await message.answer("Format: /kino_delete 1258"); return
    async with SessionLocal() as s:
        repo=MovieRepository(s); m=await repo.by_code(int(parts[1]))
        if not m: await message.answer("❌ Kino topilmadi."); return
        await redis.setex(f"delete_confirm:{message.from_user.id}",60,str(m.id))
        await message.answer(f"⚠️ <b>{m.name}</b> ni o‘chirishmi?",reply_markup=confirm("movie:delete"),parse_mode="HTML")

@router.callback_query(F.data=="confirm:movie:delete")
@admin_only
async def delete_confirm(cb:CallbackQuery):
    mid=await redis.get(f"delete_confirm:{cb.from_user.id}")
    if not mid: await cb.answer("Tasdiqlash muddati tugagan.",show_alert=True); return
    async with SessionLocal() as s:
        repo=MovieRepository(s); m=await s.get(Movie,int(mid))
        if not m: await cb.answer("Topilmadi.",show_alert=True); return
        await repo.soft_delete(m.id); await save_audit(s,cb.from_user.id,"movie.delete",str(m.id)); await s.commit()
        await redis.delete(f"delete_confirm:{cb.from_user.id}")
    await cb.message.edit_text("✅ Kino soft-delete qilindi."); await cb.answer()

@router.message(Command("kino"))
@admin_only
async def kino(message:Message):
    parts=message.text.split()
    if len(parts)!=2 or not parts[1].isdigit(): await message.answer("Format: /kino 1258"); return
    async with SessionLocal() as s:
        m=await MovieRepository(s).by_code(int(parts[1]))
        if not m: await message.answer("❌ Topilmadi."); return
        await message.answer(f"🎬 <b>{m.name}</b>\n🔑 {m.code}\n🎭 {m.genre}\n🌍 {m.country}\n📅 {m.release_year}\n⬇️ {m.downloads_count:,}\nStatus: {m.status}",parse_mode="HTML")

@router.callback_query(F.data=="adm:stats")
@admin_only
async def stats(cb:CallbackQuery):
    async with SessionLocal() as s:
        x=await StatsRepository(s).snapshot()
    await cb.message.edit_text(
        f"📊 <b>BOT STATISTIKASI</b>\n\n👥 Users: {x['total_users']:,}\n🟢 Active: {x['active_users']:,}\n🚫 Banned: {x['banned']:,}\n🎬 Movies: {x['movies']:,}\n⬇️ Downloads: {x['downloads']:,}\n\n📅 Bugun: +{x['today_users']:,} users / {x['today_downloads']:,} downloads\n📈 7 kun: {x['week_downloads']:,}\n📆 30 kun: {x['month_downloads']:,}",parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data=="adm:channels")
@admin_only
async def channels(cb:CallbackQuery):
    async with SessionLocal() as s: rows=await ChannelRepository(s).all()
    text="📺 <b>HAMKOR / DATABASE KANALLAR</b>\n\n"
    for c in rows: text+=f"#{c.id} {c.title or c.channel_id} | required={c.required} | db={c.is_database} | active={c.active}\n"
    text+="\nQo‘shish: /channel_add -100123456789 @username Title https://t.me/... 1 1"
    await cb.message.edit_text(text,parse_mode="HTML"); await cb.answer()

@router.message(Command("channel_add"))
@admin_only
async def channel_add(message:Message):
    p=message.text.split(maxsplit=6)
    if len(p)<7: await message.answer("Format: /channel_add CHANNEL_ID USERNAME TITLE LINK REQUIRED(0/1) DATABASE(0/1)"); return
    async with SessionLocal() as s:
        repo=ChannelRepository(s)
        c=await repo.add(channel_id=int(p[1]),username=p[2] or None,title=p[3],invite_link=p[4],
                         required=bool(int(p[5])),is_database=bool(int(p[6])),active=True)
        await s.commit()
    await message.answer(f"✅ Kanal qo‘shildi: #{c.id}")

@router.message(Command("channel_delete"))
@admin_only
async def channel_delete(message:Message):
    p=message.text.split()
    if len(p)!=2 or not p[1].isdigit(): await message.answer("Format: /channel_delete ID"); return
    async with SessionLocal() as s:
        await ChannelRepository(s).delete(int(p[1])); await s.commit()
    await message.answer("✅ Kanal o‘chirildi.")

@router.message(Command("ban"))
@admin_only
async def ban_start(message:Message,state:FSMContext):
    await state.set_state(BanStates.waiting_user); await message.answer("🚫 User Telegram ID:")

@router.message(BanStates.waiting_user)
async def ban_user(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.isdigit(): await message.answer("ID raqam bo‘lishi kerak."); return
    await state.update_data(user_tg=int(message.text)); await state.set_state(BanStates.waiting_reason); await message.answer("Sabab:")

@router.message(BanStates.waiting_reason)
async def ban_reason(message:Message,state:FSMContext):
    data=await state.get_data()
    async with SessionLocal() as s:
        user=await UserRepository(s).by_tg(data["user_tg"])
        if not user: await message.answer("❌ User topilmadi."); await state.clear(); return
        await BanRepository(s).ban(user.id,message.from_user.id,message.text.strip())
        await save_audit(s,message.from_user.id,"user.ban",str(user.id),{"reason":message.text.strip()}); await s.commit()
    await state.clear(); await message.answer("✅ User ban qilindi.")

@router.message(Command("unban"))
@admin_only
async def unban(message:Message):
    p=message.text.split()
    if len(p)!=2 or not p[1].isdigit(): await message.answer("Format: /unban TELEGRAM_ID"); return
    async with SessionLocal() as s:
        user=await UserRepository(s).by_tg(int(p[1]))
        if user: await BanRepository(s).unban(user.id); await s.commit()
    await message.answer("✅ Unban bajarildi.")

@router.callback_query(F.data=="adm:broadcast")
@admin_only
async def broadcast_menu(cb:CallbackQuery):
    await cb.message.answer("📢 Broadcast yaratish: /broadcast\nBot sizdan yuboriladigan xabarni kutadi.")

@router.message(Command("broadcast"))
@admin_only
async def broadcast_start(message:Message,state:FSMContext):
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer("📢 Endi broadcast qilinadigan Telegram xabarni yuboring (text/photo/video/document va boshqalar).")

@router.message(BroadcastStates.waiting_message)
async def broadcast_message(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(source_chat_id=message.chat.id,source_message_id=message.message_id)
    await state.set_state(BroadcastStates.waiting_schedule)
    await message.answer("📅 Darhol yuborish uchun <code>now</code>, rejalashtirish uchun ISO vaqt kiriting. Masalan 2026-09-15T20:00:00+05:00",parse_mode="HTML")

@router.message(BroadcastStates.waiting_schedule)
async def broadcast_schedule(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    raw=message.text.strip()
    scheduled=None
    if raw.lower()!="now":
        try: scheduled=datetime.fromisoformat(raw)
        except ValueError: await message.answer("❌ ISO vaqt noto‘g‘ri."); return
    data=await state.get_data()
    async with SessionLocal() as s:
        ids=await UserRepository(s).active_ids()
        c=await CampaignRepository(s).create(created_by=message.from_user.id,source_chat_id=data["source_chat_id"],
            source_message_id=data["source_message_id"],scheduled_at=scheduled,status="QUEUED" if not scheduled else "SCHEDULED",
            target_count=len(ids))
        await CampaignRepository(s).seed_deliveries(c.id,ids)
        await save_audit(s,message.from_user.id,"broadcast.create",str(c.id),{"target":len(ids)})
        await s.commit()
    if not scheduled: await redis.rpush("broadcast:queue",str(c.id))
    await state.clear()
    await message.answer(f"✅ Campaign #{c.id} yaratildi. Target: {len(ids):,}")

@router.callback_query(F.data=="adm:users")
@admin_only
async def users(cb:CallbackQuery):
    async with SessionLocal() as s:
        n=await s.scalar(select(__import__("sqlalchemy").func.count()).select_from(User))
    await cb.message.edit_text(f"👥 Jami users: {n:,}\nQidirish: /user TELEGRAM_ID"); await cb.answer()

@router.message(Command("user"))
@admin_only
async def user_info(message:Message):
    p=message.text.split()
    if len(p)!=2 or not p[1].isdigit(): await message.answer("Format: /user TELEGRAM_ID"); return
    async with SessionLocal() as s:
        u=await UserRepository(s).by_tg(int(p[1]))
        if not u: await message.answer("❌ User topilmadi."); return
        await message.answer(f"👤 {u.first_name or ''} @{u.username or '—'}\nID: <code>{u.telegram_id}</code>\nBanned: {u.is_banned}\nLast seen: {u.last_seen_at}",parse_mode="HTML")

@router.channel_post()
async def database_channel_media(message:Message):
    # Only whitelisted database channels are accepted.
    if message.chat.id not in get_settings().database_channel_ids: return
    media_type=None; file_id=None; unique_id=None
    if message.video: media_type="video"; file_id=message.video.file_id; unique_id=message.video.file_unique_id
    elif message.document: media_type="document"; file_id=message.document.file_id; unique_id=message.document.file_unique_id
    elif message.animation: media_type="animation"; file_id=message.animation.file_id; unique_id=message.animation.file_unique_id
    elif message.photo: media_type="photo"; file_id=message.photo[-1].file_id; unique_id=message.photo[-1].file_unique_id
    elif message.audio: media_type="audio"; file_id=message.audio.file_id; unique_id=message.audio.file_unique_id
    if not file_id: return
    payload={"channel_id":message.chat.id,"message_id":message.message_id,"file_id":file_id,"file_unique_id":unique_id,"media_type":media_type}
    # First configured admin is notified. An admin can then continue the FSM.
    admin_id=get_settings().admin_ids[0] if get_settings().admin_ids else None
    if not admin_id: return
    await redis.setex(f"pending_movie:{admin_id}",3600,json.dumps(payload))
    try:
        await message.bot.send_message(admin_id,"🎬 <b>Yangi media topildi.</b>\n/admin → Kontent → Kino qo‘shish orqali metadata kiriting.",parse_mode="HTML")
    except Exception: log.exception("Failed to notify admin")
