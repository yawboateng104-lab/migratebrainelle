from __future__ import annotations

from app.pg_tables import (
    Campaign,
    Client,
    ClientPromptProfile,
    ContentIdea,
    GeneratedAsset,
)
from app.schemas import (
    CreativeMediaInputCreate,
    CreativeRequestCreate,
    VideoEditRequestCreate,
)
from app.services.insights_service import build_marketing_summary
from app.services.onboarding_service import (
    format_brand_snapshot_message,
    format_onboarding_welcome_message,
    get_client_onboarding_snapshot,
)
from app.services.openclaw_service import OpenClawError, interpret_user_command
from app.services.pipeline_execution_service import run_creative_request_through_existing_pipeline
from app.services.prompt_intake_service import intake_and_resolve_creative_request
from app.services.review_service import (
    ReviewError,
    approve_and_publish_generated_asset,
    reject_generated_asset,
)
from app.services.telegram_context_service import (
    TelegramContextError,
    get_generation_context_for_chat,
    link_telegram_chat_to_client,
)
from app.services.telegram_runtime import (
    get_active_campaign,
    get_pending_asset_id,
    is_chat_busy,
    set_active_campaign,
    set_pending_asset_id,
    start_chat_job,
)
from app.services.video_edit_service import create_edit_revision_from_creative_request


_PENDING_EDIT_REQUESTS: dict[int | str, int] = {}
_ONE_TIME_PROMPT_OVERRIDES: dict[int | str, str] = {}
_PENDING_DIRECT_PROMPTS: dict[int | str, dict] = {}
_PENDING_WORKFLOW_OPTIONS: dict[int | str, dict] = {}


WORKFLOW_CONFIG = {
    "runway_cinematic": {
        "provider": "runway_cinematic",
        "display_name": "Runway",
        "profile_name": "telegram_runway_style",
        "template_prefix": "runway",
        "default_generation_mode": "image_to_video",
    },
    "higgsfield": {
        "provider": "higgsfield",
        "display_name": "Higgsfield",
        "profile_name": "telegram_higgsfield_style",
        "template_prefix": "higgsfield",
        "default_generation_mode": "text_to_image",
    },
}


PROMPT_MODE_CONFIG = {
    "managed": {
        "resolution_mode": "full_openai",
        "source": "telegram_managed",
        "label": "managed",
    },
    "guided": {
        "resolution_mode": "light_openai",
        "source": "telegram_guided",
        "label": "guided",
    },
    "exact": {
        "resolution_mode": "no_openai",
        "source": "telegram_exact",
        "label": "exact",
    },
}


class TelegramAgentError(Exception):
    pass


def _get_default_generation_mode(workflow: str) -> str:
    return WORKFLOW_CONFIG[workflow]["default_generation_mode"]


