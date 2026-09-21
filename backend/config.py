"""Every environment variable the backend reads, validated once (#250).

Configuration used to be read where it was used: a KeyError at import in one
module, a bare int() cast in another, and a friendly check in main.py that
covered SECRET_KEY alone and ran only if nothing had raised first. A bad
deploy failed on whichever problem it hit first, one per restart, often as a
traceback that never named the variable.

This module is the only place the environment is read — tests/test_settings.py
enforces that — and it reports every problem together, by variable name,
before any other module finishes importing.
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# The repo-root .env: what find_dotenv() located when walking up from backend/,
# so `fastapi dev` from backend/ keeps working. Absent inside the containers,
# which get their configuration from compose instead.
ENV_FILE: Path = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # extra="ignore": the root .env also serves scripts/scale_ingest.py, whose
    # ADMIN_USERNAME / ADMIN_PASSWORD would otherwise be rejected as unknown.
    model_config = SettingsConfigDict(extra="ignore")

    secret_key: str = Field(min_length=1)
    database_url: str = Field(min_length=1)

    jwt_expire_days: int = Field(default=7, gt=0)

    db_pool_size: int = Field(default=5, gt=0)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: int = Field(default=30, gt=0)

    # NoDecode: pydantic-settings would otherwise parse a list field as JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    fitman_log_format: Literal["json", "text"] = "json"
    rate_limit_disabled: bool = False

    # Scale fallbacks when neither the request nor the profile supplies a
    # value; 0 means "not configured" for height and age.
    scale_height_cm: float = Field(default=0, ge=0)
    scale_age: int = Field(default=0, ge=0)
    scale_sex: int = Field(default=1, ge=0, le=1)  # 1 = male, 0 = female

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


def _describe(error: ErrorDetails) -> str:
    name = str(error["loc"][0]).upper() if error["loc"] else "?"
    if error["type"] == "missing":
        return f"  {name}: required but not set"
    return f"  {name}: {error['msg']} (got {error['input']!r})"


def load_settings(env_file: Path | None = ENV_FILE) -> Settings:
    """Validate the environment, or stop with one message naming every problem.

    Raises SystemExit rather than letting ValidationError escape: the reader is
    an operator looking at container logs, who needs variable names and bad
    values, not pydantic field names and a documentation URL.
    """
    try:
        return Settings(_env_file=env_file)  # type: ignore[call-arg]
    except ValidationError as exc:
        lines = [_describe(e) for e in exc.errors(include_url=False)]
        raise SystemExit(
            "ERROR: invalid configuration:\n"
            + "\n".join(lines)
            + "\nCopy .env.example to .env and fill in the values."
        ) from None


settings = load_settings()
