import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
# 1. Try backend/ folder
# 2. Try project root/ folder
backend_env = Path(__file__).resolve().parent / ".env"
root_env = Path(__file__).resolve().parent.parent / ".env"

if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv() # Fallback to system env


class Settings:
    BASE_DIR = Path(__file__).resolve().parent
    EOI_DATA_DIR = str(BASE_DIR / "data" / "raw" / "eoi")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Async DB URL — defaults to local MySQL; override via DATABASE_URL env var
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+aiomysql://root:@localhost:3306/migration_db",
    )

    # Helper to parse DATABASE_URL to PyMySQL connection arguments
    @property
    def get_pymysql_args(self) -> dict:
        # Expected format: mysql+aiomysql://user:password@host:port/dbname
        # or mysql+pymysql://user:password@host:port/dbname
        import urllib.parse
        parsed = urllib.parse.urlparse(self.DATABASE_URL)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": parsed.username or "root",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/") or "migration_db",
            "autocommit": True # Add this so scripts auto-commit like sqlite mostly does
        }

    # Redis configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Cache TTL settings (in seconds)
    CACHE_DEFAULT_TTL: int = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
    CACHE_LONG_TTL: int = int(os.getenv("CACHE_LONG_TTL", "86400"))  # 24 hours

    # LLM Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Gemini model fallback chain — verified working models only
    # Invalid model names cause wasted API retry timeouts
    GEMINI_MODEL_FALLBACKS: list = [
        os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),  # Primary
        "gemini-2.5-flash",        # Latest 2.5
        "gemini-2.5-flash-lite",   # Lightweight 2.5
        "gemini-3-flash-preview",  # Next gen preview
        "gemini-1.5-flash-latest", # Reliable classic
    ]
    # Remove duplicates while preserving order
    GEMINI_MODEL_FALLBACKS = list(dict.fromkeys(GEMINI_MODEL_FALLBACKS))

    # SMTP Configuration for Emails
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "Migration Intelligence <noreply@migrationintelligence.com>")

    # Google Cloud Storage
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "interlace-migration-platform")
    GCS_PROJECT_ID: str = os.getenv("GCS_PROJECT_ID", "")

    # Sentry Error Tracking
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_ENV: str = os.getenv("SENTRY_ENV", "production")


settings = Settings()