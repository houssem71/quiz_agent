"""Main LangGraph implementation of the quiz agent."""

from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from quiz_agent.configuration import Configuration
from quiz_agent.prompts import quiz_master_system_prompt
from quiz_agent.state import QuizState
from quiz_agent.utils import QUIZ_TOOLS, count_tool_call_rounds, execute_tool_safely

# Initialize a configurable model; the actual model is chosen per call from Configuration
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens"),
)


def quiz_master(state: QuizState, config: RunnableConfig) -> Command[Literal["quiz_master_tools", "__end__"]]:
    """Ask the next question or grade the user's answer, calling tools when it needs the user's notes."""
    configurable = Configuration.from_runnable_config(config)
    model_config = {
        "model": configurable.quiz_model,
        "max_tokens": configurable.quiz_model_max_tokens,
    }
    model = configurable_model.bind_tools(QUIZ_TOOLS).with_config(model_config)

    # Keep the thread's first difficulty: changing the system prompt mid-conversation
    # invalidates the thinking blocks Claude returned on earlier turns
    difficulty = state.get("difficulty") or configurable.difficulty.value
    system_prompt = quiz_master_system_prompt.format(difficulty=difficulty)
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    # If the model asked for tools, run them; otherwise its reply goes to the user
    update = {"messages": [response], "difficulty": difficulty}
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
quiz_agent_builder.add_node("quiz_master", quiz_master)
quiz_agent_builder.add_node("quiz_master_tools", quiz_master_tools)
quiz_agent_builder.add_edge(START, "quiz_master")

quiz_agent = quiz_agent_builder.compile()
