"""Shared pytest fixtures for the quiz agent tests."""

from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from quiz_agent import agent, utils
from quiz_agent.configuration import Configuration


class FakeChatModel(BaseChatModel):
    """Chat model that returns scripted replies and records what it received, without calling an API.

    A scripted reply can be an AIMessage, a structured output object such as a Grade,
    or an exception to raise (to test retries).
    """

    responses: list[Any]
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _next_response(self, messages):
        self.received.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._next_response(messages))])

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(self._next_response)

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

    def install(*responses: Any) -> FakeChatModel:
        model = FakeChatModel(responses=list(responses))
        monkeypatch.setattr(agent, "configurable_model", model)
        return model

    return install
