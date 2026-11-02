"""Configuration management for the quiz agent."""

import os
from enum import Enum
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class Difficulty(Enum):
    """How hard the quiz questions should be."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Configuration(BaseModel):
    """Main configuration class for the quiz agent."""

    # Quiz Configuration
    difficulty: Difficulty = Field(
        default=Difficulty.MEDIUM,
        metadata={
            "x_oap_ui_config": {
                "type": "select",
                "default": "medium",
                "description": "How hard the quiz questions should be",
                "options": [
                    {"label": "Easy", "value": Difficulty.EASY.value},
                    {"label": "Medium", "value": Difficulty.MEDIUM.value},
                    {"label": "Hard", "value": Difficulty.HARD.value},
                ],
            }
        },
    )
    # Model Configuration
    quiz_model: str = Field(
        default="anthropic:claude-haiku-5-5",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "anthropic:claude-haiku-5-5",
                "description": "Model that asks the questions and grades the answers",
            }
        },
    )
    quiz_model_max_tokens: int = Field(
        default=512,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 512,
                "min": 64,
                "max": 4096,
                "description": "Maximum output tokens for each quiz model reply",
            }
        },
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})
