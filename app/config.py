import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH, override=True)


class Settings(BaseSettings):
    APP_NAME: str = os.getenv("APP_NAME", "AI Content Agent")
    APP_ENV: str = os.getenv("APP_ENV", "dev")

    DATABASE_URL: str | None = os.getenv("DATABASE_URL")

    HIGGSFIELD_API_KEY: str | None = os.getenv("HIGGSFIELD_API_KEY")
    HIGGSFIELD_API_SECRET: str | None = os.getenv("HIGGSFIELD_API_SECRET")
    HIGGSFIELD_BASE_URL: str = os.getenv(
        "HIGGSFIELD_BASE_URL",
        "https://platform.higgsfield.ai",
    )

    S3_BUCKET_NAME: str | None = os.getenv("S3_BUCKET_NAME")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-2")
    AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    S3_IMAGE_PREFIX: str = os.getenv("S3_IMAGE_PREFIX", "image-folder/")
    S3_VIDEO_PREFIX: str = os.getenv("S3_VIDEO_PREFIX", "video-folder/")

    INSTAGRAM_GRAPH_BASE_URL: str = os.getenv(
        "INSTAGRAM_GRAPH_BASE_URL",
        "https://graph.facebook.com/v25.0",
    )
    INSTAGRAM_ACCESS_TOKEN: str | None = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    INSTAGRAM_ACCOUNT_ID: str | None = os.getenv("INSTAGRAM_ACCOUNT_ID")

    OPENCLAW_BASE_URL: str | None = os.getenv("OPENCLAW_BASE_URL")
    OPENCLAW_MODEL: str | None = os.getenv("OPENCLAW_MODEL")
    OPENCLAW_TOKEN: str | None = os.getenv("OPENCLAW_TOKEN")
    OPENCLAW_ENABLED: bool = os.getenv("OPENCLAW_ENABLED", "false").lower() == "true"
    

    OPENAI_API_KEY: str | None = None
    OPENAI_REASONING_MODEL: str = os.getenv("OPENAI_REASONING_MODEL", "gpt-5.4")


    TELEGRAM_WEBHOOK_SECRET_TOKEN: str | None = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
    TELEGRAM_BOT_BASE_URL: str = os.getenv("TELEGRAM_BOT_BASE_URL", "https://api.telegram.org")
    TELEGRAM_REVIEW_BASE_URL: str = os.getenv("TELEGRAM_REVIEW_BASE_URL", "https://bot.brainelle.ai")    
    TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN") 


    RUNWAY_API_KEY: str | None = os.getenv("RUNWAY_API_KEY")
    RUNWAY_BASE_URL: str = os.getenv("RUNWAY_BASE_URL", "https://api.dev.runwayml.com")
    RUNWAY_API_VERSION: str = os.getenv("RUNWAY_API_VERSION", "2024-11-06")
    RUNWAY_MODEL: str = os.getenv("RUNWAY_MODEL", "gen4.5")

    ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_BASE_URL: str = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")
    ELEVENLABS_VOICE_ID: str | None = os.getenv("ELEVENLABS_VOICE_ID")
    ELEVENLABS_MODEL_ID: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    VIDEO_PROVIDER: str = os.getenv("VIDEO_PROVIDER", "runway")
    VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "elevenlabs")

    FFMPEG_BIN: str = os.getenv("FFMPEG_BIN", "ffmpeg")

    def validate_required(self) -> None:
        missing: list[str] = []

        required_vars = {
            "S3_BUCKET_NAME": self.S3_BUCKET_NAME,
            "DATABASE_URL": self.DATABASE_URL,
        }

        for name, value in required_vars.items():
            if not value:
                missing.append(name)

        if missing:
            missing_str = ", ".join(missing)
            raise RuntimeError(
                f"Missing required environment variables in {ENV_PATH}: {missing_str}"
            )


settings = Settings()