def handle_telegram_command(text: str, db, chat_id: int | str | None = None):
    normalized_text = (text or "").strip().lower()

    if not normalized_text:
        return {
            "mode": "instant",
            "message": "🤖 Please send a command.",
        }

    if chat_id is not None and chat_id in _PENDING_EDIT_REQUESTS:
        return _handle_edit_followup(chat_id=chat_id, text=text, db=db)

    if normalized_text in {"start", "/start", "help"}:
        return {
            "mode": "instant",
            "message": (
                "🤖 Welcome to Brainelle AI.\n\n"
                "Try:\n"
                "- link client 1\n"
                "- list campaigns\n"
                "- use campaign 2\n"
                "- brand snapshot\n"
                "- runway\n"
                "- higgsfield\n"
                "- higgsfield image\n"
                "- runway guided: <your prompt>\n"
                "- runway exact: <your prompt>\n"
                "- higgsfield guided: <your prompt>\n"
                "- higgsfield exact: <your prompt>\n"
                "- higgsfield image guided: <your prompt>\n"
                "- higgsfield image exact: <your prompt>\n"
                "- for this one <extra instruction>\n"
                "- set runway style <style>\n"
                "- set higgsfield style <style>\n"
                "- save runway guided template <name>: <prompt>\n"
                "- save runway exact template <name>: <prompt>\n"
                "- save higgsfield image guided template <name>: <prompt>\n"
                "- save higgsfield image exact template <name>: <prompt>\n"
                "- runway guided template <name>\n"
                "- runway exact template <name>\n"
                "- higgsfield image guided template <name>\n"
                "- higgsfield image exact template <name>\n"
                "- show runway templates\n"
                "- show higgsfield templates\n"
                "- show runway style\n"
                "- show higgsfield style\n"
                "- clear one-time prompt\n"
                "- insights"
            ),
        }

    if normalized_text.startswith("link client"):
        client_id = _extract_id(normalized_text)
        if not chat_id:
            return {
                "mode": "instant",
                "message": "❌ Chat ID is required.",
            }
        if not client_id:
            return {
                "mode": "instant",
                "message": "❌ Client ID required. Example: link client 1",
            }

        try:
            result = link_telegram_chat_to_client(chat_id=chat_id, client_id=client_id, db=db)
            snapshot = get_client_onboarding_snapshot(db=db, client_id=client_id)
        except TelegramContextError:
            return {
                "mode": "instant",
                "message": "❌ Client is not available for this Telegram chat.",
            }
        except Exception:
            return {
                "mode": "instant",
                "message": "❌ Client is not available for this Telegram chat.",
            }

        welcome_message = format_onboarding_welcome_message(snapshot)

        return {
            "mode": "instant",
            "message": (
                f"🔗 Telegram linked successfully\n"
                f"Client ID: {result['client_id']}\n"
                f"Chat ID: {result['telegram_chat_id']}\n\n"
                f"{welcome_message}"
            ),
        }

    if "brand snapshot" in normalized_text:
        if not chat_id:
            return {
                "mode": "instant",
                "message": "❌ Chat ID is required.",
            }

        client = db.query(Client).filter(Client.telegram_chat_id == str(chat_id)).first()
        if not client:
            return {
                "mode": "instant",
                "message": "❌ No client is linked to this Telegram chat yet. Use: link client 1",
            }

        try:
            snapshot = get_client_onboarding_snapshot(db=db, client_id=client.id)
        except Exception as exc:
            return {
                "mode": "instant",
                "message": f"❌ Failed to build brand snapshot: {exc}",
            }

        return {
            "mode": "instant",
            "message": format_brand_snapshot_message(snapshot),
        }

    if "list campaigns" in normalized_text:
        if not chat_id:
            return {
                "mode": "instant",
                "message": "❌ Chat ID is required.",
            }

        client = db.query(Client).filter(Client.telegram_chat_id == str(chat_id)).first()
        if not client:
            return {
                "mode": "instant",
                "message": "❌ No client is linked to this Telegram chat yet. Use: link client 1",
            }

        campaigns = (
            db.query(Campaign)
            .filter(Campaign.client_id == client.id)
            .order_by(Campaign.id.asc())
            .all()
        )

        if not campaigns:
            return {
                "mode": "instant",
                "message": "❌ No campaigns found for this client.",
            }

        active_campaign_id = get_active_campaign(chat_id)

        msg = "📋 Your Campaigns:\n\n"
        for campaign in campaigns:
            marker = " ✅ ACTIVE" if active_campaign_id == campaign.id else ""
            msg += f"- ID: {campaign.id} | {campaign.app_name}{marker}\n"

        msg += "\nUse: use campaign <id>"

        return {
            "mode": "instant",
            "message": msg,
        }

    if "use campaign" in normalized_text:
        campaign_id = _extract_id(normalized_text)
        if not campaign_id:
            return {
                "mode": "instant",
                "message": "❌ Please provide campaign id. Example: use campaign 2",
            }

        if not chat_id:
            return {
                "mode": "instant",
                "message": "❌ Chat ID is required.",
            }

        client = db.query(Client).filter(Client.telegram_chat_id == str(chat_id)).first()
        if not client:
            return {
                "mode": "instant",
                "message": "❌ No client is linked to this Telegram chat yet. Use: link client 1",
            }

        campaign = (
            db.query(Campaign)
            .filter(
                Campaign.id == campaign_id,
                Campaign.client_id == client.id,
            )
            .first()
        )
        if not campaign:
            return {
                "mode": "instant",
                "message": "❌ That campaign is not available for this Telegram-linked client.",
            }

        set_active_campaign(chat_id, campaign_id)

        return {
            "mode": "instant",
            "message": f"✅ Now using campaign {campaign_id} ({campaign.app_name})",
        }

    if normalized_text.startswith("for this one"):
        if not chat_id:
            return {
                "mode": "instant",
                "message": "❌ Chat ID is required.",
            }

        override_text = text[len("for this one") :].strip()
        if not override_text:
            return {
                "mode": "instant",
                "message": "❌ Please include the custom text after 'for this one'.",
            }

        _ONE_TIME_PROMPT_OVERRIDES[chat_id] = override_text
        return {
            "mode": "instant",
            "message": (
                "🧠 One-time override saved for the next generation:\n\n"
                f"{override_text}\n\n"
                "Now run your workflow."
            ),
        }

    if normalized_text == "clear one-time prompt":
        if not chat_id:
            return {
                "mode": "instant",
                "message": "❌ Chat ID is required.",
            }

        _ONE_TIME_PROMPT_OVERRIDES.pop(chat_id, None)
        return {
            "mode": "instant",
            "message": "🧹 Cleared the one-time prompt override for this chat.",
        }

    if normalized_text.startswith("save runway guided template "):
        return _save_named_template_command(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            prompt_mode_key="guided",
            command_text=text,
            prefix="save runway guided template ",
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("save runway exact template "):
        return _save_named_template_command(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            prompt_mode_key="exact",
            command_text=text,
            prefix="save runway exact template ",
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("save higgsfield guided template "):
        return _save_named_template_command(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_mode_key="guided",
            command_text=text,
            prefix="save higgsfield guided template ",
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("save higgsfield exact template "):
        return _save_named_template_command(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_mode_key="exact",
            command_text=text,
            prefix="save higgsfield exact template ",
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("save higgsfield image guided template "):
        return _save_named_template_command(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_mode_key="guided",
            command_text=text,
            prefix="save higgsfield image guided template ",
            generation_mode="text_to_image",
        )

    if normalized_text.startswith("save higgsfield image exact template "):
        return _save_named_template_command(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_mode_key="exact",
            command_text=text,
            prefix="save higgsfield image exact template ",
            generation_mode="text_to_image",
        )

    if normalized_text == "show runway templates":
        return _show_named_templates(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
        )

    if normalized_text == "show higgsfield templates":
        return _show_named_templates(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
        )

    if normalized_text.startswith("delete runway template "):
        template_name = text[len("delete runway template ") :].strip()
        return _delete_named_template(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            template_name=template_name,
        )

    if normalized_text.startswith("delete higgsfield template "):
        template_name = text[len("delete higgsfield template ") :].strip()
        return _delete_named_template(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            template_name=template_name,
        )

    if normalized_text.startswith("runway guided template "):
        template_name = text[len("runway guided template ") :].strip()
        return _run_saved_template(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            default_prompt_mode_key="guided",
            template_name=template_name,
        )

    if normalized_text.startswith("runway exact template "):
        template_name = text[len("runway exact template ") :].strip()
        return _run_saved_template(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            default_prompt_mode_key="exact",
            template_name=template_name,
        )

    if normalized_text.startswith("higgsfield guided template "):
        template_name = text[len("higgsfield guided template ") :].strip()
        return _run_saved_template(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            default_prompt_mode_key="guided",
            template_name=template_name,
        )

    if normalized_text.startswith("higgsfield exact template "):
        template_name = text[len("higgsfield exact template ") :].strip()
        return _run_saved_template(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            default_prompt_mode_key="exact",
            template_name=template_name,
        )

    if normalized_text.startswith("higgsfield image guided template "):
        template_name = text[len("higgsfield image guided template ") :].strip()
        return _run_saved_template(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            default_prompt_mode_key="guided",
            template_name=template_name,
        )

    if normalized_text.startswith("higgsfield image exact template "):
        template_name = text[len("higgsfield image exact template ") :].strip()
        return _run_saved_template(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            default_prompt_mode_key="exact",
            template_name=template_name,
        )

    if normalized_text.startswith("set runway style"):
        return _save_workflow_style(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            style_text=text[len("set runway style") :].strip(),
        )

    if normalized_text.startswith("set higgsfield style"):
        return _save_workflow_style(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            style_text=text[len("set higgsfield style") :].strip(),
        )

    if normalized_text == "show runway style":
        return _show_workflow_style(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
        )

    if normalized_text == "show higgsfield style":
        return _show_workflow_style(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
        )

    if normalized_text == "clear runway style":
        return _clear_workflow_style(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
        )

    if normalized_text == "clear higgsfield style":
        return _clear_workflow_style(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
        )

    if normalized_text.startswith("runway guided:"):
        direct_prompt = text.split(":", 1)[1].strip()
        return _queue_direct_prompt_generation(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            prompt_text=direct_prompt,
            prompt_mode_key="guided",
            template_name=None,
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("runway exact:"):
        direct_prompt = text.split(":", 1)[1].strip()
        return _queue_direct_prompt_generation(
            db=db,
            chat_id=chat_id,
            workflow="runway_cinematic",
            prompt_text=direct_prompt,
            prompt_mode_key="exact",
            template_name=None,
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("higgsfield image guided:"):
        direct_prompt = text.split(":", 1)[1].strip()
        return _queue_direct_prompt_generation(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_text=direct_prompt,
            prompt_mode_key="guided",
            template_name=None,
            generation_mode="text_to_image",
        )

    if normalized_text.startswith("higgsfield image exact:"):
        direct_prompt = text.split(":", 1)[1].strip()
        return _queue_direct_prompt_generation(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_text=direct_prompt,
            prompt_mode_key="exact",
            template_name=None,
            generation_mode="text_to_image",
        )

    if normalized_text.startswith("higgsfield guided:"):
        direct_prompt = text.split(":", 1)[1].strip()
        return _queue_direct_prompt_generation(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_text=direct_prompt,
            prompt_mode_key="guided",
            template_name=None,
            generation_mode="image_to_video",
        )

    if normalized_text.startswith("higgsfield exact:"):
        direct_prompt = text.split(":", 1)[1].strip()
        return _queue_direct_prompt_generation(
            db=db,
            chat_id=chat_id,
            workflow="higgsfield",
            prompt_text=direct_prompt,
            prompt_mode_key="exact",
            template_name=None,
            generation_mode="image_to_video",
        )

    if normalized_text == "runway":
        return _deferred_request(
            chat_id,
            "runway_cinematic",
            db,
            generation_mode=_get_default_generation_mode("runway_cinematic"),
        )

    if normalized_text == "higgsfield":
        return _deferred_request(
            chat_id,
            "higgsfield",
            db,
            generation_mode=_get_default_generation_mode("higgsfield"),
        )

    if normalized_text == "higgsfield image":
        return _deferred_request(chat_id, "higgsfield", db, generation_mode="text_to_image")

    if normalized_text.startswith("approve"):
        asset_id = _extract_id(normalized_text)
        if not asset_id and chat_id is not None:
            asset_id = get_pending_asset_id(chat_id)

        return {
            "mode": "instant",
            "message": _approve(asset_id, db),
        }

    if normalized_text.startswith("reject"):
        asset_id = _extract_id(normalized_text)
        if not asset_id and chat_id is not None:
            asset_id = get_pending_asset_id(chat_id)

        return {
            "mode": "instant",
            "message": _reject(asset_id, db),
        }

    if "insights" in normalized_text or "analytics" in normalized_text:
        return {
            "mode": "instant",
            "message": _insights(db),
        }

    try:
        ai_result = interpret_user_command(text)
        action = ai_result.get("action")
        asset_id = ai_result.get("asset_id")

        if action == "runway":
            return _deferred_request(
                chat_id,
                "runway_cinematic",
                db,
                generation_mode=_get_default_generation_mode("runway_cinematic"),
            )

        if action == "higgsfield":
            return _deferred_request(
                chat_id,
                "higgsfield",
                db,
                generation_mode=_get_default_generation_mode("higgsfield"),
            )

        if action == "approve":
            if not asset_id and chat_id is not None:
                asset_id = get_pending_asset_id(chat_id)

            return {
                "mode": "instant",
                "message": _approve(asset_id, db),
            }

        if action == "reject":
            if not asset_id and chat_id is not None:
                asset_id = get_pending_asset_id(chat_id)

            return {
                "mode": "instant",
                "message": _reject(asset_id, db),
            }

        if action == "insights":
            return {
                "mode": "instant",
                "message": _insights(db),
            }

    except (
        OpenClawError,
        TelegramAgentError,
        ReviewError,
        TelegramContextError,
    ) as exc:
        print(f"[TELEGRAM FALLBACK ERROR] {exc}")

    return {
        "mode": "instant",
        "message": (
            "🤖 I didn’t understand.\n"
            "Try:\n"
            "- link client 1\n"
            "- brand snapshot\n"
            "- list campaigns\n"
            "- use campaign 2\n"
            "- runway\n"
            "- higgsfield\n"
            "- higgsfield image\n"
            "- runway guided: <your prompt>\n"
            "- runway exact: <your prompt>\n"
            "- higgsfield guided: <your prompt>\n"
            "- higgsfield exact: <your prompt>\n"
            "- higgsfield image guided: <your prompt>\n"
            "- higgsfield image exact: <your prompt>\n"
            "- save higgsfield image guided template <name>: <prompt>\n"
            "- save higgsfield image exact template <name>: <prompt>\n"
            "- higgsfield image guided template <name>\n"
            "- higgsfield image exact template <name>\n"
            "- show higgsfield templates\n"
            "- approve 16\n"
            "- reject 16\n"
            "- insights"
        ),
    }


def run_deferred_workflow(workflow: str, db, chat_id: int | str):
    workflow_options = _PENDING_WORKFLOW_OPTIONS.pop(chat_id, {})
    generation_mode = workflow_options.get("generation_mode") or WORKFLOW_CONFIG[workflow]["default_generation_mode"]

    context = get_generation_context_for_chat(chat_id=chat_id, db=db)

    creative_request = _create_telegram_creative_request(
        db=db,
        workflow=workflow,
        context=context,
        chat_id=chat_id,
        generation_mode=generation_mode,
    )

    execution_result = run_creative_request_through_existing_pipeline(
        db=db,
        creative_request_id=creative_request.id,
    )

    pipeline_result = execution_result["pipeline_result"]
    asset_id = pipeline_result["generated_asset_id"]
    asset_type = pipeline_result.get("asset_type") or "video"

    set_pending_asset_id(chat_id, asset_id)

    reply_markup = _build_review_reply_markup(
        asset_id=asset_id,
        creative_request_id=creative_request.id,
    )

    message = _build_draft_review_message(
        workflow=workflow,
        client_id=context["client_id"],
        campaign_id=context["campaign_id"],
        asset_id=asset_id,
        review_status=pipeline_result["review_status"],
        asset_url=pipeline_result["asset_url"],
        caption_used=pipeline_result["caption_used"],
        creative_request_id=creative_request.id,
    )

    response = {
        "message": message,
        "reply_markup": reply_markup,
        "asset_type": asset_type,
    }

    if asset_type == "image":
        response["image_url"] = pipeline_result["asset_url"]
    else:
        response["video_url"] = pipeline_result["asset_url"]

    return response


def handle_callback_action(
    action: str,
    asset_id: int | None,
    db,
    creative_request_id: int | None = None,
    chat_id: int | str | None = None,
):
    if action == "approve":
        return _approve(asset_id, db)

    if action == "reject":
        return _reject(asset_id, db)

    if action == "manual_post":
        return _manual_post(asset_id, db)

    if action == "edit":
        if not creative_request_id:
            raise TelegramAgentError("Creative request ID required for edit")

        if chat_id is not None:
            _PENDING_EDIT_REQUESTS[chat_id] = creative_request_id

        return {
            "mode": "instant",
            "message": (
                "✏️ What would you like to change?\n\n"
                "Examples:\n"
                "- change the lighting\n"
                "- make the pacing faster\n"
                "- update the background\n"
                "- make the opening stronger"
            ),
        }

    raise TelegramAgentError("Unsupported callback action")


def _queue_direct_prompt_generation(
    db,
    chat_id: int | str | None,
    workflow: str,
    prompt_text: str,
    prompt_mode_key: str,
    template_name: str | None,
    generation_mode: str,
):
    if not chat_id:
        return {
            "mode": "instant",
            "message": "❌ Chat ID is required.",
        }

    if not prompt_text:
        return {
            "mode": "instant",
            "message": "❌ Please include the prompt text after the workflow command.",
        }

    try:
        get_generation_context_for_chat(chat_id=chat_id, db=db)
    except TelegramContextError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    mode_config = PROMPT_MODE_CONFIG[prompt_mode_key]

    _PENDING_DIRECT_PROMPTS[chat_id] = {
        "prompt_text": prompt_text,
        "prompt_mode_key": prompt_mode_key,
        "prompt_source": mode_config["source"],
        "template_name": template_name,
        "prompt_resolution_mode": mode_config["resolution_mode"],
        "generation_mode": generation_mode,
    }

    provider_name = WORKFLOW_CONFIG[workflow]["display_name"]
    mode_label = mode_config["label"]
    mode_suffix = " image" if generation_mode == "text_to_image" else ""

    return {
        "mode": "instant",
        "message": (
            f"🧾 {provider_name}{mode_suffix} {mode_label} prompt saved for next generation:\n\n"
            f"{prompt_text}\n\n"
            f"Now run {WORKFLOW_CONFIG[workflow]['template_prefix']}{' image' if generation_mode == 'text_to_image' else ''}."
        ),
    }


def _deferred_request(chat_id: int | str | None, workflow: str, db, generation_mode: str):
    if chat_id is None:
        return {
            "mode": "instant",
            "message": "❌ Chat ID is required for deferred workflow.",
        }

    try:
        get_generation_context_for_chat(chat_id=chat_id, db=db)
    except TelegramContextError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    if is_chat_busy(chat_id):
        return {
            "mode": "instant",
            "message": (
                "⏳ I’m already working on a draft for this chat.\n"
                "Please wait for the current one to finish before starting another."
            ),
        }

    _PENDING_WORKFLOW_OPTIONS[chat_id] = {
        "generation_mode": generation_mode,
    }

    started = start_chat_job(chat_id, workflow)
    if not started:
        return {
            "mode": "instant",
            "message": (
                "⏳ I’m already working on a draft for this chat.\n"
                "Please wait for the current one to finish before starting another."
            ),
        }

    provider_name = WORKFLOW_CONFIG[workflow]["display_name"]
    asset_label = "image draft" if generation_mode == "text_to_image" else "draft"

    return {
        "mode": "deferred",
        "workflow": workflow,
        "ack_message": (
            f"🎬 Got it — generating your {provider_name} {asset_label} now.\n"
            f"I’ll send the preview here as soon as it’s ready."
        ),
    }


def _approve(asset_id: int | None, db):
    if not asset_id:
        raise TelegramAgentError("Asset ID required for approve command")

    try:
        result = approve_and_publish_generated_asset(asset_id, db)
    except ReviewError as exc:
        raise TelegramAgentError(str(exc)) from exc

    return (
        f"🚀 Published successfully!\n"
        f"Asset ID: {result['generated_asset_id']}\n"
        f"Published Post ID: {result['published_post_id']}\n"
        f"Publish Status: {result['publish_status']}"
    )


def _manual_post(asset_id: int | None, db):
    if not asset_id:
        raise TelegramAgentError("Asset ID required for manual_post command")

    generated_asset = (
        db.query(GeneratedAsset)
        .filter(GeneratedAsset.id == asset_id)
        .first()
    )
    if not generated_asset:
        raise TelegramAgentError(f"Generated asset {asset_id} not found")

    if hasattr(generated_asset, "status"):
        generated_asset.status = "ready_for_operator_handoff"
        db.add(generated_asset)

    content_idea = (
        db.query(ContentIdea)
        .filter(ContentIdea.id == generated_asset.content_idea_id)
        .first()
    )
    if content_idea:
        if hasattr(content_idea, "review_status"):
            content_idea.review_status = "approved"
        if hasattr(content_idea, "publish_status"):
            content_idea.publish_status = "ready_for_operator_handoff"
        db.add(content_idea)

    db.commit()

    return (
        "Approved — your content is ready for the final music and posting step.\n\n"
        "Our team has been notified to finish audio selection and complete the manual "
        "posting process. We’ll follow up once your post has been published."
    )


def _reject(asset_id: int | None, db):
    if not asset_id:
        raise TelegramAgentError("Asset ID required for reject command")

    try:
        result = reject_generated_asset(asset_id, db)
    except ReviewError as exc:
        raise TelegramAgentError(str(exc)) from exc

    return (
        f"❌ Draft rejected\n"
        f"Asset ID: {result['generated_asset_id']}\n"
        f"Review Status: {result['review_status']}"
    )


def _insights(db):
    result = build_marketing_summary(db=db)

    highlights = "\n".join(f"- {item}" for item in result["highlights"])
    recommendations = "\n".join(f"- {item}" for item in result["recommendations"])

    return (
        f"📊 Summary:\n{result['summary']}\n\n"
        f"🔥 Highlights:\n{highlights}\n\n"
        f"💡 Recommendations:\n{recommendations}"
    )


def _extract_id(text: str) -> int | None:
    for part in text.replace(":", " ").split():
        if part.isdigit():
            return int(part)
    return None


def _build_review_reply_markup(asset_id: int, creative_request_id: int | None = None) -> dict:
    if creative_request_id:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Approve & Publish",
                        "callback_data": f"review:approve:{asset_id}",
                    }
                ],
                [
                    {
                        "text": "🎵 Approve for Music and Manual Posting",
                        "callback_data": f"review:manual_post:{asset_id}:{creative_request_id}",
                    }
                ],
                [
                    {
                        "text": "✏️ Request Edit",
                        "callback_data": f"review:edit:{creative_request_id}",
                    }
                ],
                [
                    {
                        "text": "❌ Reject",
                        "callback_data": f"review:reject:{asset_id}",
                    }
                ],
            ]
        }

    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve:{asset_id}"},
                {"text": "❌ Reject", "callback_data": f"reject:{asset_id}"},
            ]
        ]
    }


