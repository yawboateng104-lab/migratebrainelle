"""make published_posts multi-provider

Revision ID: 69b7891f1f79
Revises: 23e4f386d8bc
Create Date: 2026-03-26 05:17:42.162882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "69b7891f1f79"
down_revision: Union[str, None] = "23e4f386d8bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns as nullable first so existing rows do not fail.
    op.add_column(
        "published_posts",
        sa.Column("generated_asset_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "published_posts",
        sa.Column("workflow", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "published_posts",
        sa.Column("provider", sa.String(length=100), nullable=True),
    )

    # Backfill workflow/provider for existing rows.
    op.execute("""
        UPDATE published_posts
        SET workflow = COALESCE(workflow, 'legacy'),
            provider = COALESCE(provider, 'legacy')
        WHERE workflow IS NULL
           OR provider IS NULL
    """)

    # Backfill generated_asset_id using the latest generated asset per content idea.
    op.execute("""
        UPDATE published_posts p
        SET generated_asset_id = ga.id
        FROM (
            SELECT DISTINCT ON (content_idea_id)
                id,
                content_idea_id
            FROM generated_assets
            ORDER BY content_idea_id, id DESC
        ) ga
        WHERE p.content_idea_id = ga.content_idea_id
          AND p.generated_asset_id IS NULL
    """)

    # Drop old "one published post per content idea" uniqueness.
    op.drop_constraint(
        "published_posts_content_idea_id_key",
        "published_posts",
        type_="unique",
    )

    # Add FK/index/unique for generated_asset_id.
    op.create_foreign_key(
        "fk_published_posts_generated_asset_id",
        "published_posts",
        "generated_assets",
        ["generated_asset_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "ix_published_posts_generated_asset_id",
        "published_posts",
        ["generated_asset_id"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_published_posts_generated_asset_id",
        "published_posts",
        ["generated_asset_id"],
    )

    # Now make columns required.
    op.alter_column("published_posts", "generated_asset_id", nullable=False)
    op.alter_column("published_posts", "workflow", nullable=False)
    op.alter_column("published_posts", "provider", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        "uq_published_posts_generated_asset_id",
        "published_posts",
        type_="unique",
    )

    op.drop_index(
        "ix_published_posts_generated_asset_id",
        table_name="published_posts",
    )

    op.drop_constraint(
        "fk_published_posts_generated_asset_id",
        "published_posts",
        type_="foreignkey",
    )

    op.create_unique_constraint(
        "published_posts_content_idea_id_key",
        "published_posts",
        ["content_idea_id"],
    )

    op.drop_column("published_posts", "provider")
    op.drop_column("published_posts", "workflow")
    op.drop_column("published_posts", "generated_asset_id")
