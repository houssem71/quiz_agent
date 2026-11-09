"""Tests for the notes tools and tool helpers."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from quiz_agent.utils import (
    count_tool_call_rounds,
    get_last_question,
    list_notes,
    load_notes,
)


def test_list_notes_shows_only_notes_files(notes_dir):
    (notes_dir / "draft.py").write_text("print('hi')", encoding="utf-8")
    assert list_notes.invoke({}) == "python_basics.md"


def test_load_notes_reads_file(notes_dir):
    assert load_notes.invoke({"filename": "python_basics.md"}) == "A list is ordered and mutable."


def test_load_notes_refuses_files_outside_notes_folder(notes_dir):
    (notes_dir.parent / "secret.md").write_text("API_KEY=sk-secret", encoding="utf-8")
    result = load_notes.invoke({"filename": "../secret.md"})
    assert result.startswith("Error")
    assert "sk-secret" not in result


def test_load_notes_refuses_non_notes_files(notes_dir):
    (notes_dir / ".env").write_text("API_KEY=sk-secret", encoding="utf-8")
    assert load_notes.invoke({"filename": ".env"}).startswith("Error")


def test_load_notes_reports_missing_file(notes_dir):
    assert "was not found" in load_notes.invoke({"filename": "missing.md"})


def test_count_tool_call_rounds_counts_only_since_last_user_message():
    tool_call = {"name": "list_notes", "args": {}, "id": "call_1"}
    messages = [
        HumanMessage(content="first"),
        AIMessage(content="", tool_calls=[tool_call]),
        ToolMessage(content="python_basics.md", tool_call_id="call_1"),
        AIMessage(content="Question 1?"),
        HumanMessage(content="second"),
        AIMessage(content="", tool_calls=[{**tool_call, "id": "call_2"}]),
    ]
    assert count_tool_call_rounds(messages) == 1


def test_get_last_question_is_none_on_first_turn():
    assert get_last_question([HumanMessage(content="hi")]) is None


def test_get_last_question_skips_tool_calls():
    tool_call = {"name": "list_notes", "args": {}, "id": "call_1"}
    messages = [
        HumanMessage(content="Quiz me on my notes"),
        AIMessage(content="", tool_calls=[tool_call]),
        ToolMessage(content="python_basics.md", tool_call_id="call_1"),
        AIMessage(content="What does mutable mean?"),
        HumanMessage(content="It can change"),
    ]
    assert get_last_question(messages) == "What does mutable mean?"
