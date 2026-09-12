# Kino Bot — Production Telegram Media Distribution

Production-oriented Telegram kino/video katalogi. Python 3.12+, aiogram 3, PostgreSQL, SQLAlchemy 2, Alembic, Redis and Docker/Railway.

> Faqat tarqatishga huquq berilgan yoki qonuniy foydalanish mumkin bo‘lgan kontent bilan ishlating. Loyiha copyrightni buzishga mo‘ljallangan maxsus mexanizmlarni bermaydi.

## 1. Architecture

```text
Telegram
   │
   ├── Bot Service ── aiogram ── Service ── Repository ── PostgreSQL
   │        │                         │
   │        └──────────────────────── Redis (FSM/cache/rate-limit/queue)
   │
   └── Database Channel
              │
              └── channel_post → whitelist → file_id metadata → admin FSM

Admin Broadcast
   │
   └── Campaign → Redis queue → Worker → Telegram copy_message → delivery analytics
```

Railway tavsiya etiladigan servislar:
- Bot
- Worker
- PostgreSQL
- Redis

Media Railway diskiga yozilmaydi. Telegram `file_id` saqlanadi va keyinchalik Telegramdan qayta yuboriladi.

## 2. Project tree

```text
kino-bot/
├── app/
│   ├── config/
│   ├── database/
│   ├── bot/
│   ├── handlers/
│   ├── services/
│   ├── states.py
│   ├── health.py
│   └── main.py
├── worker/
├── alembic/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── railway.json
├── requirements.txt
├── .env.example
└── README.md
```

## 3. Local requirements

- Python 3.12+
- Docker + Docker Compose
- Telegram bot token
- PostgreSQL
- Redis

## 4. Installation

```bash
git clone <YOUR_REPOSITORY>
cd kino-bot
cp .env.example .env
```

`.env` ichiga token, numeric admin ID va database channel ID yozing.

Local Docker:

```bash
docker compose up --build
```

Bot:
```text
python -m app
```

Worker:
```text
python -m worker
```

Migration:
```bash
alembic upgrade head
```

## 5. BotFather

BotFather orqali bot yarating va tokenni faqat `.env`ga joylashtiring.

Commands:
```text
start - Botni boshlash
help - Yordam
admin - Admin panel
stats - Statistika
kino - Kino ma'lumotlari
ban - User ban
unban - User unban
```

## 6. Database channel

1. Telegram channel yarating.
2. Botni administrator qiling.
3. Botga postlarni ko‘rish va channel post update olish uchun zarur admin huquqlarini bering.
4. Channel ID ni `DATABASE_CHANNEL_IDS`ga yozing.
5. Begona channel postlari qabul qilinmaydi.

Misol:
```env
DATABASE_CHANNEL_IDS=-100123456789,-100987654321
```

Kanalga video kelganda bot Telegram file_id, file_unique_id, channel ID va message ID ni oladi. Fayl serverga yuklanmaydi.

## 7. Admin

Adminlar username bilan emas, numeric Telegram ID bilan aniqlanadi:

```env
ADMIN_IDS=123456789,987654321
```

Productionda qo‘shimcha RBAC jadvallari mavjud: SUPERADMIN, ADMIN, MODERATOR, EDITOR. Initial deploymentda bootstrap authorization `.env` orqali qilinadi.

## 8. Kino qo‘shish

Database channelga media yuboring. Birinchi konfiguratsiyadagi admin xabar oladi.

Keyin:
```text
/admin
→ Kontent
→ Kino qo‘shish
→ Name
→ Genre
→ Country
→ Year
→ Description
→ Confirm
```

Kod 4 xonali random unique integer sifatida generatsiya qilinadi va DB UNIQUE constraint bilan himoyalangan.

## 9. User flow

User:
```text
/start
1258
```

Bot:
1. rate limit
2. ban check
3. required channel check
4. movie lookup
5. active status
6. idempotent download analytics
7. atomic counter increment
8. metadata
9. Telegram `file_id` orqali media

## 10. Counter integrity

`downloads_count = downloads_count + 1` ko‘rinishidagi SQL UPDATE ishlatiladi. Analytics `movie_downloads` jadvalida saqlanadi.

Duplicate Telegram update uchun `update_id` UNIQUE.

## 11. Search

PostgreSQL `pg_trgm` extension va GIN trigram index ishlatiladi. Architecture full-text searchga ham tayyor.

## 12. Required channels

`channels` jadvali:
- channel_id
- username
- title
- invite_link
- active
- required
- is_database

Bot required channelga `getChatMember` orqali tekshiradi.

Bot required channelsda administrator bo‘lishi kerak.

## 13. Broadcast

Broadcast bot handlerida serial loop bilan bajarilmaydi.

```text
Admin
  ↓
Campaign
  ↓
PostgreSQL deliveries
  ↓
Redis queue
  ↓
Worker
  ↓
Telegram copy_message
```

Worker:
- rate limit
- RetryAfter handling
- network retry
- retry attempts
- blocked/deleted users detection
- progress counters
- scheduled campaign polling

Media qayta upload qilinmaydi: campaign source message Telegram `copy_message` bilan nusxalanadi.

## 14. Scheduling

Darhol:
```text
/broadcast
→ message
→ now
```

Scheduled:
```text
2026-09-15T20:00:00+05:00
```

