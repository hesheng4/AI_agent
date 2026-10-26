"""add agent_artifacts and share_links

Revision ID: e8a4f2c6b9d1
Revises: b7f2a9c4d1e8
Create Date: 2026-10-26

credibility-convergence v1 步骤 6/7：
- agent_artifacts：Agent 产出物持久化（payload JSON + agent/时间复合索引）
- share_links：通用分享链接（sha256 token 哈希 + TTL + 撤销标记）

SQLite 兼容：纯建表，无 ALTER，不需要 batch 模式，但保持与库内迁移
一致的风格。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8a4f2c6b9d1"
down_revision: str | None = "b7f2a9c4d1e8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("agent", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_artifacts_user_id", "agent_artifacts", ["user_id"])
    op.create_index(
        "ix_artifacts_user_agent_time",
        "agent_artifacts",
        ["user_id", "agent", "created_at"],
    )

    op.create_table(
        "share_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_share_token_hash"),
    )
    op.create_index("ix_share_links_owner_id", "share_links", ["owner_id"])
    op.create_index("ix_share_links_token_hash", "share_links", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_share_links_token_hash", table_name="share_links")
    op.drop_index("ix_share_links_owner_id", table_name="share_links")
    op.drop_table("share_links")
    op.drop_index("ix_artifacts_user_agent_time", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_user_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
