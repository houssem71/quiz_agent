"""Streamlit quiz frontend for the quiz agent.

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
REPO_URL = "https://github.com/houssem71/quiz_agent"
STARTER_TOPICS = {
    "Python": "Quiz me on Python",
    "LangGraph": "Quiz me on LangGraph",
    "Cars": "Quiz me on cars",
    "Geography": "Quiz me on world geography",
    "My notes": "Quiz me on my notes",
}


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


def parse_grade(content: str) -> dict[str, str]:
    """Read the fields of a grader message ("correct: True", "score: 1/2", ...) into a dict."""
    body = content.strip().removeprefix("<grade>").removesuffix("</grade>")
    return dict(line.split(": ", 1) for line in body.strip().splitlines() if ": " in line)


def chat_history(messages: list[dict]) -> list[tuple[str, str, dict | None]]:
    """Turn the thread's messages into (role, text, grade) to display, hiding grader and tool messages.

    A grade is attached to the quiz master's reply that follows the grader message.
    """
    history = []
    pending_grade = None
    for message in messages:
        text = text_of(message.get("content", ""))
        if message["type"] == "human" and message.get("name") == "grader":
            pending_grade = parse_grade(text)
        elif message["type"] == "human":
            history.append(("user", text, None))
        elif message["type"] == "ai" and text:
            history.append(("assistant", text, pending_grade))
            pending_grade = None
    return history


def show_grade_badge(grade: dict | None) -> None:
    """Show a green or red verdict above a graded reply."""
    if grade is None:
        return
    if grade.get("correct") == "True":
        st.badge("Correct", color="green")
    else:
        st.badge("Not quite", color="red")


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


def accuracy(stats: dict) -> float:
    """Share of correct answers, between 0 and 1."""
    return stats["correct"] / stats["answered"] if stats["answered"] else 0.0


st.set_page_config(page_title="Quiz Agent", layout="centered")
client = get_client()

# Streamlit reruns this whole script on every interaction; session_state survives reruns
with st.sidebar:
    st.header("Quiz settings")
    user_id = st.text_input("Your name", value=DEFAULT_USER, help="Each name has its own long-term memory.").strip() or DEFAULT_USER
    difficulty = st.segmented_control(
        "Difficulty", ["easy", "medium", "hard"], default="medium", format_func=str.capitalize
    ) or "medium"
    st.caption("Name and difficulty apply when you start a new quiz.")
    if st.button("New quiz", type="primary", width="stretch"):
        st.session_state.pop("thread_id", None)

try:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = client.threads.create()["thread_id"]
    thread_id = st.session_state.thread_id
    # The server is the source of truth: rebuild the quiz from the thread's saved state
    values = client.threads.get_state(thread_id).get("values") or {}
    topics = [item["value"] for item in client.store.search_items([user_id, "quiz_results"], limit=20)["items"]]
except httpx.ConnectError:
    st.error(f"Can't reach the LangGraph server at {SERVER_URL}. Start it with `uv run python -m langgraph_cli dev`.")
    st.stop()

topics.sort(key=accuracy)
answered = values.get("answered", 0)
correct = values.get("correct", 0)

# The scoreboard lives in the sidebar so it stays visible while the conversation scrolls
with st.sidebar:
    st.divider()
    st.header("Current quiz")
    score_column, accuracy_column = st.columns(2)
    score_column.metric("Score", f"{correct}/{answered}")
    accuracy_column.metric("Accuracy", f"{correct / answered:.0%}" if answered else "–")
    st.caption(f"Difficulty: {(values.get('difficulty') or difficulty).capitalize()}")
    st.divider()
    st.header("Your progress")
    if not topics:
        st.caption("No quiz history yet. Answer a few questions to see your topics here.")
    for stats in topics:
        st.progress(accuracy(stats), text=f"{stats['topic']} · {stats['correct']}/{stats['answered']}")
    st.divider()
    st.caption(f"Built with LangGraph, Claude and Streamlit · [Source code]({REPO_URL})")

# Header and scoreboard
st.title("Quiz Agent")
st.markdown("Your AI study buddy: pick a topic, answer questions, and it remembers what you need to practise.")

# Quiz conversation
history = chat_history(values.get("messages", []))
starter_prompt = None
if not history:
    with st.container(border=True):
        st.subheader("Pick a topic to start")
        if topics:
            weakest = topics[0]["topic"]
            if st.button(f"Practise your weakest topic: {weakest}", type="primary", width="stretch"):
                starter_prompt = f"Quiz me on {weakest}"
        with st.container(horizontal=True):
            for label, message in STARTER_TOPICS.items():
                if st.button(label):
                    starter_prompt = message
        st.caption("Or type any topic below.")

for role, text, grade in history:
    with st.chat_message(role):
        show_grade_badge(grade)
        st.markdown(text)

prompt = st.chat_input("Type your answer, or a topic to study") or starter_prompt
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                st.write_stream(stream_reply(client, thread_id, prompt, {"user_id": user_id, "difficulty": difficulty}))
        except RuntimeError as error:
            st.error(f"The agent failed: {error}")
    # Rerun to refresh the score, grade badges and progress from the server
    st.rerun()