def _build_draft_review_message(
    workflow: str,
    client_id: int,
    campaign_id: int,
    asset_id: int,
    review_status: str,
    asset_url: str,
    caption_used: str | None,
    creative_request_id: int | None = None,
) -> str:
    caption_preview = _shorten_caption(caption_used or "")

    music_vibe = "Professional, modern, uplifting, premium corporate"

    lines = [
        f"🎬 Draft generated using {workflow}",
        f"Client ID: {client_id}",
        f"Campaign ID: {campaign_id}",
        f"Asset ID: {asset_id}",
        f"Review Status: {review_status}",
    ]

    if creative_request_id:
        lines.append(f"Creative Request ID: {creative_request_id}")

    lines.extend(
        [
            "",
            "📝 Caption Preview:",
            caption_preview or "(no caption)",
            "",
            f"🎵 Suggested Music Vibe: {music_vibe}",
            "",
            f"🔗 Preview URL: {asset_url}",
            "",
            "Choose one:",
            "• Approve & Publish",
            "• Approve for Music and Manual Posting",
            "• Request Edit",
            "• Reject",
        ]
    )

    return "\n".join(lines)


def _shorten_caption(text: str, max_length: int = 350) -> str:
    value = (text or "").strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def _create_telegram_creative_request(
    db,
    workflow: str,
    context: dict,
    chat_id: int | str | None = None,
    generation_mode: str = "image_to_video",
):
    campaign = db.get(Campaign, context["campaign_id"])
    if not campaign:
        raise TelegramAgentError("Campaign not found for Telegram generation context")

    runtime_prompt_overrides = None
    direct_prompt_payload = None

    if chat_id is not None:
        override_text = _ONE_TIME_PROMPT_OVERRIDES.pop(chat_id, None)
        if override_text:
            runtime_prompt_overrides = {
                "custom_prompt_text": override_text,
                "telegram_freeform_override": override_text,
            }

        direct_prompt_payload = _PENDING_DIRECT_PROMPTS.pop(chat_id, None)

    prompt_mode_key = "managed"
    prompt_resolution_mode = PROMPT_MODE_CONFIG["managed"]["resolution_mode"]
    prompt_input_source = PROMPT_MODE_CONFIG["managed"]["source"]
    direct_prompt_text = None
    client_template_name = None
    direct_prompt_mode = False
    reduce_openai_creative_interpretation = False
    resolved_generation_mode = generation_mode

    if direct_prompt_payload:
        prompt_mode_key = direct_prompt_payload.get("prompt_mode_key") or "managed"
        prompt_resolution_mode = (
            direct_prompt_payload.get("prompt_resolution_mode")
            or PROMPT_MODE_CONFIG[prompt_mode_key]["resolution_mode"]
        )
        prompt_input_source = (
            direct_prompt_payload.get("prompt_source")
            or PROMPT_MODE_CONFIG[prompt_mode_key]["source"]
        )
        direct_prompt_text = (direct_prompt_payload.get("prompt_text") or "").strip() or None
        client_template_name = direct_prompt_payload.get("template_name")
        direct_prompt_mode = bool(direct_prompt_text)
        reduce_openai_creative_interpretation = prompt_mode_key == "guided"
        resolved_generation_mode = direct_prompt_payload.get("generation_mode") or generation_mode

    media_inputs = []
    source_image_s3_key = context.get("source_image_s3_key")
    logo_s3_key = context.get("logo_s3_key")

    if resolved_generation_mode == "image_to_video":
        if not source_image_s3_key:
            raise TelegramAgentError("No source image found for this client’s campaign.")
        media_inputs.append(
            CreativeMediaInputCreate(
                media_role="source_image",
                storage_type="s3",
                storage_key=source_image_s3_key,
                is_primary=True,
            )
        )
    elif resolved_generation_mode == "text_to_image" and source_image_s3_key:
        media_inputs.append(
            CreativeMediaInputCreate(
                media_role="source_image",
                storage_type="s3",
                storage_key=source_image_s3_key,
                is_primary=True,
            )
        )

    creative_request_payload = CreativeRequestCreate(
        client_id=context["client_id"],
        campaign_id=context["campaign_id"],
        content_idea_id=context["content_idea_id"],
        request_source="telegram_command",
        content_goal="lead_generation",
        content_type="instagram_reel",
        target_platform="instagram",
        generation_mode=resolved_generation_mode,
        preferred_workflow=workflow,
        topic=campaign.app_name,
        hook=None,
        angle=None,
        description=campaign.app_description,
        cta=campaign.cta,
        tone=campaign.tone,
        audience=campaign.audience,
        visual_style=None,
        scene_description=direct_prompt_text or None,
        extra_instructions=direct_prompt_text or None,
        raw_input_json={
            "telegram_generation_context": {
                "workflow": workflow,
                "generated_from_chat": True,
                "campaign_id": context["campaign_id"],
                "content_idea_id": context["content_idea_id"],
            },
            "runtime_prompt_overrides": runtime_prompt_overrides,
            "direct_prompt_mode": direct_prompt_mode,
            "direct_client_prompt": direct_prompt_text,
            "client_template_name": client_template_name,
            "prompt_input_source": prompt_input_source,
            "provider_locked": True,
            "workflow_locked": True,
            "reduce_openai_creative_interpretation": reduce_openai_creative_interpretation,
            "prompt_resolution_mode": prompt_resolution_mode,
            "telegram_prompt_mode": prompt_mode_key,
            "source_image_s3_key": source_image_s3_key,
            "logo_s3_key": logo_s3_key,
        },
        media_inputs=media_inputs,
    )

    result = intake_and_resolve_creative_request(db, creative_request_payload)
    return result["creative_request"]



