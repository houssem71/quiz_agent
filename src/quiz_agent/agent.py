"""Main LangGraph implementation of the quiz agent."""

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from quiz_agent.state import QuizState


def echo(state: QuizState) -> dict:
    """Reply with the user's last message, to prove the graph runs end to end."""
    last_message = state["messages"][-1]
    return {"messages": [AIMessage(content=f"You said: {last_message.content}")]}


quiz_agent_builder = StateGraph(QuizState)
quiz_agent_builder.add_node("echo", echo)
quiz_agent_builder.add_edge(START, "echo")
quiz_agent_builder.add_edge("echo", END)

quiz_agent = quiz_agent_builder.compile()
