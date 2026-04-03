"""sync latest schema

Revision ID: 8bac4bcac731
Revises: 69b7891f1f79
Create Date: 2026-03-30 08:34:23.470801

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8bac4bcac731"
down_revision: Union[str, None] = "69b7891f1f79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # New tables
    # ------------------------------------------------------------------
    op.create_table(
        "creative_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("content_idea_id", sa.Integer(), nullable=True),
        sa.Column("request_source", sa.String(length=50), nullable=False),
        sa.Column("content_goal", sa.String(length=100), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("target_platform", sa.String(length=50), nullable=False),
        sa.Column("generation_mode", sa.String(length=100), nullable=True),
        sa.Column("preferred_workflow", sa.String(length=100), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cta", sa.String(length=255), nullable=True),
        sa.Column("tone", sa.String(length=255), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("visual_style", sa.Text(), nullable=True),
        sa.Column("scene_description", sa.Text(), nullable=True),
        sa.Column("extra_instructions", sa.Text(), nullable=True),
        sa.Column("raw_input_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["content_idea_id"], ["content_ideas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_creative_requests_campaign_id"),
        "creative_requests",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_requests_client_id"),
        "creative_requests",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_requests_content_idea_id"),
        "creative_requests",
        ["content_idea_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_requests_id"),
        "creative_requests",
        ["id"],
        unique=False,
    )

    op.create_table(
        "creative_feedback_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("creative_request_id", sa.Integer(), nullable=True),
        sa.Column("signal_source", sa.String(length=100), nullable=False),
        sa.Column("signal_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("priority_score", sa.Float(), nullable=True),
        sa.Column("structured_signal_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["creative_request_id"], ["creative_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_creative_feedback_signals_campaign_id"),
        "creative_feedback_signals",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_feedback_signals_client_id"),
        "creative_feedback_signals",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_feedback_signals_creative_request_id"),
        "creative_feedback_signals",
        ["creative_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_feedback_signals_id"),
        "creative_feedback_signals",
        ["id"],
        unique=False,
    )

    op.create_table(
        "creative_media_inputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creative_request_id", sa.Integer(), nullable=False),
        sa.Column("media_role", sa.String(length=100), nullable=False),
        sa.Column("storage_type", sa.String(length=50), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("media_url", sa.String(length=1000), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creative_request_id"], ["creative_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_creative_media_inputs_creative_request_id"),
        "creative_media_inputs",
        ["creative_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_creative_media_inputs_id"),
        "creative_media_inputs",
        ["id"],
        unique=False,
    )
    op.alter_column("creative_media_inputs", "is_primary", server_default=None)

    op.create_table(
        "resolved_creative_specs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creative_request_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("workflow", sa.String(length=100), nullable=False),
        sa.Column("generation_mode", sa.String(length=100), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("voiceover_script", sa.Text(), nullable=True),
        sa.Column("caption_text", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("provider_payload_json", sa.JSON(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["creative_request_id"], ["creative_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resolved_creative_specs_client_id"),
        "resolved_creative_specs",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resolved_creative_specs_creative_request_id"),
        "resolved_creative_specs",
        ["creative_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resolved_creative_specs_id"),
        "resolved_creative_specs",
        ["id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Existing tables: safe additive changes
    # ------------------------------------------------------------------
    op.add_column(
        "client_instagram_accounts",
        sa.Column("page_name", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "client_instagram_accounts",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("client_instagram_accounts", "is_primary", server_default=None)

    # Only create this if it does not already exist in the DB.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_client_instagram_accounts_id'
            ) THEN
                CREATE INDEX ix_client_instagram_accounts_id
                ON client_instagram_accounts (id);
            END IF;
        END $$;
        """
    )

    # Type alignment with models
    op.alter_column(
        "clients",
        "name",
        existing_type=sa.TEXT(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "clients",
        "telegram_chat_id",
        existing_type=sa.TEXT(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )

    # Only create this if it does not already exist in the DB.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_clients_id'
            ) THEN
                CREATE INDEX ix_clients_id
                ON clients (id);
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # published_posts changes for multi-provider / multi-publish support
    # ------------------------------------------------------------------
    op.drop_constraint(
        "uq_published_posts_generated_asset_id",
        "published_posts",
        type_="unique",
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_published_posts_content_idea_id'
            ) THEN
                CREATE INDEX ix_published_posts_content_idea_id
                ON published_posts (content_idea_id);
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_published_posts_content_idea_id'
            ) THEN
                ALTER TABLE published_posts
                ADD CONSTRAINT fk_published_posts_content_idea_id
                FOREIGN KEY (content_idea_id)
                REFERENCES content_ideas (id)
                ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Roll back published_posts changes
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_published_posts_content_idea_id'
            ) THEN
                ALTER TABLE published_posts
                DROP CONSTRAINT fk_published_posts_content_idea_id;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_published_posts_content_idea_id'
            ) THEN
                DROP INDEX ix_published_posts_content_idea_id;
            END IF;
        END $$;
        """
    )

    op.create_unique_constraint(
        "uq_published_posts_generated_asset_id",
        "published_posts",
        ["generated_asset_id"],
    )

    # ------------------------------------------------------------------
    # Roll back clients / client_instagram_accounts
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_clients_id'
            ) THEN
                DROP INDEX ix_clients_id;
            END IF;
        END $$;
        """
    )

    op.alter_column(
        "clients",
        "telegram_chat_id",
        existing_type=sa.String(length=255),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column(
        "clients",
        "name",
        existing_type=sa.String(length=255),
        type_=sa.TEXT(),
        existing_nullable=False,
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_client_instagram_accounts_id'
            ) THEN
                DROP INDEX ix_client_instagram_accounts_id;
            END IF;
        END $$;
        """
    )

    op.drop_column("client_instagram_accounts", "is_primary")
    op.drop_column("client_instagram_accounts", "page_name")

    # ------------------------------------------------------------------
    # Drop new tables
    # ------------------------------------------------------------------
    op.drop_index(
        op.f("ix_resolved_creative_specs_id"),
        table_name="resolved_creative_specs",
    )
    op.drop_index(
        op.f("ix_resolved_creative_specs_creative_request_id"),
        table_name="resolved_creative_specs",
    )
    op.drop_index(
        op.f("ix_resolved_creative_specs_client_id"),
        table_name="resolved_creative_specs",
    )
    op.drop_table("resolved_creative_specs")

    op.drop_index(
        op.f("ix_creative_media_inputs_id"),
        table_name="creative_media_inputs",
    )
    op.drop_index(
        op.f("ix_creative_media_inputs_creative_request_id"),
        table_name="creative_media_inputs",
    )
    op.drop_table("creative_media_inputs")

    op.drop_index(
        op.f("ix_creative_feedback_signals_id"),
        table_name="creative_feedback_signals",
    )
    op.drop_index(
        op.f("ix_creative_feedback_signals_creative_request_id"),
        table_name="creative_feedback_signals",
    )
    op.drop_index(
        op.f("ix_creative_feedback_signals_client_id"),
        table_name="creative_feedback_signals",
    )
    op.drop_index(
        op.f("ix_creative_feedback_signals_campaign_id"),
        table_name="creative_feedback_signals",
    )
    op.drop_table("creative_feedback_signals")

    op.drop_index(
        op.f("ix_creative_requests_id"),
        table_name="creative_requests",
    )
    op.drop_index(
        op.f("ix_creative_requests_content_idea_id"),
        table_name="creative_requests",
    )
    op.drop_index(
        op.f("ix_creative_requests_client_id"),
        table_name="creative_requests",
    )
    op.drop_index(
        op.f("ix_creative_requests_campaign_id"),
        table_name="creative_requests",
    )
    op.drop_table("creative_requests")