def _handle_edit_followup(chat_id: int | str, text: str, db):
    creative_request_id = _PENDING_EDIT_REQUESTS.pop(chat_id, None)
    if not creative_request_id:
        return {
            "mode": "instant",
            "message": "❌ No pending edit request found.",
        }

    edit_text = (text or "").strip()
    if not edit_text:
        return {
            "mode": "instant",
            "message": "❌ Please send the edit instructions as text.",
        }

    payload = VideoEditRequestCreate(
        creative_request_id=creative_request_id,
        edit_notes=edit_text,
    )

    try:
        result = create_edit_revision_from_creative_request(db, payload)
    except Exception as exc:
        return {
            "mode": "instant",
            "message": f"❌ Failed to create edit revision: {exc}",
        }

    revised_creative_request = result["creative_request"]

    execution_result = run_creative_request_through_existing_pipeline(
        db=db,
        creative_request_id=revised_creative_request.id,
    )

    pipeline_result = execution_result["pipeline_result"]
    asset_id = pipeline_result["generated_asset_id"]
    asset_type = pipeline_result.get("asset_type") or "video"

    set_pending_asset_id(chat_id, asset_id)

    campaign = db.get(Campaign, revised_creative_request.campaign_id)
    campaign_id = campaign.id if campaign else revised_creative_request.campaign_id

    reply_markup = _build_review_reply_markup(
        asset_id=asset_id,
        creative_request_id=revised_creative_request.id,
    )

    message = _build_draft_review_message(
        workflow=revised_creative_request.preferred_workflow or "updated_workflow",
        client_id=revised_creative_request.client_id,
        campaign_id=campaign_id,
        asset_id=asset_id,
        review_status=pipeline_result["review_status"],
        asset_url=pipeline_result["asset_url"],
        caption_used=pipeline_result["caption_used"],
        creative_request_id=revised_creative_request.id,
    )

    response = {
        "mode": "edited_draft_ready",
        "message": message,
        "reply_markup": reply_markup,
        "asset_type": asset_type,
    }

    if asset_type == "image":
        response["image_url"] = pipeline_result["asset_url"]
    else:
        response["video_url"] = pipeline_result["asset_url"]

    return response


