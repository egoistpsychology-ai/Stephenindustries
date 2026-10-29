"""Environment configuration for Stephen Industries."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if parsed < 0:
        raise ValueError(f"{name} must not be negative")
    return parsed

def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must not be negative")
    return parsed

def _path_env(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path

@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    deepseek_api_key: str
    supabase_url: str
    supabase_key: str
    github_token: str
    github_repo: str
    google_credentials_file: str
    max_cost_usd_per_task: float
    max_delegations_per_task: int
    crewai_storage_dir: Path
    audit_db_path: Path
    groq_input_usd_per_million: float
    groq_output_usd_per_million: float
    deepseek_input_usd_per_million: float
    deepseek_output_usd_per_million: float

def load_settings() -> Settings:
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_repo=os.getenv("GITHUB_REPO", "owner/name"),
        google_credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", ""),
        max_cost_usd_per_task=_float_env("MAX_COST_USD_PER_TASK", 0.50),
        max_delegations_per_task=_int_env("MAX_DELEGATIONS_PER_TASK", 10),
        crewai_storage_dir=_path_env("CREWAI_STORAGE_DIR", "./.memory"),
        audit_db_path=_path_env("AUDIT_DB_PATH", "./audit.sqlite"),
        groq_input_usd_per_million=_float_env("GROQ_INPUT_USD_PER_MILLION", 0.59),
        groq_output_usd_per_million=_float_env("GROQ_OUTPUT_USD_PER_MILLION", 0.79),
        deepseek_input_usd_per_million=_float_env("DEEPSEEK_INPUT_USD_PER_MILLION", 0.27),
        deepseek_output_usd_per_million=_float_env("DEEPSEEK_OUTPUT_USD_PER_MILLION", 1.10),
    )

settings = load_settings()
