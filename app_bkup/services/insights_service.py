from datetime import UTC, datetime, timedelta

from app.pg_tables import Campaign, ContentIdea, GeneratedAsset, PublishedPost


class InsightsError(Exception):
    pass


def build_marketing_summary(db, days: int = 7):
    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    campaigns = db.query(Campaign).all()

    total_campaigns = len(campaigns)

    content_ideas = db.query(ContentIdea).all()
    total_content_ideas = len(content_ideas)

    generated_assets = db.query(GeneratedAsset).all()
    total_assets = len(generated_assets)

    published_posts = (
        db.query(PublishedPost)
        .filter(PublishedPost.created_at >= cutoff_date)
        .all()
    )

    total_published_recent = len(published_posts)

    draft_assets = [
        a for a in generated_assets if a.status == "pending_review"
    ]

    rejected_assets = [
        a for a in generated_assets if a.status == "rejected"
    ]

    approved_assets = [
        a for a in generated_assets if a.status == "approved"
    ]

    published_assets = [
        a for a in generated_assets if a.status == "published"
    ]

    # ---------------- HIGHLIGHTS ----------------
    highlights = []

    highlights.append(f"{total_campaigns} active campaigns")
    highlights.append(f"{total_content_ideas} total content ideas")
    highlights.append(f"{total_assets} total generated assets")

    highlights.append(f"{total_published_recent} posts published in last {days} days")

    highlights.append(f"{len(draft_assets)} drafts pending review")
    highlights.append(f"{len(published_assets)} assets successfully published")

    # ---------------- RECOMMENDATIONS ----------------
    recommendations = []

    if len(draft_assets) > 5:
        recommendations.append(
            "You have many drafts pending review. Consider approving or rejecting faster to maintain content velocity."
        )

    if total_published_recent == 0:
        recommendations.append(
            "No content published recently. Increase posting frequency to stay active."
        )

    if len(rejected_assets) > len(published_assets):
        recommendations.append(
            "High rejection rate detected. Consider improving prompt quality or content strategy."
        )

    if total_campaigns == 0:
        recommendations.append(
            "No campaigns found. Create a campaign to begin generating content."
        )

    if not recommendations:
        recommendations.append(
            "Content pipeline is running smoothly. Continue generating and publishing consistently."
        )

    # ---------------- SUMMARY ----------------
    summary = (
        f"In the last {days} days, your system generated {total_assets} assets and "
        f"published {total_published_recent} posts. "
        f"There are currently {len(draft_assets)} drafts awaiting review."
    )

    return {
        "summary": summary,
        "highlights": highlights,
        "recommendations": recommendations,
        "metrics": {
            "campaigns": total_campaigns,
            "content_ideas": total_content_ideas,
            "generated_assets": total_assets,
            "published_recent": total_published_recent,
            "drafts_pending": len(draft_assets),
            "published_total": len(published_assets),
            "rejected_total": len(rejected_assets),
        },
        "generated_at": datetime.now(UTC),
        "window_days": days,
    }
