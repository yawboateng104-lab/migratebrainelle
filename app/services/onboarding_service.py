from app.pg_tables import Client, Campaign
from app.services.external_analytics_service import build_external_client_snapshot


class OnboardingError(Exception):
    pass


def get_client_onboarding_snapshot(db, client_id: int) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise OnboardingError("Client not found")

    campaigns = (
        db.query(Campaign)
        .filter(Campaign.client_id == client_id)
        .order_by(Campaign.id.asc())
        .all()
    )

    primary_campaign = campaigns[0] if campaigns else None

    payload = {
        "client_id": client.id,
        "business_name": primary_campaign.app_name if primary_campaign else client.name,
        "business_description": primary_campaign.app_description if primary_campaign else "",
        "website_url": None,
        "industry": None,
        "target_audience": primary_campaign.audience if primary_campaign else "",
        "instagram_handle": primary_campaign.instagram_handle if primary_campaign else "",
    }

    external_snapshot = build_external_client_snapshot(payload)

    return {
        "client_id": client.id,
        "business_name": payload["business_name"],
        "onboarding_summary": external_snapshot["onboarding_summary"],
        "content_pillars": external_snapshot["content_pillars"],
        "hook_ideas": external_snapshot["hook_ideas"],
        "tone_recommendation": external_snapshot["tone_recommendation"],
        "visual_recommendation": external_snapshot["visual_recommendation"],
        "music_vibe_suggestion": external_snapshot["music_vibe_suggestion"],
        "posting_opportunities": external_snapshot["posting_opportunities"],
    }


def format_onboarding_welcome_message(snapshot: dict) -> str:
    pillars = "\n".join(f"- {item}" for item in snapshot["content_pillars"])
    hooks = "\n".join(f"- {item}" for item in snapshot["hook_ideas"])
    opportunities = "\n".join(f"- {item}" for item in snapshot["posting_opportunities"])

    return (
        f"👋 Welcome to your AI Content Agent for <b>{snapshot['business_name']}</b>\n\n"
        f"{snapshot['onboarding_summary']}\n\n"
        f"🔥 <b>Recommended Content Pillars</b>\n{pillars}\n\n"
        f"🎯 <b>Hook Ideas</b>\n{hooks}\n\n"
        f"🎨 <b>Tone Recommendation</b>\n{snapshot['tone_recommendation']}\n\n"
        f"🎬 <b>Visual Direction</b>\n{snapshot['visual_recommendation']}\n\n"
        f"🎵 <b>Suggested Music Vibe</b>\n{snapshot['music_vibe_suggestion']}\n\n"
        f"📈 <b>Posting Opportunities</b>\n{opportunities}\n\n"
        f"Choose what to do next:\n"
        f"- type <b>list campaigns</b>\n"
        f"- type <b>higgsfield</b>\n"
        f"- type <b>runway</b>\n"
        f"- type <b>brand snapshot</b>\n"
        f"- type <b>help</b>"
    )


def format_brand_snapshot_message(snapshot: dict) -> str:
    pillars = "\n".join(f"- {item}" for item in snapshot["content_pillars"])
    hooks = "\n".join(f"- {item}" for item in snapshot["hook_ideas"])

    return (
        f"🏷️ <b>Brand Snapshot for {snapshot['business_name']}</b>\n\n"
        f"{snapshot['onboarding_summary']}\n\n"
        f"🔥 <b>Content Pillars</b>\n{pillars}\n\n"
        f"🎯 <b>Hook Ideas</b>\n{hooks}\n\n"
        f"🎨 <b>Tone</b>\n{snapshot['tone_recommendation']}\n\n"
        f"🎬 <b>Visual Style</b>\n{snapshot['visual_recommendation']}\n\n"
        f"🎵 <b>Music Vibe</b>\n{snapshot['music_vibe_suggestion']}"
    )
