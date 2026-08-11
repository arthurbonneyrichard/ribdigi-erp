from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql+asyncpg://ribdigi:ribdigi@postgres:5432/ribdigi_erp"
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = "redis://redis:6379/0"
    RABBITMQ_URL: str = "amqp://ribdigi:ribdigi@rabbitmq:5672/"
    CORS_ORIGINS: str = "http://localhost:3000"
    TRUSTED_HOSTS: str = ""
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_BACKEND: str = "auto"  # auto | redis | memory
    # Production recommendation: set True so multi-instance deploys share sliding windows.
    RATE_LIMIT_REQUIRE_REDIS: bool = False
    RATE_LIMIT_REDIS_PREFIX: str = "ribdigi:ratelimit"
    # Stage 6 P2 — app-data cache (dashboard / catalog). Soft-fail; never 503 on Redis miss.
    CACHE_ENABLED: bool = True
    CACHE_BACKEND: str = "auto"  # auto | redis | memory
    CACHE_REDIS_PREFIX: str = "ribdigi:cache"
    CACHE_DASHBOARD_TTL_SECONDS: int = 300
    CACHE_CATALOG_TTL_SECONDS: int = 600
    # Stage 7 C2 — user permissions cache (architecture: perms:{user_id}, 1h)
    CACHE_PERMISSIONS_TTL_SECONDS: int = 3600
    # Stage 7 W2 — webhook delivery retries (exponential backoff from base)
    WEBHOOK_MAX_ATTEMPTS: int = 5
    WEBHOOK_RETRY_BASE_SECONDS: int = 60
    CELERY_WEBHOOK_RETRY_INTERVAL_SECONDS: int = 30
    ALLOW_DEVELOPMENT_SEED: bool = False
    BACKUP_DIR: str = "/data/backups"
    MEDIA_DIR: str = "/data/media"
    MEDIA_MAX_LOGO_BYTES: int = 2_000_000
    MEDIA_MAX_ATTACHMENT_BYTES: int = 10_000_000
    # local | s3 (MinIO-compatible via S3_ENDPOINT)
    STORAGE_BACKEND: str = "local"
    S3_ENDPOINT: str = ""
    S3_ENDPOINT_URL: str = ""  # alias of S3_ENDPOINT
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_FORCE_PATH_STYLE: bool = True
    BACKUP_RETENTION_COUNT: int = 30
    BACKUP_ENCRYPTION_KEY: str = ""
    # Stage 27 B1 — opt-in auto .ribbak upload after create_backup (Stage 26 env names)
    BACKUP_OFFSITE_UPLOAD_ENABLED: bool = False
    BACKUP_OFFSITE_S3_BUCKET: str = ""
    BACKUP_OFFSITE_S3_PREFIX: str = "ribdigi/logical/ribbak"
    # Stage 27 P1 — PgBouncer transaction mode (also auto-detected for host pgbouncer / :6432)
    PGBOUNCER_TRANSACTION_MODE: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    TOTP_ENCRYPTION_KEY: str = ""
    TOTP_ENFORCED_ROLES: str = "company_admin,super_admin"
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "RIBDIGI ERP"
    WEBAUTHN_ORIGIN: str = ""  # defaults to FRONTEND_URL
    EMAIL_ENABLED: bool = True
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@localhost"
    SMTP_FROM_NAME: str = "RIBDIGI ERP"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: float = 15.0
    FRONTEND_URL: str = "http://localhost:3000"
    SMS_ENABLED: bool = True
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    SMS_TIMEOUT_SECONDS: float = 15.0
    CELERY_ENABLED: bool = True
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_TASK_ALWAYS_EAGER: bool = False
    CELERY_LOW_STOCK_INTERVAL_MINUTES: int = 60
    CELERY_PAYMENT_DUE_INTERVAL_MINUTES: int = 60
    CELERY_QUOTATION_EXPIRY_INTERVAL_MINUTES: int = 60
    CELERY_RECURRING_INTERVAL_MINUTES: int = 15
    CELERY_BACKUP_INTERVAL_MINUTES: int = 60
    CELERY_TRIAL_INTERVAL_MINUTES: int = 60
    CELERY_REPORT_EMAIL_INTERVAL_MINUTES: int = 60
    CELERY_FX_INTERVAL_MINUTES: int = 360
    # open_er_api (default) | frankfurter | disabled
    FX_PROVIDER: str = "open_er_api"
    FX_API_BASE_URL: str = ""
    FX_TIMEOUT_SECONDS: float = 15.0
    # Bank API connectors (mock | http_json per connection; global kill-switch)
    BANK_FEED_SYNC_ENABLED: bool = True
    BANK_FEED_TIMEOUT_SECONDS: float = 30.0
    CELERY_BANK_FEED_INTERVAL_MINUTES: int = 360
    CELERY_AI_PREDICTION_INTERVAL_MINUTES: int = 360
    CELERY_AI_INSIGHTS_INTERVAL_MINUTES: int = 1440
    # POS cash drawer (store-level mode; fallback when shift has no store)
    POS_DRAWER_FALLBACK_MODE: str = "mock"  # none|mock|network|browser_bridge
    POS_DRAWER_DEFAULT_PORT: int = 9100
    POS_DRAWER_TIMEOUT_SECONDS: float = 3.0
    TRIAL_DAYS: int = 14
    TRIAL_GRACE_DAYS: int = 7
    # Stage 1 G19 — catch-all hash-chained audit for mutating /api/v1 writes
    AUDIT_HTTP_MIDDLEWARE_ENABLED: bool = True
    # Stage 1 G20 — BR-17.2 retention / cold archive
    AUDIT_RETENTION_YEARS: int = 7
    # Logs older than this many days are eligible for cold-archive copy (rows are never deleted).
    AUDIT_COLD_ARCHIVE_AFTER_DAYS: int = 365
    CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES: int = 1440
    # Stage 5 H5 — Prometheus-text /metrics (full Grafana stack deferred)
    METRICS_ENABLED: bool = True
    # Stage 18 L1 — structured JSON request/error logs (MVP-lite)
    REQUEST_LOG_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [x.strip() for x in self.TRUSTED_HOSTS.split(",") if x.strip()]

    @property
    def celery_broker_url(self) -> str:
        return (self.CELERY_BROKER_URL or self.RABBITMQ_URL or "").strip()

    @property
    def celery_result_backend(self) -> str:
        if (self.CELERY_RESULT_BACKEND or "").strip():
            return self.CELERY_RESULT_BACKEND.strip()
        # Use Redis DB 1 so rate-limit keys on DB 0 stay isolated
        base = (self.REDIS_URL or "redis://localhost:6379/0").rstrip("/")
        if base.endswith("/0"):
            return base[:-1] + "1"
        return base + "/1"

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.APP_ENV.lower() == "production":
            weak = {"change-me", "change-this-in-production", "dev-secret", ""}
            if self.JWT_SECRET_KEY in weak or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "Production JWT_SECRET_KEY must be a strong secret of at least 32 characters"
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            origins = self.cors_origins
            if not origins:
                raise ValueError("Production CORS_ORIGINS must list at least one allowed origin")
            if any(o == "*" for o in origins):
                raise ValueError("Production CORS_ORIGINS must not include wildcard '*'")
            if not self.RATE_LIMIT_ENABLED:
                raise ValueError("RATE_LIMIT_ENABLED must be true in production")
            if self.RATE_LIMIT_PER_MINUTE < 1 or self.RATE_LIMIT_AUTH_PER_MINUTE < 1:
                raise ValueError("Rate limit values must be positive in production")
            backend = (self.RATE_LIMIT_BACKEND or "auto").lower()
            if backend not in {"auto", "redis", "memory"}:
                raise ValueError("RATE_LIMIT_BACKEND must be auto, redis, or memory")
            if self.RATE_LIMIT_REQUIRE_REDIS and backend == "memory":
                raise ValueError("RATE_LIMIT_REQUIRE_REDIS cannot be used with memory backend")
            if self.EMAIL_ENABLED:
                if not (self.SMTP_HOST or "").strip():
                    raise ValueError("Production EMAIL_ENABLED requires SMTP_HOST")
                if not (self.SMTP_FROM_EMAIL or "").strip():
                    raise ValueError("Production EMAIL_ENABLED requires SMTP_FROM_EMAIL")
            if self.SMS_ENABLED:
                sid = (self.TWILIO_ACCOUNT_SID or "").strip()
                token = (self.TWILIO_AUTH_TOKEN or "").strip()
                from_no = (self.TWILIO_FROM_NUMBER or "").strip()
                if not (sid and token and from_no):
                    raise ValueError(
                        "Production SMS_ENABLED requires TWILIO_ACCOUNT_SID, "
                        "TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER"
                    )
        return self


settings = Settings()
