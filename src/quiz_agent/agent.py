"""Main LangGraph implementation of the quiz agent."""

from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from quiz_agent.configuration import Configuration
from quiz_agent.prompts import (
    grade_answer_prompt,
    grade_message_template,
    quiz_master_system_prompt,
)
from quiz_agent.state import Grade, QuizState
from quiz_agent.utils import (
    QUIZ_TOOLS,
    count_tool_call_rounds,
    execute_tool_safely,
    get_last_question,
    load_learner_history,
    save_quiz_result,
)

# Initialize a configurable model; the actual model is chosen per call from Configuration
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens"),
)


def grade_answer(state: QuizState, config: RunnableConfig) -> Command[Literal["quiz_master"]]:
    """Grade the user's latest message as structured data and update the thread's score."""
    question = get_last_question(state["messages"])
    # First turn: there is no question to answer yet
    if question is None:
        return Command(goto="quiz_master")

    configurable = Configuration.from_runnable_config(config)
    model_config = {
        "model": configurable.quiz_model,
        "max_tokens": configurable.quiz_model_max_tokens,
    }
    # json_schema uses Claude's native structured outputs, which work with thinking enabled
    grader_model = (
        configurable_model
        .with_structured_output(Grade, method="json_schema")
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(model_config)
    )

    prompt = grade_answer_prompt.format(question=question, answer=state["messages"][-1].text)
    grade: Grade = grader_model.invoke([HumanMessage(content=prompt)])
    if not grade.is_answer:
        return Command(goto="quiz_master")

    # Long-term memory: the store outlives this thread, the score below does not
    save_quiz_result(get_store(), configurable.user_id, grade)

    answered = state.get("answered", 0) + 1
    correct = state.get("correct", 0) + int(grade.is_correct)
    # Store the grade as a message so the quiz master's conversation stays append-only
    grade_message = HumanMessage(
        content=grade_message_template.format(
            is_correct=grade.is_correct,
            topic=grade.topic,
            feedback=grade.feedback,
            correct=correct,
            answered=answered,
        ),
        name="grader",
    )
    return Command(
        goto="quiz_master",
        update={"messages": [grade_message], "answered": answered, "correct": correct},
    )


def quiz_master(state: QuizState, config: RunnableConfig) -> Command[Literal["quiz_master_tools", "__end__"]]:
    """Ask the next question or react to the graded answer, calling tools when it needs the user's notes."""
    configurable = Configuration.from_runnable_config(config)
    model_config = {
        "model": configurable.quiz_model,
        "max_tokens": configurable.quiz_model_max_tokens,
    }
    model = configurable_model.bind_tools(QUIZ_TOOLS).with_config(model_config)

    # Keep the thread's first difficulty: changing the system prompt mid-conversation
    # invalidates the thinking blocks Claude returned on earlier turns
    difficulty = state.get("difficulty") or configurable.difficulty.value
    # Read long-term memory once per thread, for the same reason
    learner_history = state.get("learner_history") or load_learner_history(get_store(), configurable.user_id)
    system_prompt = quiz_master_system_prompt.format(difficulty=difficulty, learner_history=learner_history)
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    # If the model asked for tools, run them; otherwise its reply goes to the user
    update = {"messages": [response], "difficulty": difficulty, "learner_history": learner_history}
    if response.tool_calls:
        return Command(goto="quiz_master_tools", update=update)
    return Command(goto=END, update=update)


def quiz_master_tools(state: QuizState, config: RunnableConfig) -> Command[Literal["quiz_master", "__end__"]]:
    """Execute the tools the quiz master called and send the results back to it."""
    configurable = Configuration.from_runnable_config(config)
    most_recent_message = state["messages"][-1]
    tools_by_name = {tool.name: tool for tool in QUIZ_TOOLS}

    tool_outputs = [
        ToolMessage(
            content=execute_tool_safely(tools_by_name.get(tool_call["name"]), tool_call["args"], config),
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
        for tool_call in most_recent_message.tool_calls
    ]

    # Stop the loop if the model keeps calling tools without answering the user
    exceeded_iterations = count_tool_call_rounds(state["messages"]) >= configurable.max_react_tool_calls
    if exceeded_iterations:
        return Command(goto=END, update={"messages": tool_outputs})
    return Command(goto="quiz_master", update={"messages": tool_outputs})


quiz_agent_builder = StateGraph(QuizState, config_schema=Configuration)
quiz_agent_builder.add_node("grade_answer", grade_answer)
quiz_agent_builder.add_node("quiz_master", quiz_master)
quiz_agent_builder.add_node("quiz_master_tools", quiz_master_tools)
quiz_agent_builder.add_edge(START, "grade_answer")

quiz_agent = quiz_agent_builder.compile()
