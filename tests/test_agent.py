"""Tests for the quiz agent graph, using a fake model instead of a real API."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from quiz_agent.agent import quiz_agent, quiz_agent_builder

LIST_NOTES_CALL = {"name": "list_notes", "args": {}, "id": "call_1"}


def test_plain_reply_ends_the_run(fake_model):
    model = fake_model(AIMessage(content="Which topic do you want to study?"))

    result = quiz_agent.invoke({"messages": [HumanMessage(content="hi")]})

    assert result["messages"][-1].content == "Which topic do you want to study?"
    assert len(model.received) == 1


def test_tool_call_runs_tool_and_returns_to_model(fake_model, notes_dir):
    model = fake_model(
        AIMessage(content="", tool_calls=[LIST_NOTES_CALL]),
        AIMessage(content="What does mutable mean?"),
    )

    result = quiz_agent.invoke({"messages": [HumanMessage(content="Quiz me on my notes")]})

    tool_message = result["messages"][2]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call_1"
    assert "python_basics.md" in tool_message.content
    assert result["messages"][-1].content == "What does mutable mean?"
    assert len(model.received) == 2


def test_tool_loop_stops_at_limit(fake_model, notes_dir):
    model = fake_model(
        AIMessage(content="", tool_calls=[LIST_NOTES_CALL]),
        AIMessage(content="", tool_calls=[{**LIST_NOTES_CALL, "id": "call_2"}]),
    )

    result = quiz_agent.invoke(
        {"messages": [HumanMessage(content="Quiz me on my notes")]},
        config={"configurable": {"max_react_tool_calls": 1}},
    )

    assert len(model.received) == 1
    assert isinstance(result["messages"][-1], ToolMessage)


def test_difficulty_stays_locked_for_the_thread(fake_model):
    model = fake_model(AIMessage(content="Question 1?"), AIMessage(content="Question 2?"))
    graph = quiz_agent_builder.compile(checkpointer=InMemorySaver())
    thread = {"thread_id": "test-thread"}

    graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"configurable": {**thread, "difficulty": "hard"}},
    )
    graph.invoke(
        {"messages": [HumanMessage(content="next question")]},
        config={"configurable": {**thread, "difficulty": "easy"}},
    )

    second_system_prompt = model.received[1][0].content
    assert "at hard difficulty" in second_system_prompt
