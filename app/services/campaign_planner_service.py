from app.integrations.openai_client import generate_campaign_bootstrap


def bootstrap_campaign_plan(payload: dict) -> dict:
    return generate_campaign_bootstrap(payload)
