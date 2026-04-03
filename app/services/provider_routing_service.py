PROVIDER_CAPABILITIES = {
    "higgsfield": {
        "generation_modes": ["text_to_image", "image_to_video"],
        "supports_source_image": True,
        "supports_voiceover": False,
        "supports_avatar": False,
    },
    "runway_cinematic": {
        "generation_modes": ["text_to_video", "image_to_video", "voiceover_video"],
        "supports_source_image": True,
        "supports_voiceover": True,
        "supports_avatar": False,
    },
    "heygen_avatar": {
        "generation_modes": ["avatar_video", "text_to_video"],
        "supports_source_image": True,
        "supports_voiceover": True,
        "supports_avatar": True,
    },
}


def choose_provider(
    generation_mode: str | None,
    has_source_image: bool,
    needs_voiceover: bool = False,
    preferred_workflow: str | None = None,
) -> dict:
    if preferred_workflow:
        return {
            "provider": preferred_workflow,
            "workflow": preferred_workflow,
        }

    if generation_mode == "image_to_video" and has_source_image:
        return {"provider": "higgsfield", "workflow": "higgsfield"}

    if generation_mode == "voiceover_video" or needs_voiceover:
        return {"provider": "runway_cinematic", "workflow": "runway_cinematic"}

    if generation_mode == "avatar_video":
        return {"provider": "heygen_avatar", "workflow": "heygen_avatar"}

    if generation_mode == "text_to_image":
        return {"provider": "higgsfield", "workflow": "higgsfield"}

    return {"provider": "runway_cinematic", "workflow": "runway_cinematic"}
