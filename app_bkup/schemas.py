from datetime import datetime
from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    app_name: str = Field(..., min_length=1)
    app_description: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1)
    tone: str = Field(..., min_length=1)
    posting_frequency: int = Field(..., ge=1, le=30)
    instagram_handle: str = Field(..., min_length=1)
    cta: str = Field(..., min_length=1)


class CampaignResponse(BaseModel):
    id: int
    app_name: str
    app_description: str
    audience: str
    tone: str
    posting_frequency: int
    instagram_handle: str
    cta: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentIdeaCreate(BaseModel):
    campaign_id: int
    pillar: str
    title: str
    hook: str
    angle: str
    format: str
    status: str = "draft"


class ContentIdeaResponse(BaseModel):
    id: int
    campaign_id: int
    pillar: str
    title: str
    hook: str
    angle: str
    format: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class ScriptResponse(BaseModel):
    id: int
    content_idea_id: int
    hook: str
    script_text: str
    caption: str
    hashtags: str
    voiceover_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoPromptResponse(BaseModel):
    id: int
    content_idea_id: int
    prompt_text: str
    shot_list: str
    visual_style: str
    camera_notes: str
    created_at: datetime

    model_config = {"from_attributes": True}

class GeneratedAssetResponse(BaseModel):
    id: int
    content_idea_id: int
    provider: str
    asset_url: str
    thumbnail_url: str | None
    asset_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    id: int
    content_idea_id: int
    status: str
    feedback: str | None
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalUpdate(BaseModel):
    status: str
    feedback: str | None = None
    approved_by: str | None = None

class PublishedPostResponse(BaseModel):
    id: int
    content_idea_id: int
    platform: str
    platform_post_id: str
    publish_status: str
    caption_used: str
    published_at: datetime

    model_config = {"from_attributes": True}


class FeatureInsight(BaseModel):
    feature_name: str
    usage_count: int
    trend: str


class MarketingSummaryResponse(BaseModel):
    time_window_days: int
    generated_at: datetime
    app_summary: dict
    top_features: list[FeatureInsight]
    behavior_insights: list[str]
    content_angles: list[str]
    cta_recommendation: str




class GenerateVideoAssetRequest(BaseModel):
    content_idea_id: int = Field(..., example=123)
    prompt_text: str = Field(
        ...,
        example="15-30 second vertical cinematic reel, founder-led energy, soft dramatic lighting, subtle dolly-in, emotionally engaging opening frame, premium brand feel",
    )
    source_image_s3_key: str = Field(
        ...,
        example="image-folder/53eeb85d-acaf-4f26-97b2-a60ef69b35e3.png",
    )


class GenerateVideoAssetResponse(BaseModel):
    id: int
    content_idea_id: int
    asset_type: str
    asset_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CinematicVideoPromptResponse(BaseModel):
    prompt_text: str
    shot_list: str
    visual_style: str
    camera_notes: str
    duration_seconds: int
    opening_frame_description: str
    mood: str
    editing_pace: str
    cta_overlay_text: str | None = None



###schema for pipeline selector workflow whether higg or runway
class PipelineRunRequest(BaseModel):
    workflow: str = Field(
        ...,
        example="runway_cinematic",
    )
    source_image_s3_key: str = Field(
        ...,
        example="image-folder/53eeb85d-acaf-4f26-97b2-a60ef69b35e3.png",
    )


class PipelineRunResponse(BaseModel):
    workflow: str
    content_idea_id: int
    script_id: int
    video_prompt_id: int
    generated_asset_id: int
    published_post_id: int | None = None
    publish_status: str | None = None
    asset_url: str
    caption_used: str
    review_status: str

    model_config = {"from_attributes": True}


class ApproveAndPublishResponse(BaseModel):
    generated_asset_id: int
    content_idea_id: int
    published_post_id: int
    publish_status: str
    asset_url: str
    caption_used: str
    review_status: str

    model_config = {"from_attributes": True}


class RejectAssetResponse(BaseModel):
    generated_asset_id: int
    content_idea_id: int
    review_status: str

    model_config = {"from_attributes": True}
