from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    profile: str = "dev"
    gemini_api_key: str = ""
    claude_api_key: str = ""
    anthropic_api_key: str = ""
    claude_model_fast: str = ""
    claude_model_strong: str = ""
    grader_model: str = "gemini-2.5-flash-lite"

    # Task 3 configuration
    t3_db_path: str = "task3.db"
    t3_hourly_rate: float = 150.0
    t3_currency: str = "USD"
    t3_tax_rate: float = 0.0

    # Task 1 connection (HTTP only!)
    t1_base_url: str = "http://localhost:8001"
    t1_api_key: str = ""

    # Model names per agent
    t3_extract_model: str = "gemini-3.8-flash"
    t3_feasibility_model: str = "gemini-3.8-flash"
    t3_scope_model: str = "gemini-3.8-flash"
    t3_estimate_model: str = "gemini-3.8-flash"
    t3_proposal_model: str = "gemini-3.8-flash"

    # LLM Response Cache
    llm_cache_enabled: bool = True

    # Offline Heuristic degraded mode fallback (default False for evals/production safety)
    allow_offline_fallback: bool = False

    class Config:
        env_file = "../.env"
        extra = "ignore"


settings = Settings()
