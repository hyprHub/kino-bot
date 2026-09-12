from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table("users",
        sa.Column("id",sa.Integer,primary_key=True),sa.Column("telegram_id",sa.BigInteger,nullable=False,unique=True),
        sa.Column("username",sa.String(255)),sa.Column("first_name",sa.String(255)),sa.Column("last_name",sa.String(255)),
        sa.Column("language",sa.String(10),nullable=False,server_default="uz"),sa.Column("is_active",sa.Boolean,nullable=False,server_default="true"),
        sa.Column("is_banned",sa.Boolean,nullable=False,server_default="false"),sa.Column("joined_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.Column("last_seen_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_users_telegram_id","users",["telegram_id"]); op.create_index("ix_users_is_active","users",["is_active"]); op.create_index("ix_users_is_banned","users",["is_banned"])
    op.create_table("roles",sa.Column("id",sa.Integer,primary_key=True),sa.Column("name",sa.String(50),unique=True,nullable=False))
    op.create_table("permissions",sa.Column("id",sa.Integer,primary_key=True),sa.Column("name",sa.String(100),unique=True,nullable=False))
    op.create_table("role_permissions",sa.Column("role_id",sa.Integer,sa.ForeignKey("roles.id",ondelete="CASCADE"),primary_key=True),sa.Column("permission_id",sa.Integer,sa.ForeignKey("permissions.id",ondelete="CASCADE"),primary_key=True))
    op.create_table("admins",sa.Column("id",sa.Integer,primary_key=True),sa.Column("telegram_id",sa.BigInteger,unique=True,nullable=False),sa.Column("role_id",sa.Integer,sa.ForeignKey("roles.id"),nullable=False),sa.Column("is_active",sa.Boolean,server_default="true"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_admins_telegram_id","admins",["telegram_id"])
    op.create_table("channels",sa.Column("id",sa.Integer,primary_key=True),sa.Column("channel_id",sa.BigInteger,unique=True,nullable=False),sa.Column("username",sa.String(255)),sa.Column("title",sa.String(255)),sa.Column("invite_link",sa.String(1000)),sa.Column("active",sa.Boolean,server_default="true"),sa.Column("required",sa.Boolean,server_default="false"),sa.Column("is_database",sa.Boolean,server_default="false"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_channels_channel_id","channels",["channel_id"]); op.create_index("ix_channels_required","channels",["required"])
    op.create_table("movies",
        sa.Column("id",sa.Integer,primary_key=True),sa.Column("code",sa.Integer,unique=True,nullable=False),sa.Column("name",sa.String(500),nullable=False),
        sa.Column("search_vector",sa.Text),sa.Column("description",sa.Text),sa.Column("genre",sa.String(500)),sa.Column("country",sa.String(255)),sa.Column("release_year",sa.Integer),
        sa.Column("telegram_channel_id",sa.BigInteger,nullable=False),sa.Column("telegram_message_id",sa.BigInteger,nullable=False),
        sa.Column("telegram_file_id",sa.Text,nullable=False),sa.Column("telegram_file_unique_id",sa.String(255),nullable=False),
        sa.Column("media_type",sa.String(30),server_default="video"),sa.Column("downloads_count",sa.BigInteger,server_default="0"),
        sa.Column("status",sa.String(20),server_default="ACTIVE"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_movies_code","movies",["code"]); op.create_index("ix_movies_status","movies",["status"]); op.create_index("ix_movies_downloads_count","movies",["downloads_count"]); op.create_index("ix_movies_file_unique","movies",["telegram_file_unique_id"])
    op.execute("CREATE INDEX ix_movies_name_trgm ON movies USING gin (name gin_trgm_ops)")
    op.create_table("movie_downloads",sa.Column("id",sa.Integer,primary_key=True),sa.Column("movie_id",sa.Integer,sa.ForeignKey("movies.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("downloaded_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("update_id",sa.BigInteger,unique=True))
    op.create_index("ix_downloads_movie_date","movie_downloads",["movie_id","downloaded_at"]); op.create_index("ix_downloads_date","movie_downloads",["downloaded_at"])
    op.create_table("bans",sa.Column("id",sa.Integer,primary_key=True),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id",ondelete="CASCADE"),unique=True),sa.Column("reason",sa.Text),sa.Column("created_by",sa.BigInteger),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("expires_at",sa.DateTime(timezone=True)))
    op.create_table("advertisements",sa.Column("id",sa.Integer,primary_key=True),sa.Column("created_by",sa.BigInteger),sa.Column("source_chat_id",sa.BigInteger),sa.Column("source_message_id",sa.BigInteger),sa.Column("scheduled_at",sa.DateTime(timezone=True)),sa.Column("status",sa.String(30),server_default="DRAFT"),sa.Column("target_count",sa.Integer,server_default="0"),sa.Column("sent_count",sa.Integer,server_default="0"),sa.Column("failed_count",sa.Integer,server_default="0"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_ads_scheduled","advertisements",["scheduled_at"]); op.create_index("ix_ads_status","advertisements",["status"])
    op.create_table("advertisement_deliveries",sa.Column("id",sa.Integer,primary_key=True),sa.Column("campaign_id",sa.Integer,sa.ForeignKey("advertisements.id",ondelete="CASCADE")),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id",ondelete="CASCADE")),sa.Column("status",sa.String(20),server_default="PENDING"),sa.Column("attempts",sa.Integer,server_default="0"),sa.Column("last_error",sa.Text),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("campaign_id","user_id",name="uq_campaign_user"))
    op.create_index("ix_deliveries_status","advertisement_deliveries",["status"])
    op.create_table("settings",sa.Column("key",sa.String(100),primary_key=True),sa.Column("value",postgresql.JSONB,server_default="{}"),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_table("audit_logs",sa.Column("id",sa.Integer,primary_key=True),sa.Column("admin_id",sa.BigInteger,index=True),sa.Column("action",sa.String(100),index=True),sa.Column("target",sa.String(255)),sa.Column("metadata_json",postgresql.JSONB,server_default="{}"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),index=True))
    op.execute("""INSERT INTO roles(name) VALUES ('SUPERADMIN'),('ADMIN'),('MODERATOR'),('EDITOR') ON CONFLICT (name) DO NOTHING""")

def downgrade():
    for t in ["audit_logs","settings","advertisement_deliveries","advertisements","bans","movie_downloads","movies","channels","admins","role_permissions","permissions","roles","users"]:
        op.drop_table(t)
