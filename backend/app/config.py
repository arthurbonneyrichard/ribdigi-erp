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
    # Offline POS authorization window. Default matches refresh-token days (7×24h).
    # Tenants may set 1–168 hours via company profile; the POS client must not hardcode 7 days.
    OFFLINE_AUTH_HOURS_DEFAULT: int = 168
    OFFLINE_AUTH_HOURS_MIN: int = 1
    OFFLINE_AUTH_HOURS_MAX: int = 168
    # Existing env files may still set this. The till does not park a sale after this many tries.
    OFFLINE_SYNC_MAX_RETRIES: int = 8
    REDIS_URL: str = "redis://redis:6379/0"
    RABBITMQ_URL: str = "amqp://ribdigi:ribdigi@rabbitmq:5672/"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    TRUSTED_HOSTS: str = ""
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120
    # GET/HEAD share this bucket. Default matches PER_MINUTE; raise only when
    # a real read burst (inventory + credit + notifications) is blocked.
    RATE_LIMIT_READ_PER_MINUTE: int = 180
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_BACKEND: str = "auto"  # auto | redis | memory
    RATE_LIMIT_REQUIRE_REDIS: bool = False
    RATE_LIMIT_REDIS_PREFIX: str = "ribdigi:ratelimit"
    # Auto-log successful POST/PUT/PATCH/DELETE under /api/v1 (BR-17.1 catch-all).
    AUDIT_HTTP_MIDDLEWARE_ENABLED: bool = True
    # BR-17.2 — minimum retention (years); cold archive after N hot days (rows kept, not purged).
    AUDIT_RETENTION_YEARS: int = 7
    AUDIT_COLD_ARCHIVE_AFTER_DAYS: int = 365
    CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES: int = 1440
    # BR-18.6 — webhook delivery retries (exponential backoff from base)
    WEBHOOK_MAX_ATTEMPTS: int = 5
    WEBHOOK_RETRY_BASE_SECONDS: int = 60
    CELERY_WEBHOOK_RETRY_INTERVAL_SECONDS: int = 30
    ALLOW_DEVELOPMENT_SEED: bool = False
    # Deploy identity — set by Docker Compose build/runtime for Dokploy verification.
    # release_channel must be "production" for the commercial ERP (not GitHub main).
    RIBDIGI_RELEASE_CHANNEL: str = "development"
    RIBDIGI_BUILD_ID: str = "dev"
    BACKUP_DIR: str = "/data/backups"
    MEDIA_DIR: str = "/data/media"
    MEDIA_MAX_LOGO_BYTES: int = 2_000_000
    MEDIA_MAX_ATTACHMENT_BYTES: int = 10_000_000
    SUPPORT_ATTACHMENT_MAX_BYTES: int = 10_000_000
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
    TOTP_ENCRYPTION_KEY: str = ""
    TOTP_ENFORCED_ROLES: str = "company_admin,super_admin"
    # When false, login skips TOTP/passkey challenge and enrollment gates (password + tenant only).
    # Set true in production to require enrolled second factors at sign-in.
    LOGIN_2FA_ENABLED: bool = False
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "RIBDIGI ERP"
    WEBAUTHN_ORIGIN: str = ""  # defaults to FRONTEND_URL
    EMAIL_ENABLED: bool = True
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@localhost"
    SMTP_FROM_NAME: str = "Ribdigi House"
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
    CELERY_BATCH_EXPIRY_INTERVAL_MINUTES: int = 60
    CELERY_RECURRING_INTERVAL_MINUTES: int = 15
    CELERY_RECURRING_NOTIFY_INTERVAL_MINUTES: int = 60
    CELERY_BACKUP_INTERVAL_MINUTES: int = 60
    CELERY_TRIAL_INTERVAL_MINUTES: int = 60
    CELERY_BILLING_INTERVAL_MINUTES: int = 60
    # SaaS subscription billing (tenants paying for Ribdigi). mock | paystack | flutterwave.
    # mock never charges in production. A live provider charges only with its secret.
    BILLING_PROVIDER: str = "mock"
    PAYSTACK_SECRET_KEY: str = ""
    FLUTTERWAVE_SECRET_KEY: str = ""
    FLUTTERWAVE_WEBHOOK_HASH: str = ""
    BILLING_WEBHOOK_SECRET: str = ""
    BILLING_GRACE_DAYS: int = 7
    BILLING_MAX_ATTEMPTS: int = 3
    BILLING_REMINDER_DAYS: str = "7,3,1"
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
    # POS cash drawer (store-level mode; fallback when shift has no store)
    POS_DRAWER_FALLBACK_MODE: str = "mock"  # none|mock|network|browser_bridge
    POS_DRAWER_DEFAULT_PORT: int = 9100
    POS_DRAWER_TIMEOUT_SECONDS: float = 3.0
    TRIAL_DAYS: int = 14
    TRIAL_GRACE_DAYS: int = 7
    # Ops monitoring (Prometheus text + structured request logs)
    METRICS_ENABLED: bool = True
    REQUEST_LOG_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    # AI Business Assistant (fail-closed until enabled + approved provider + key)
    AI_ENABLED: bool = False
    AI_PROVIDER: str = "none"  # none | openai | mock (mock = non-production only)
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = ""
    AI_MODEL: str = ""
    AI_MAX_MESSAGE_CHARS: int = 16000  # ~4096 tokens heuristic
    AI_CHAT_TIMEOUT_SECONDS: float = 30.0
    # AI Security Monitor (rule-based; no LLM)
    AI_SECURITY_MONITOR_ENABLED: bool = True
    AI_SECURITY_ALERT_THRESHOLD: int = 60
    CELERY_AI_SECURITY_INTERVAL_MINUTES: int = 15
    # AI inventory predictions (rule-based velocity; no LLM)
    AI_INVENTORY_LOOKBACK_DAYS: int = 28
    AI_INVENTORY_DEFAULT_LEAD_DAYS: int = 7
    AI_INVENTORY_COVER_DAYS: int = 14

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
            if (
                self.RATE_LIMIT_PER_MINUTE < 1
                or self.RATE_LIMIT_AUTH_PER_MINUTE < 1
                or self.RATE_LIMIT_READ_PER_MINUTE < 1
            ):
                raise ValueError("Rate limit values must be positive in production")
            if not self.trusted_hosts:
                raise ValueError(
                    "Production TRUSTED_HOSTS must list at least one host "
                    "(e.g. erp.ribdigihouse.com,localhost,127.0.0.1)"
                )
            if not self.LOGIN_2FA_ENABLED:
                raise ValueError(
                    "Production LOGIN_2FA_ENABLED must be true "
                    "(password-only login is not allowed in production)"
                )
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
            billing_provider = (self.BILLING_PROVIDER or "mock").strip().lower()
            if billing_provider not in {"mock", "paystack", "flutterwave"}:
                raise ValueError("BILLING_PROVIDER must be mock, paystack, or flutterwave")
            if billing_provider == "paystack":
                secret = (self.PAYSTACK_SECRET_KEY or "").strip()
                weak_keys = {"", "change-me", "sk_test", "sk_live"}
                if secret.lower() in weak_keys or len(secret) < 16:
                    raise ValueError(
                        "Production BILLING_PROVIDER=paystack requires PAYSTACK_SECRET_KEY"
                    )
            if billing_provider == "flutterwave":
                secret = (self.FLUTTERWAVE_SECRET_KEY or "").strip()
                weak_keys = {"", "change-me", "flwseck_test", "flwseck"}
                if secret.lower() in weak_keys or len(secret) < 16:
                    raise ValueError(
                        "Production BILLING_PROVIDER=flutterwave requires FLUTTERWAVE_SECRET_KEY"
                    )
            if self.AI_ENABLED:
                provider = (self.AI_PROVIDER or "").strip().lower()
                if provider in {"", "none", "mock"}:
                    raise ValueError(
                        "Production AI_ENABLED requires AI_PROVIDER=openai "
                        "(mock is not allowed in production)"
                    )
                if provider not in {"openai"}:
                    raise ValueError(
                        f"Production AI_PROVIDER '{provider}' is not an approved provider"
                    )
                key = (self.AI_API_KEY or "").strip()
                weak = {"", "change-me", "changeme", "replace-me", "your-api-key", "sk-test"}
                if not key or key.lower() in weak or len(key) < 16:
                    raise ValueError(
                        "Production AI_ENABLED requires a strong AI_API_KEY "
                        "(min 16 chars, not a placeholder)"
                    )
                if self.AI_MAX_MESSAGE_CHARS < 256:
                    raise ValueError("AI_MAX_MESSAGE_CHARS must be >= 256 in production")
        return self


settings = Settings()
