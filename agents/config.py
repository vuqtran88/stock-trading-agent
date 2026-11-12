"""LLM configuration and settings for the multi-agent stock picking committee."""

import logging
import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class AgentSettings(BaseSettings):
    """Agent and LLM configuration with multi-provider fallback."""

    # Default LLM Model. LiteLLM format: 'gemini/gemini-4-argon', 'gemini/gemini-3.8-flash', 'gpt-4o-mini', etc.
    LLM_MODEL: str = "gemini/gemini-4-argon"
    LLM_FALLBACK_MODEL: str = "gemini/gemini-3.8-flash"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1500

    # Provider API keys (loaded from environment or GCP Secret Manager if present)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    model_config = ConfigDict(env_file=".env", extra="ignore")

    def ensure_environment_keys(self) -> None:
        """Propagate loaded API keys to os.environ for LiteLLM, with GCP Secret Manager fallback."""
        if not self.GEMINI_API_KEY and not os.environ.get("GEMINI_API_KEY"):
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                secret_name = "projects/stock-trading-agent-249477/secrets/gemini-api-key/versions/latest"
                resp = client.access_secret_version(name=secret_name)
                key = resp.payload.data.decode("utf-8").strip()
                if key:
                    self.GEMINI_API_KEY = key
                    logger.info("Loaded GEMINI_API_KEY from GCP Secret Manager.")
            except Exception as e:
                logger.debug(f"GCP Secret Manager gemini-api-key lookup skipped: {e}")

        if self.GEMINI_API_KEY and not os.environ.get("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = self.GEMINI_API_KEY
        if self.OPENAI_API_KEY and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY
        if self.ANTHROPIC_API_KEY and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = self.ANTHROPIC_API_KEY


agent_settings = AgentSettings()
agent_settings.ensure_environment_keys()
