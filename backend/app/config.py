from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Chatbot Platform"
    secret_key: str = "change-me-in-production-use-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatbot"

    # LLM provider: "groq" | "bytez" | "gemini" | "openrouter"
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_max_output_tokens: int = 512
    groq_max_history_messages: int = 10
    groq_max_prompt_chars: int = 4000
    groq_max_message_chars: int = 3000
    groq_user_rpm: int = 20
    groq_user_daily_limit: int = 500
    groq_global_rpm: int = 40
    groq_min_interval_sec: float = 1.0
    bytez_api_key: str = ""
    bytez_model: str = "Qwen/Qwen3-4B"
    bytez_max_output_tokens: int = 512
    bytez_max_history_messages: int = 10
    bytez_max_prompt_chars: int = 4000
    bytez_max_message_chars: int = 3000
    bytez_user_rpm: int = 10
    bytez_user_daily_limit: int = 200
    bytez_global_rpm: int = 20
    bytez_min_interval_sec: float = 2.0
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"
    gemini_max_output_tokens: int = 512
    gemini_max_history_messages: int = 6
    gemini_max_prompt_chars: int = 2000
    gemini_max_message_chars: int = 1500
    gemini_user_rpm: int = 4          # max messages per user per minute
    gemini_user_daily_limit: int = 40  # max messages per user per day
    gemini_global_rpm: int = 8         # max total API calls per minute
    gemini_min_interval_sec: float = 6.0  # min seconds between user messages
    gemini_max_retries: int = 2
    gemini_enable_file_context: bool = False  # off by default to save free-tier quota
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
