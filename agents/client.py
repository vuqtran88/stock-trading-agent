"""Unified LLM client using LiteLLM with structured output and fallback support."""

import json
import logging
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel
import litellm
from agents.config import agent_settings

logger = logging.getLogger(__name__)

# Suppress noisy LiteLLM telemetry/logs
litellm.telemetry = False
litellm.drop_params = True


class LLMClient:
    """Multi-provider LLM caller supporting async structured completions."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or agent_settings.LLM_MODEL
        self.fallback_model = agent_settings.LLM_FALLBACK_MODEL
        self.temperature = agent_settings.LLM_TEMPERATURE

    async def complete_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Type[BaseModel],
    ) -> BaseModel:
        """Call LLM and parse response strictly into the given Pydantic schema."""
        schema_dict = response_schema.model_json_schema()
        system_instruction = (
            f"You MUST respond ONLY with valid JSON conforming strictly to this schema:\n"
            f"{json.dumps(schema_dict, indent=2)}\n"
            f"Do not include any Markdown fencing (e.g. ```json), commentary, or preambles."
        )

        full_messages = [{"role": "system", "content": system_instruction}] + messages

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=full_messages,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content.strip()
            # Clean possible markdown wrapping if the model ignored the system prompt
            if raw_content.startswith("```"):
                lines = raw_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_content = "\n".join(lines).strip()

            parsed = json.loads(raw_content)
            return response_schema.model_validate(parsed)
        except Exception as primary_err:
            logger.warning(
                f"Primary model {self.model} failed ({primary_err}). Attempting fallback {self.fallback_model}..."
            )
            try:
                response = await litellm.acompletion(
                    model=self.fallback_model,
                    messages=full_messages,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
                raw_content = response.choices[0].message.content.strip()
                if raw_content.startswith("```"):
                    lines = raw_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_content = "\n".join(lines).strip()
                return response_schema.model_validate(json.loads(raw_content))
            except Exception as fallback_err:
                logger.error(f"Both primary and fallback LLM failed: {fallback_err}")
                raise RuntimeError(f"LLM completion error: {fallback_err}") from fallback_err

