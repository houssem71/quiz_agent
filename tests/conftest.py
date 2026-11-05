"""Shared pytest fixtures for the quiz agent tests."""

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from quiz_agent import agent, utils
from quiz_agent.configuration import Configuration


class FakeChatModel(BaseChatModel):
    """Chat model that returns scripted replies and records what it received, without calling an API."""

    responses: list[AIMessage]
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])

    def bind_tools(self, tools, **kwargs):
        return self

    def with_config(self, config=None, **kwargs):
        return self


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove config environment variables so they can't override the test's config."""
    for field_name in Configuration.model_fields:
        monkeypatch.delenv(field_name.upper(), raising=False)


@pytest.fixture
def notes_dir(tmp_path, monkeypatch):
    """Point the notes tools at a temporary folder with one notes file."""
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "python_basics.md").write_text("A list is ordered and mutable.", encoding="utf-8")
    monkeypatch.setattr(utils, "NOTES_DIR", notes)
    return notes


@pytest.fixture
def fake_model(monkeypatch):
    """Replace the agent's model with a FakeChatModel that returns the given replies in order."""

    def install(*responses: AIMessage) -> FakeChatModel:
        model = FakeChatModel(responses=list(responses))
        monkeypatch.setattr(agent, "configurable_model", model)
        return model

    return install
