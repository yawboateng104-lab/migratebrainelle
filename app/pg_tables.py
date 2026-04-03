from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )

    instagram_accounts: Mapped[list["ClientInstagramAccount"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )

    prompt_profiles: Mapped[list["ClientPromptProfile"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=True,
        index=True,
    )
    app_name: Mapped[str] = mapped_column(String(255), nullable=False)
    app_description: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(255), nullable=False)
    posting_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    instagram_handle: Mapped[str] = mapped_column(String(255), nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)
    default_source_image_s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    client: Mapped["Client | None"] = relationship(
        back_populates="campaigns",
    )

    content_ideas: Mapped[list["ContentIdea"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class ClientInstagramAccount(Base):
    __tablename__ = "client_instagram_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    instagram_account_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    facebook_page_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    long_lived_user_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    token_obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    graph_base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://graph.facebook.com/v25.0",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    client: Mapped["Client"] = relationship(
        back_populates="instagram_accounts",
    )


class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pillar: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="content_ideas")
    script: Mapped["Script | None"] = relationship(
        back_populates="content_idea",
        cascade="all, delete-orphan",
        uselist=False,
    )
    video_prompt: Mapped["VideoPrompt | None"] = relationship(
        back_populates="content_idea",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[str] = mapped_column(Text, nullable=False)
    voiceover_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    content_idea: Mapped["ContentIdea"] = relationship(
        back_populates="script",
    )


class VideoPrompt(Base):
    __tablename__ = "video_prompts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    shot_list: Mapped[str] = mapped_column(Text, nullable=False)
    visual_style: Mapped[str] = mapped_column(Text, nullable=False)
    camera_notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    content_idea: Mapped["ContentIdea"] = relationship(
        back_populates="video_prompt",
    )


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_asset_id: Mapped[int] = mapped_column(
        ForeignKey("generated_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    publish_status: Mapped[str] = mapped_column(String(50), nullable=False, default="published")
    caption_used: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class AppEvent(Base):
    __tablename__ = "app_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    feature_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )


class CreativeRequest(Base):
    __tablename__ = "creative_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id"),
        nullable=True,
        index=True,
    )
    content_idea_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_ideas.id"),
        nullable=True,
        index=True,
    )

    request_source: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    content_goal: Mapped[str] = mapped_column(String(100), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_platform: Mapped[str] = mapped_column(String(50), nullable=False, default="instagram")
    generation_mode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_workflow: Mapped[str | None] = mapped_column(String(100), nullable=True)

    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class CreativeMediaInput(Base):
    __tablename__ = "creative_media_inputs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    creative_request_id: Mapped[int] = mapped_column(
        ForeignKey("creative_requests.id"),
        nullable=False,
        index=True,
    )

    media_role: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class ResolvedCreativeSpec(Base):
    __tablename__ = "resolved_creative_specs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    creative_request_id: Mapped[int] = mapped_column(
        ForeignKey("creative_requests.id"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow: Mapped[str] = mapped_column(String(100), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(100), nullable=False)

    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    voiceover_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)

    provider_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="resolved")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class CreativeFeedbackSignal(Base):
    __tablename__ = "creative_feedback_signals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id"),
        nullable=True,
        index=True,
    )
    creative_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("creative_requests.id"),
        nullable=True,
        index=True,
    )

    signal_source: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    structured_signal_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    provider: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    workflow: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)

    default_variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index(
            "ix_prompt_templates_lookup",
            "template_key",
            "provider",
            "workflow",
            "channel",
            "content_type",
            "is_active",
        ),
    )


class ClientPromptProfile(Base):
    __tablename__ = "client_prompt_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    profile_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    provider: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    workflow: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    brand_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    creative_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    client: Mapped["Client"] = relationship(
        back_populates="prompt_profiles",
    )

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "profile_name",
            "provider",
            "workflow",
            "channel",
            "content_type",
            name="uq_client_prompt_profiles_scope",
        ),
        Index(
            "ix_client_prompt_profiles_lookup",
            "client_id",
            "provider",
            "workflow",
            "channel",
            "content_type",
            "is_active",
            "is_default",
        ),
    )
