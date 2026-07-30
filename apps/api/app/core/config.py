from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every knob comes from the environment — nothing is hardcoded per-environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # ── app ──
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"
    seed_on_startup: bool = True

    # ── organization (single-tenant) ──
    org_name: str = "Matchify"
    org_website: str = "https://matchify.ai"

    # ── mongo ──
    mongo_url: str = "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true"
    mongo_db: str = "matchify"

    # ── auth ──
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cookie_secure: bool = False
    cookie_domain: str = ""

    # Open manager signup is convenient for a demo and wrong for production —
    # flip to false and invite managers instead.
    allow_manager_signup: bool = True

    access_cookie_name: str = "mx_access"
    refresh_cookie_name: str = "mx_refresh"
    # Readable by JS on purpose: the Next.js middleware uses it to pick a
    # redirect target. It is a UX hint only — never trusted for authorization.
    role_cookie_name: str = "mx_role"

    # ── object storage (MinIO) ──
    # Signed for the browser, reached over the compose network by the server.
    storage_endpoint_internal: str = "http://minio:9000"
    storage_endpoint_public: str = "http://localhost:9000"
    storage_access_key: str = "matchify"
    storage_secret_key: str = "matchify-dev-secret"
    storage_bucket: str = "matchify"
    # Must match MINIO_REGION on the server. Any label works — it only has to
    # agree on both sides, since it is part of the request signature.
    storage_region: str = "local"
    presign_ttl_seconds: int = 900
    max_upload_mb: int = 10

    # ── Resume parsing (one of two LLM uses in this codebase — the other is
    #    the interview-booking chat agent below, which shares this same
    #    OpenRouter key/model) ──
    #: "stub" (regex only, no key needed) or "openrouter" (an LLM).
    resume_parser: str = "stub"

    # OpenRouter is OpenAI-compatible, so `ai_model` is any model slug it routes
    # to — swapping providers is a config change, not a code change.
    openrouter_api_key: str = ""
    # Shared secret the AI team's service presents to read the graph export.
    # This is how they get data; they do not call us for scoring.
    # Machine-to-machine, so it is not tied to a user account and can be rotated
    # without touching anyone's login. Empty disables the endpoints entirely.
    inbound_ai_token: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ai_model: str = "anthropic/claude-opus-4-8"

    # ── Match scoring hand-off ──
    # When a candidate applies, we ping this URL so the AI team can score the
    # (candidate, job) pair and write the result back. Fire-and-forget: a down
    # webhook never affects the apply, and they also reconcile from
    # GET /graph/applications?match_status=pending. Empty disables the ping.
    ai_match_webhook_url: str = ""
    #: Presented to the webhook as `X-Matchify-Token` so the receiver can tell a
    #: genuine call from noise. Optional.
    ai_match_webhook_token: str = ""

    # ── Calendar assistant (interview scheduling) ──
    # Reaches the calendar-mcp sidecar container. Empty disables interview
    # scheduling entirely (calendar_service fails closed with a 503) — which
    # also disables the booking chat agent, since its two tools are
    # get_availability/book_interview.
    calendar_assistant_url: str = ""
    calendar_assistant_token: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
