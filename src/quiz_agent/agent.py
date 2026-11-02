"""Main LangGraph implementation of the quiz agent."""

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from quiz_agent.configuration import Configuration
from quiz_agent.prompts import quiz_master_system_prompt
from quiz_agent.state import QuizState

# Initialize a configurable model; the actual model is chosen per call from Configuration
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens"),
)


def quiz_master(state: QuizState, config: RunnableConfig) -> dict:
    """Ask the next question or grade the user's answer, based on the conversation so far."""
    configurable = Configuration.from_runnable_config(config)
    model_config = {
        "model": configurable.quiz_model,
        "max_tokens": configurable.quiz_model_max_tokens,
    }
    model = configurable_model.with_config(model_config)

    system_prompt = quiz_master_system_prompt.format(difficulty=configurable.difficulty.value)
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}


quiz_agent_builder = StateGraph(QuizState, config_schema=Configuration)
quiz_agent_builder.add_node("quiz_master", quiz_master)
quiz_agent_builder.add_edge(START, "quiz_master")
quiz_agent_builder.add_edge("quiz_master", END)

quiz_agent = quiz_agent_builder.compile()
