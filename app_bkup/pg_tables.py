from datetime import datetime, UTC
from sqlalchemy import Boolean, String, Integer, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan"
    )

    instagram_accounts: Mapped[list["ClientInstagramAccount"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan"
    )


###Campaign table
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    client: Mapped["Client | None"] = relationship(
        back_populates="campaigns"
    )

    content_ideas: Mapped[list["ContentIdea"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan"
    )


###clinet instagram account table
class ClientInstagramAccount(Base):
    __tablename__ = "client_instagram_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    instagram_account_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    facebook_page_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    graph_base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://graph.facebook.com/v25.0",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    client: Mapped["Client"] = relationship(
        back_populates="instagram_accounts"
    )




##Content ideas table agent table that gets ideas for vids table inside Postgres
class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    pillar: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="content_ideas")
    script: Mapped["Script | None"] = relationship(
        back_populates="content_idea",
        cascade="all, delete-orphan",
        uselist=False
    )
    video_prompt: Mapped["VideoPrompt | None"] = relationship(
        back_populates="content_idea",
        cascade="all, delete-orphan",
        uselist=False
    )


##Scripts Table that generates scripts for agent on what kind of vids table inside Postgres
class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[str] = mapped_column(Text, nullable=False)
    voiceover_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    content_idea: Mapped["ContentIdea"] = relationship(
        back_populates="script"
    )


###Video Prompt Table that generates kind of vids table inside Postgres
class VideoPrompt(Base):
    __tablename__ = "video_prompts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    shot_list: Mapped[str] = mapped_column(Text, nullable=False)
    visual_style: Mapped[str] = mapped_column(Text, nullable=False)
    camera_notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    content_idea: Mapped["ContentIdea"] = relationship(
        back_populates="video_prompt"
    )
##GenerateAsset Table basically assets from posting table inside Postgres for owner video approvals
class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

##Approval Table inside Postgres for owner video apporvals
class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

##Published posts table inside Postgres
class PublishedPost(Base):
    __tablename__ = "published_posts"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_idea_id: Mapped[int] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    generated_asset_id: Mapped[int] = mapped_column(
        ForeignKey("generated_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    workflow: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    publish_status: Mapped[str] = mapped_column(String(50), nullable=False, default="published")
    caption_used: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


##table for app events
class AppEvent(Base):
    __tablename__ = "app_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    feature_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
