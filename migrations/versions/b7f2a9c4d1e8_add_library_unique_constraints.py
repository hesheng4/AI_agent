"""add library unique constraints

Revision ID: b7f2a9c4d1e8
Revises: 6ab33371ef5b
Create Date: 2026-08-23

补齐 models 与 baseline 迁移的漂移：paper_collections / paper_categories /
paper_tags 的三个唯一约束（uq_user_paper / uq_user_category_name /
uq_user_tag_name）在 6ab33371ef5b 中缺失，导致走 Alembic 建表的库
可以插入重复收藏 / 重名分类 / 重名标签（create_all 路径则不受影响）。

加约束前先按 (user_id, 业务键) 去重，保留 id 最小的一行，否则存量
重复行会让约束创建失败。SQLite 兼容走 batch 模式。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f2a9c4d1e8"
down_revision: str | None = "6ab33371ef5b"
branch_labels: str | None = None
depends_on: str | None = None

_DEDUP_SQL = {
    "paper_collections": "user_id, paper_id",
    "paper_categories": "user_id, name",
    "paper_tags": "user_id, name",
}


def upgrade() -> None:
    # 存量去重：保留每组 id 最小的一行（MIN(id) 对字符串主键同样有效）
    for table, key in _DEDUP_SQL.items():
        op.execute(
            f"DELETE FROM {table} WHERE id NOT IN "
            f"(SELECT MIN(id) FROM {table} GROUP BY {key})"
        )

    with op.batch_alter_table("paper_collections") as batch:
        batch.create_unique_constraint("uq_user_paper", ["user_id", "paper_id"])
    with op.batch_alter_table("paper_categories") as batch:
        batch.create_unique_constraint("uq_user_category_name", ["user_id", "name"])
    with op.batch_alter_table("paper_tags") as batch:
        batch.create_unique_constraint("uq_user_tag_name", ["user_id", "name"])


def downgrade() -> None:
    with op.batch_alter_table("paper_tags") as batch:
        batch.drop_constraint("uq_user_tag_name", type_="unique")
    with op.batch_alter_table("paper_categories") as batch:
        batch.drop_constraint("uq_user_category_name", type_="unique")
    with op.batch_alter_table("paper_collections") as batch:
        batch.drop_constraint("uq_user_paper", type_="unique")