def _get_client_for_chat(db, chat_id: int | str | None):
    if not chat_id:
        raise TelegramAgentError("Chat ID is required.")

    client = db.query(Client).filter(Client.telegram_chat_id == str(chat_id)).first()
    if not client:
        raise TelegramAgentError("No client is linked to this Telegram chat yet. Use: link client 1")

    return client


def _get_or_create_workflow_profile(db, client_id: int, workflow: str) -> ClientPromptProfile:
    config = WORKFLOW_CONFIG[workflow]

    profile = (
        db.query(ClientPromptProfile)
        .filter(
            ClientPromptProfile.client_id == client_id,
            ClientPromptProfile.profile_name == config["profile_name"],
            ClientPromptProfile.workflow == workflow,
            ClientPromptProfile.channel == "telegram",
            ClientPromptProfile.content_type == "instagram_reel",
        )
        .first()
    )

    if profile:
        if profile.profile_variables is None:
            profile.profile_variables = {}
        return profile

    profile = ClientPromptProfile(
        client_id=client_id,
        profile_name=config["profile_name"],
        is_active=True,
        is_default=True,
        provider=config["provider"],
        workflow=workflow,
        channel="telegram",
        content_type="instagram_reel",
        brand_voice="",
        style_rules="",
        negative_prompt="",
        creative_guidelines="",
        cta_guidelines="",
        profile_variables={},
        metadata_json={"source": "telegram_style_command"},
    )
    db.add(profile)
    db.flush()

    return profile