Worker har 5 sekundda scheduled campaignlarni queuega chiqaradi. Redis queue persistent Redis konfiguratsiyasida AOF bilan ishlatiladi.

## 15. Health

```text
GET /health
```

Response:
```json
{
  "application": "OK",
  "database": "OK",
  "redis": "OK"
}
```

Railway healthcheck `/health`ga yo‘naltirilgan.

## 16. Docker

Bot:
```bash
docker compose up bot
```

Worker:
```bash
docker compose up worker
```

Container non-root user bilan ishlaydi.

## 17. Railway deployment

### Step 1 — GitHub
Repository yarating va push qiling.

### Step 2 — Railway
Yangi project yarating.

### Step 3 — PostgreSQL
Railway PostgreSQL service qo‘shing.

### Step 4 — Redis
Railway Redis service qo‘shing.

### Step 5 — Bot service
GitHub repositorydan service yarating. Dockerfile avtomatik ishlaydi.

Bot start command:
```text
alembic upgrade head && python -m app
```

### Step 6 — Worker
Xuddi shu repositorydan ikkinchi service yarating.

Worker start command:
```text
python -m worker
```

### Step 7 — Variables

Kamida:
```env
BOT_TOKEN=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ADMIN_IDS=123456789
DATABASE_CHANNEL_IDS=-100123456789
LOG_LEVEL=INFO
TIMEZONE=Asia/Tashkent
```

Railway variable reference sintaksisi service nomlariga qarab UI orqali tanlanadi; actual generated variable nomini Railway dashboarddan tekshiring.

### Step 8 — Migration

Bot start command migrationni avtomatik ishga tushiradi. Manual:
```bash
alembic upgrade head
```

### Step 9 — Logs

Bot:
```text
railway logs
```

Worker:
```text
railway logs
```

Structured JSON logging ishlatiladi.

## 18. Backup

Railway filesystemni backup repository sifatida ishlatmang.

PostgreSQL backup strategiyasi:
- automated daily logical backup
- haftalik encrypted snapshot
- external object storage
- retention policy
- restore drill

Misol:
```bash
pg_dump "$DATABASE_URL" | gzip > backup.sql.gz
```

Productionda backup faylini alohida encrypted storagega yuboring. Backup ichidagi credentiallarni loglamang.

## 19. Security

- `.env` commit qilinmaydi.
- Secrets source code ichida yo‘q.
- Admin numeric Telegram ID.
- Callback actiondan oldin authorization.
- Redis rate limit.
- DB constraints.
- SQLAlchemy parameterization.
- Soft delete.
- Audit log.
- Error response generic.
- Telegram token logging qilinmaydi.
- Database channel whitelist.

## 20. Scaling

10k+ users uchun:
- PostgreSQL indexed lookup
- Redis cache/rate-limit
- async I/O
- atomic counters
- pagination-ready repositories
- separate broadcast worker
- stateless bot service
- Telegram media references

100k+ scale uchun:
- bot replicas/webhook
- Redis-backed FSM
- PgBouncer
- read replicas for analytics
- dedicated analytics aggregation
- queue sharding
- metrics/observability platform
- external backup/object storage

Broadcast worker horizontal scaling qilinadigan bo‘lsa, delivery row locking/idempotency bilan worker ownershipni kuchaytirish tavsiya qilinadi.

## 21. Tests

```bash
pytest -q
pytest --cov=app
```

Testlar service contracts, configuration, counter operation kabi kritik qismlarni qamrab oladi. Production deploy oldidan PostgreSQL/Redis bilan integration test pipeline qo‘shish tavsiya etiladi.

## 22. Migrations

Yangi migration:
```bash
alembic revision --autogenerate -m "description"
```

Tekshirish:
```bash
alembic upgrade head
```

Rollback:
```bash
alembic downgrade -1
```

## 23. Troubleshooting

### Bot video qabul qilmayapti
- Bot channel admin ekanini tekshiring.
- `DATABASE_CHANNEL_IDS` channel ID bilan aynan mosligini tekshiring.
- Bot update olishini tekshiring.

### Required subscription ishlamayapti
- Bot required channelda admin bo‘lsin.
- channel_id to‘g‘ri bo‘lsin.
- username/invite link valid bo‘lsin.

### Railway DB xatosi
- `DATABASE_URL` mavjudligini tekshiring.
- PostgreSQL service running holatda bo‘lsin.
- migration loglarini tekshiring.

### Broadcast ishlamayapti
- Worker service running.
- `REDIS_URL` bot va workerda bir xil Redisga qaragan.
- queue key `broadcast:queue`.
- Telegram flood limitlarini tekshiring.

## 24. Important operational notes

Telegram `file_id` doimiy server-side file storage o‘rnini bosadigan Telegram media reference sifatida ishlatiladi. Bot media uchun Railway diskiga bog‘lanmaydi.

`file_unique_id` deduplication/reference uchun saqlanadi, media yuborishda `file_id` ishlatiladi.

Admin metadata workflow uchun pending media Redisda vaqtincha saqlanadi. Production multi-admin UXni yanada kuchaytirish uchun pending itemni admin claim qiladigan callback/locking flow qo‘shish mumkin.

Copyrightli kontent faqat tegishli huquq mavjud bo‘lganda tarqatilishi kerak.
