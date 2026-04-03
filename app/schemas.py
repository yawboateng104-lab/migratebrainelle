from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any



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
        example="Luxury modern high-rise office with panoramic skyline, confident female founder, cinematic corporate lighting, photorealistic premium brand aesthetic",
    )
    generation_mode: Optional[str] = Field(
        default="image_to_video",
        example="text_to_image",
    )
    source_image_s3_key: Optional[str] = Field(
        default=None,
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
        example="higgsfield",
    )
    source_image_s3_key: Optional[str] = Field(
        default=None,
        example="image-folder/53eeb85d-acaf-4f26-97b2-a60ef69b35e3.png",
    )
    generation_mode: Optional[str] = Field(
        default=None,
        example="text_to_image",
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
    asset_type: str
    generation_mode: str
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


##new 3/30

class CreativeMediaInputCreate(BaseModel):
    media_role: str
    storage_type: str
    storage_key: Optional[str] = None
    media_url: Optional[str] = None
    mime_type: Optional[str] = None
    is_primary: bool = False


class CreativeRequestCreate(BaseModel):
    client_id: int
    campaign_id: Optional[int] = None
    content_idea_id: Optional[int] = None

    request_source: str = "api"
    content_goal: str
    content_type: str
    target_platform: str = "instagram"
    generation_mode: Optional[str] = None
    preferred_workflow: Optional[str] = None

    topic: Optional[str] = None
    hook: Optional[str] = None
    angle: Optional[str] = None
    description: Optional[str] = None
    cta: Optional[str] = None
    tone: Optional[str] = None
    audience: Optional[str] = None
    visual_style: Optional[str] = None
    scene_description: Optional[str] = None
    extra_instructions: Optional[str] = None

    raw_input_json: Optional[Dict[str, Any]] = None
    media_inputs: List[CreativeMediaInputCreate] = []


class CreativeRequestResponse(BaseModel):
    id: int
    status: str

    class Config:
        from_attributes = True


class CreativeFeedbackSignalCreate(BaseModel):
    client_id: int
    campaign_id: Optional[int] = None
    creative_request_id: Optional[int] = None

    signal_source: str
    signal_type: str
    title: str
    summary: Optional[str] = None
    recommendation: Optional[str] = None
    priority_score: Optional[float] = None
    structured_signal_json: Optional[Dict[str, Any]] = None


class CampaignBootstrapRequest(BaseModel):
    client_id: int
    business_name: str
    business_description: str
    audience: str
    tone: str
    cta: Optional[str] = None
    offer: Optional[str] = None
    posting_frequency: Optional[int] = 3



class ClientMetaConnectCreate(BaseModel):
    client_id: int
    facebook_page_id: Optional[str] = None
    page_name: Optional[str] = None
    instagram_account_id: Optional[str] = None
    instagram_username: Optional[str] = None

    access_token: str
    long_lived_user_token: Optional[str] = None

    token_expires_at: Optional[str] = None
    graph_base_url: Optional[str] = "https://graph.facebook.com/v25.0"

    status: Optional[str] = "active"




class DirectorShotInput(BaseModel):
    shot_name: str
    description: str
    camera_move: Optional[str] = None
    duration_seconds: Optional[int] = None
    transition_style: Optional[str] = None


class DirectorBriefCreate(BaseModel):
    client_id: int
    campaign_id: Optional[int] = None
    content_idea_id: Optional[int] = None

    content_goal: str
    content_type: str
    target_platform: str = "instagram"
    generation_mode: Optional[str] = None
    preferred_workflow: Optional[str] = None

    topic: Optional[str] = None
    hook: Optional[str] = None
    angle: Optional[str] = None
    description: Optional[str] = None
    cta: Optional[str] = None
    tone: Optional[str] = None
    audience: Optional[str] = None

    visual_style: Optional[str] = None
    environment_style: Optional[str] = None
    lighting_style: Optional[str] = None
    camera_style: Optional[str] = None
    motion_intensity: Optional[str] = None

    preserve_environment: Optional[bool] = True
    preserve_identity: Optional[bool] = True
    use_source_image_strongly: Optional[bool] = True

    voiceover_required: Optional[bool] = False
    short_form_hook_priority: Optional[bool] = True
    safe_text_overlay_regions: Optional[bool] = True

    direction_notes: Optional[str] = None
    negative_direction: Optional[str] = None

    requested_shots: List[DirectorShotInput] = []
    media_inputs: List["CreativeMediaInputCreate"] = []


class VideoEditShotUpdate(BaseModel):
    shot_number: int
    shot_name: Optional[str] = None
    description: Optional[str] = None
    camera_move: Optional[str] = None
    duration_seconds: Optional[int] = None
    transition_style: Optional[str] = None


class VideoEditRequestCreate(BaseModel):
    creative_request_id: int
    edit_goal: Optional[str] = "revise_video"

    regenerate_workflow: Optional[str] = None
    keep_source_image: Optional[bool] = True
    keep_voiceover: Optional[bool] = True
    keep_caption: Optional[bool] = True

    edit_notes: Optional[str] = None
    change_hook: Optional[str] = None
    change_cta: Optional[str] = None
    change_tone: Optional[str] = None
    change_visual_style: Optional[str] = None
    change_environment_style: Optional[str] = None
    change_lighting_style: Optional[str] = None
    change_camera_style: Optional[str] = None
    change_motion_intensity: Optional[str] = None

    add_music: Optional[bool] = False
    music_mode: Optional[str] = None  # internal_library, manual_instagram, none
    music_track_name: Optional[str] = None
    music_mood: Optional[str] = None
    music_notes: Optional[str] = None

    replacement_media_inputs: List["CreativeMediaInputCreate"] = []
    shot_updates: List[VideoEditShotUpdate] = []


DirectorBriefCreate.model_rebuild()
VideoEditRequestCreate.model_rebuild()


from typing import Optional, List
from pydantic import BaseModel


class ExternalAnalyticsOnboardingRequest(BaseModel):
    client_id: int
    business_name: str
    business_description: Optional[str] = None
    website_url: Optional[str] = None
    industry: Optional[str] = None
    target_audience: Optional[str] = None
    instagram_handle: Optional[str] = None


class ClientOnboardingResponse(BaseModel):
    client_id: int
    business_name: str
    onboarding_summary: str
    content_pillars: List[str]
    hook_ideas: List[str]
    tone_recommendation: str
    visual_recommendation: str
