from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
def user_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Kino kodlari"), KeyboardButton(text="🏆 TOP 10")],
        [KeyboardButton(text="ℹ️ Admin haqida")],
        [KeyboardButton(text="🔍 Qidirish"), KeyboardButton(text="🔥 Trending")],
    ], resize_keyboard=True)

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kontent",callback_data="adm:content"),
         InlineKeyboardButton(text="📺 Kanallar",callback_data="adm:channels")],
        [InlineKeyboardButton(text="📢 Reklama",callback_data="adm:broadcast"),
         InlineKeyboardButton(text="📊 Statistika",callback_data="adm:stats")],
        [InlineKeyboardButton(text="👥 Users",callback_data="adm:users"),
         InlineKeyboardButton(text="🚫 Banlar",callback_data="adm:bans")],
        [InlineKeyboardButton(text="⚙️ Settings",callback_data="adm:settings"),
         InlineKeyboardButton(text="🔧 System",callback_data="adm:system")],
    ])

def content_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo‘shish",callback_data="cnt:add")],
        [InlineKeyboardButton(text="🔎 Kino qidirish",callback_data="cnt:search"),
         InlineKeyboardButton(text="✏️ Tahrirlash",callback_data="cnt:edit")],
        [InlineKeyboardButton(text="🗑 O‘chirish",callback_data="cnt:delete")],
        [InlineKeyboardButton(text="⬅️ Orqaga",callback_data="adm:home")]
    ])

def confirm(action):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha",callback_data=f"confirm:{action}"),
         InlineKeyboardButton(text="❌ Bekor qilish",callback_data="confirm:no")]
    ])

def subscription_keyboard(channels):
    rows=[]
    for c in channels:
        link=c.invite_link or (f"https://t.me/{c.username.lstrip('@')}" if c.username else None)
        if link: rows.append([InlineKeyboardButton(text=f"📢 {c.title or c.username or c.channel_id}",url=link)])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish",callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
