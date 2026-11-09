"""Tests for the quiz agent graph, using a fake model instead of a real API."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from quiz_agent.agent import quiz_agent, quiz_agent_builder
from quiz_agent.state import Grade

LIST_NOTES_CALL = {"name": "list_notes", "args": {}, "id": "call_1"}
CORRECT_GRADE = Grade(is_answer=True, is_correct=True, topic="Python lists", feedback="Mutable means it can change.")
WRONG_GRADE = Grade(is_answer=True, is_correct=False, topic="Python lists", feedback="Mutable means it can change.")
NOT_AN_ANSWER = Grade(is_answer=False, is_correct=False, topic="", feedback="")


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
    model = fake_model(AIMessage(content="Question 1?"), NOT_AN_ANSWER, AIMessage(content="Question 2?"))
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

    # received[1] is the grader's call; received[2] is the quiz master's second turn
    second_system_prompt = model.received[2][0].content
    assert "at hard difficulty" in second_system_prompt


def answer_turn(answer: str) -> dict:
    """Input where the quiz master already asked a question and the user answers it."""
    return {
        "messages": [
            HumanMessage(content="Python"),
            AIMessage(content="What does mutable mean?"),
            HumanMessage(content=answer),
        ]
    }


def test_first_turn_is_not_graded(fake_model):
    model = fake_model(AIMessage(content="Which topic?"))

    result = quiz_agent.invoke({"messages": [HumanMessage(content="hi")]})

    assert len(model.received) == 1
    assert "answered" not in result


def test_correct_answer_is_scored_and_shown_to_quiz_master(fake_model):
    model = fake_model(CORRECT_GRADE, AIMessage(content="Correct! Next question?"))

    result = quiz_agent.invoke(answer_turn("It can be changed after creation"))

    assert result["answered"] == 1
    assert result["correct"] == 1
    grade_message = result["messages"][3]
    assert grade_message.name == "grader"
    assert "score: 1/1" in grade_message.content
    # The quiz master's call ends with the grade message
    assert model.received[1][-1].content == grade_message.content


def test_wrong_answer_counts_as_answered_but_not_correct(fake_model):
    fake_model(WRONG_GRADE, AIMessage(content="Not quite. Next question?"))

    result = quiz_agent.invoke(answer_turn("It means it is sorted"))

    assert result["answered"] == 1
    assert result["correct"] == 0


def test_non_answer_is_not_scored(fake_model):
    fake_model(NOT_AN_ANSWER, AIMessage(content="Sure, what topic instead?"))

    result = quiz_agent.invoke(answer_turn("Can we switch topic?"))

    assert "answered" not in result
    assert not any(message.name == "grader" for message in result["messages"])


def test_grader_retries_after_a_failure(fake_model):
    model = fake_model(
        ValueError("output did not match the schema"),
        CORRECT_GRADE,
        AIMessage(content="Correct! Next question?"),
    )

    result = quiz_agent.invoke(answer_turn("It can be changed after creation"))

    assert len(model.received) == 3
    assert result["correct"] == 1