def _save_workflow_style(db, chat_id: int | str | None, workflow: str, style_text: str):
    if not style_text:
        return {
            "mode": "instant",
            "message": "❌ Please include the style text after the command.",
        }

    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    profile = _get_or_create_workflow_profile(db, client.id, workflow)
    profile.is_active = True
    profile.is_default = True
    profile.style_rules = style_text
    db.add(profile)
    db.commit()

    workflow_name = WORKFLOW_CONFIG[workflow]["display_name"]
    return {
        "mode": "instant",
        "message": f"🎨 Saved {workflow_name} style:\n\n{style_text}",
    }


def _show_workflow_style(db, chat_id: int | str | None, workflow: str):
    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    config = WORKFLOW_CONFIG[workflow]
    profile = (
        db.query(ClientPromptProfile)
        .filter(
            ClientPromptProfile.client_id == client.id,
            ClientPromptProfile.profile_name == config["profile_name"],
            ClientPromptProfile.workflow == workflow,
            ClientPromptProfile.channel == "telegram",
            ClientPromptProfile.content_type == "instagram_reel",
            ClientPromptProfile.is_active.is_(True),
        )
        .first()
    )

    workflow_name = config["display_name"]

    if not profile:
        return {
            "mode": "instant",
            "message": f"ℹ️ No saved {workflow_name} style found yet.",
        }

    return {
        "mode": "instant",
        "message": (
            f"🎨 Current {workflow_name} style:\n\n"
            f"{(profile.style_rules or '').strip() or '(empty)'}"
        ),
    }


