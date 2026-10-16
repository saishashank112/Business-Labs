"""App configuration — reads all settings from .env file.

Every field below maps to an environment variable.
Example: t1_api_key  →  T1_API_KEY in .env
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central config for the Knowledge Brain service."""

    # ── API authentication ──────────────────────────────────
    t1_api_key: str = "dev-key"

    # ── Database paths ──────────────────────────────────────
    t1_db_path: str = "task1.db"
    t1_chroma_path: str = "chroma_data"

    # ── Sitemap & crawl settings ────────────────────────────
    t1_sitemap_url: str = (
        "https://support.brilliantdirectories.com/support/sitemap.xml"
    )
    t1_crawl_delay: float = 1.0        # seconds between requests per worker
    t1_crawl_concurrency: int = 2      # max parallel page downloads
    t1_crawl_max_retries: int = 3      # stop retrying a page after this many
    t1_crawl_max_pages: int = 20       # limit for testing; increase later

    # ── Server ──────────────────────────────────────────────
    t1_host: str = "localhost"
    t1_port: int = 8001

    # ── Model names (never hard-coded; set in .env) ─────────
    t1_rag_model: str = "gemini-2.0-flash"
    t1_image_model: str = "gemini-2.0-flash"
    t1_embed_model: str = "all-MiniLM-L6-v2"

    # ── LLM API keys ───────────────────────────────────────
    gemini_api_key: str = ""
    claude_api_key: str = ""

    # ── Profile ─────────────────────────────────────────────
    profile: str = "dev"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Single instance used everywhere via:  from app.config import settings
settings = Settings()
