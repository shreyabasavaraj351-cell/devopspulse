from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads backend/.env first, then the repo-root .env
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "sqlite:///./pipelinemind.db"
    secret_key: str = "dev-insecure-change-me"
    access_token_expire_minutes: int = 720
    frontend_origin: str = "http://localhost:5173"
    max_upload_bytes: int = 2097152

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    hindsight_base_url: str = "http://localhost:8888"
    hindsight_api_key: str = ""


settings = Settings()