def _clear_workflow_style(db, chat_id: int | str | None, workflow: str):
    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    config = WORKFLOW_CONFIG[workflow]
    profile = (
        db.query(ClientPromptProfile)
        .filter(
            ClientPromptProfile.client_id == client.id,
            ClientPromptProfile.profile_name == config["profile_name"],
            ClientPromptProfile.workflow == workflow,
            ClientPromptProfile.channel == "telegram",
            ClientPromptProfile.content_type == "instagram_reel",
        )
        .first()
    )

    workflow_name = config["display_name"]

    if not profile:
        return {
            "mode": "instant",
            "message": f"ℹ️ No saved {workflow_name} style found to clear.",
        }

    profile.style_rules = ""
    db.add(profile)
    db.commit()

    return {
        "mode": "instant",
        "message": f"🧹 Cleared saved {workflow_name} style.",
    }


def _save_named_template_command(
    db,
    chat_id: int | str | None,
    workflow: str,
    prompt_mode_key: str,
    command_text: str,
    prefix: str,
    generation_mode: str,
):
    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    raw_value = command_text[len(prefix) :].strip()
    if ":" not in raw_value:
        return {
            "mode": "instant",
            "message": "❌ Use format: save <workflow> <mode> template <name>: <prompt>",
        }

    template_name, prompt_text = raw_value.split(":", 1)
    template_name = template_name.strip().lower()
    prompt_text = prompt_text.strip()

    if not template_name or not prompt_text:
        return {
            "mode": "instant",
            "message": "❌ Template name and prompt text are both required.",
        }

    profile = _get_or_create_workflow_profile(db, client.id, workflow)
    profile_variables = dict(profile.profile_variables or {})
    saved_templates = dict(profile_variables.get("saved_templates") or {})
    saved_templates[template_name] = {
        "prompt_text": prompt_text,
        "prompt_mode_key": prompt_mode_key,
        "prompt_resolution_mode": PROMPT_MODE_CONFIG[prompt_mode_key]["resolution_mode"],
        "generation_mode": generation_mode,
        "updated_from": "telegram_save_template",
    }
    profile_variables["saved_templates"] = saved_templates
    profile.profile_variables = profile_variables

    db.add(profile)
    db.commit()

    workflow_name = WORKFLOW_CONFIG[workflow]["display_name"]
    mode_label = PROMPT_MODE_CONFIG[prompt_mode_key]["label"]
    asset_suffix = " image" if generation_mode == "text_to_image" else ""

    return {
        "mode": "instant",
        "message": (
            f"💾 Saved {workflow_name}{asset_suffix} {mode_label} template '{template_name}':\n\n"
            f"{prompt_text}"
        ),
    }


