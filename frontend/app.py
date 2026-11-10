"""Streamlit chat frontend for the quiz agent.

The app never runs the agent or holds API keys: it talks to the LangGraph server
(`langgraph dev`) through its HTTP API, exactly like LangGraph Studio does.
"""

import httpx
import streamlit as st
from langgraph_sdk import get_sync_client

SERVER_URL = "http://127.0.0.1:2024"
GRAPH_NAME = "Quiz Agent"
# Only show tokens from the node that talks to the user, not the grader's JSON
CHAT_NODE = "quiz_master"
DEFAULT_USER = "default_user"


@st.cache_resource
def get_client():
    """Create the API client once and reuse it across Streamlit reruns."""
    # The local dev server needs no key, so don't send one
    return get_sync_client(url=SERVER_URL, api_key=None)


def text_of(content) -> str:
    """Extract the text from message content, which is a string or a list of content blocks (text, thinking, tool use)."""
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")


def chat_history(messages: list[dict]) -> list[tuple[str, str]]:
    """Turn the thread's messages into (role, text) pairs to display, hiding grader and tool messages."""
    history = []
    for message in messages:
        text = text_of(message.get("content", ""))
        if message["type"] == "human" and message.get("name") != "grader":
            history.append(("user", text))
        elif message["type"] == "ai" and text:
            history.append(("assistant", text))
    return history


def stream_reply(client, thread_id: str, user_message: str, configurable: dict):
    """Start a run on the thread and yield the quiz master's reply token by token."""
    for part in client.runs.stream(
        thread_id,
        GRAPH_NAME,
        input={"messages": [{"role": "user", "content": user_message}]},
        config={"configurable": configurable},
        stream_mode="messages-tuple",
    ):
        if part.event == "error":
            raise RuntimeError(part.data)
        if part.event != "messages":
            continue
        message_chunk, metadata = part.data
        if metadata.get("langgraph_node") == CHAT_NODE:
            yield text_of(message_chunk.get("content", ""))


st.set_page_config(page_title="Quiz Agent", page_icon="🎓")
st.title("🎓 Quiz Agent")
client = get_client()

# Streamlit reruns this whole script on every interaction; session_state survives reruns
with st.sidebar:
    user_id = st.text_input("User", value=DEFAULT_USER).strip() or DEFAULT_USER
    difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"], index=1)
    st.caption("User and difficulty apply when you start a new quiz.")
    if st.button("New quiz", use_container_width=True):
        st.session_state.pop("thread_id", None)

try:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = client.threads.create()["thread_id"]
    thread_id = st.session_state.thread_id
    # The server is the source of truth: rebuild the chat from the thread's saved state
    values = client.threads.get_state(thread_id).get("values") or {}
    topics = client.store.search_items([user_id, "quiz_results"], limit=20)["items"]
except httpx.ConnectError:
    st.error(f"Can't reach the LangGraph server at {SERVER_URL}. Start it with `uv run python -m langgraph_cli dev`.")
    st.stop()

with st.sidebar:
    st.metric("Score (this quiz)", f"{values.get('correct', 0)}/{values.get('answered', 0)}")
    st.subheader("Your topics (all quizzes)")
    if not topics:
        st.caption("No quiz history yet.")
    for item in sorted(topics, key=lambda item: item["value"]["correct"] / item["value"]["answered"]):
        stats = item["value"]
        st.write(f"{stats['topic']}: {stats['correct']}/{stats['answered']}")

for role, text in chat_history(values.get("messages", [])):
    with st.chat_message(role):
        st.markdown(text)

if prompt := st.chat_input("Your answer, or a topic to study"):
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            st.write_stream(stream_reply(client, thread_id, prompt, {"user_id": user_id, "difficulty": difficulty}))
        except RuntimeError as error:
            st.error(f"The agent failed: {error}")
    # Rerun to refresh the score, topics and history from the server
    st.rerun()
