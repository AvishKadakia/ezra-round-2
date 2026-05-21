from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="", validation_alias=AliasChoices("DATABASE_URL"))

    # Accept both your app names and Railway/AWS auto-injected names.
    s3_endpoint_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "S3_ENDPOINT_URL",
            "BUCKET_ENDPOINT",
            "AWS_ENDPOINT_URL_S3",
            "AWS_S3_ENDPOINT_URL",
        ),
    )
    s3_bucket_name: str = Field(
        default="",
        validation_alias=AliasChoices(
            "S3_BUCKET_NAME",
            "BUCKET_NAME",
            "AWS_BUCKET_NAME",
        ),
    )
    s3_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "S3_ACCESS_KEY_ID",
            "AWS_ACCESS_KEY_ID",
            "BUCKET_ACCESS_KEY_ID",
        ),
    )
    s3_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "S3_SECRET_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY",
            "BUCKET_SECRET_ACCESS_KEY",
        ),
    )
    s3_region: str = Field(
        default="auto",
        validation_alias=AliasChoices(
            "S3_REGION",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            "BUCKET_REGION",
        ),
    )

    # Let botocore choose unless Railway tells you otherwise.
    s3_addressing_style: str = Field(default="auto", validation_alias=AliasChoices("S3_ADDRESSING_STYLE"))

    public_api_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    mcp_public_url: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:4173"

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    max_upload_bytes: int = 10 * 1024 * 1024
    upload_chunk_bytes: int = 1024 * 1024
    max_pdf_pages_to_summarize: int = 20

    worker_poll_seconds: float = 2.0
    worker_recovery_seconds: float = 15.0
    worker_stale_job_seconds: int = 30 * 60

    s3_connect_timeout_seconds: int = 5
    s3_read_timeout_seconds: int = 15
    s3_max_attempts: int = 2
    s3_ssl_verify: bool = True
    s3_ca_bundle: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("s3_endpoint_url")
    @classmethod
    def normalize_s3_endpoint(cls, value: str) -> str:
        value = value.strip().strip('"').strip("'")
        if value and not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value.rstrip("/")

    @field_validator("s3_bucket_name", "s3_access_key_id", "s3_secret_access_key", "s3_region", "s3_addressing_style")
    @classmethod
    def strip_secret_like_values(cls, value: str) -> str:
        return value.strip().strip('"').strip("'")

    @property
    def normalized_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_mcp_url(self) -> str:
        if self.mcp_public_url:
            return self.mcp_public_url.rstrip("/")
        return f"{self.public_api_base_url.rstrip('/')}/mcp"


@lru_cache
def get_settings() -> Settings:
    return Settings()