def _show_named_templates(db, chat_id: int | str | None, workflow: str):
    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    profile = _get_or_create_workflow_profile(db, client.id, workflow)
    saved_templates = dict((profile.profile_variables or {}).get("saved_templates") or {})
    workflow_name = WORKFLOW_CONFIG[workflow]["display_name"]

    if not saved_templates:
        return {
            "mode": "instant",
            "message": f"ℹ️ No saved {workflow_name} templates found yet.",
        }

    lines = [f"📚 Saved {workflow_name} templates:"]
    for name in sorted(saved_templates.keys()):
        mode_label = saved_templates[name].get("prompt_mode_key") or "guided"
        generation_mode = saved_templates[name].get("generation_mode") or "image_to_video"
        mode_suffix = "image" if generation_mode == "text_to_image" else "video"
        lines.append(f"- {name} ({mode_label}, {mode_suffix})")

    return {
        "mode": "instant",
        "message": "\n".join(lines),
    }


def _delete_named_template(db, chat_id: int | str | None, workflow: str, template_name: str):
    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    template_name = (template_name or "").strip().lower()
    if not template_name:
        return {
            "mode": "instant",
            "message": "❌ Please provide the template name.",
        }

    profile = _get_or_create_workflow_profile(db, client.id, workflow)
    profile_variables = dict(profile.profile_variables or {})
    saved_templates = dict(profile_variables.get("saved_templates") or {})

    if template_name not in saved_templates:
        return {
            "mode": "instant",
            "message": f"ℹ️ Template '{template_name}' was not found.",
        }

    saved_templates.pop(template_name, None)
    profile_variables["saved_templates"] = saved_templates
    profile.profile_variables = profile_variables

    db.add(profile)
    db.commit()

    return {
        "mode": "instant",
        "message": f"🗑️ Deleted template '{template_name}'.",
    }


def _run_saved_template(
    db,
    chat_id: int | str | None,
    workflow: str,
    default_prompt_mode_key: str,
    template_name: str,
):
    try:
        client = _get_client_for_chat(db, chat_id)
    except TelegramAgentError as exc:
        return {
            "mode": "instant",
            "message": f"❌ {exc}",
        }

    template_name = (template_name or "").strip().lower()
    if not template_name:
        return {
            "mode": "instant",
            "message": "❌ Please provide the template name.",
        }

    profile = _get_or_create_workflow_profile(db, client.id, workflow)
    saved_templates = dict((profile.profile_variables or {}).get("saved_templates") or {})
    template_payload = saved_templates.get(template_name)

    if not template_payload:
        return {
            "mode": "instant",
            "message": f"ℹ️ Template '{template_name}' was not found.",
        }

    prompt_text = (template_payload.get("prompt_text") or "").strip()
    saved_mode = template_payload.get("prompt_mode_key") or default_prompt_mode_key
    generation_mode = template_payload.get("generation_mode") or "image_to_video"

    if not prompt_text:
        return {
            "mode": "instant",
            "message": f"❌ Template '{template_name}' has no prompt text.",
        }

    return _queue_direct_prompt_generation(
        db=db,
        chat_id=chat_id,
        workflow=workflow,
        prompt_text=prompt_text,
        prompt_mode_key=saved_mode,
        template_name=template_name,
        generation_mode=generation_mode,
    )
