"""Tools and helper functions for the quiz agent."""

from pathlib import Path

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.store.base import BaseStore

from quiz_agent.state import Grade

NOTES_DIR = Path("notes")
ALLOWED_NOTE_SUFFIXES = {".md", ".txt"}
MAX_NOTES_CHARS = 20000
MAX_HISTORY_TOPICS = 5
NO_HISTORY = "No quiz history yet."


##########################
# Notes Tools
##########################
@tool
def list_notes() -> str:
    """List the study notes files the user has saved.

    Call this first when the user wants to be quizzed on their own notes, to find which files exist.
    """
    if not NOTES_DIR.is_dir():
        return "No notes folder found."
    names = sorted(path.name for path in NOTES_DIR.iterdir() if path.suffix in ALLOWED_NOTE_SUFFIXES)
    return "\n".join(names) if names else "No notes files found."


@tool
def load_notes(filename: str) -> str:
    """Load one of the user's study notes files so you can quiz them on its content.

    Args:
        filename: Name of a file returned by list_notes, for example "python_basics.md".
    """
    path = (NOTES_DIR / filename).resolve()
    # Only allow notes files directly inside the notes folder
    if path.parent != NOTES_DIR.resolve() or path.suffix not in ALLOWED_NOTE_SUFFIXES:
        return f"Error: {filename} is not a notes file. Use list_notes to see the available files."
    if not path.is_file():
        return f"Error: {filename} was not found. Use list_notes to see the available files."
    return path.read_text(encoding="utf-8")[:MAX_NOTES_CHARS]


QUIZ_TOOLS: list[BaseTool] = [list_notes, load_notes]


##########################
# Tool Execution Helpers
##########################
def execute_tool_safely(tool: BaseTool | None, args: dict, config: RunnableConfig) -> str:
    """Run a tool and return its result, or an error message the model can read."""
    if tool is None:
        return "Error: unknown tool."
    try:
        return tool.invoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


def count_tool_call_rounds(messages: list[AnyMessage]) -> int:
    """Count the model's tool-calling replies since the user's last message."""
    rounds = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, AIMessage) and message.tool_calls:
            rounds += 1
    return rounds


##########################
# Grading Helpers
##########################
def get_last_question(messages: list[AnyMessage]) -> str | None:
    """Return the quiz master's last text reply before the user's latest message, or None on the first turn."""
    for message in reversed(messages[:-1]):
        if isinstance(message, AIMessage) and not message.tool_calls and message.text:
            return message.text
    return None


##########################
# Long-Term Memory Helpers
##########################
def quiz_results_namespace(user_id: str) -> tuple[str, ...]:
    """Store namespace for one user's quiz results; the user id comes first so users never share memory."""
    return (user_id, "quiz_results")


def save_quiz_result(store: BaseStore | None, user_id: str, grade: Grade) -> None:
    """Add a graded answer to the user's per-topic stats in the long-term store."""
    if store is None:
        return
    namespace = quiz_results_namespace(user_id)
    key = grade.topic.strip().lower()
    item = store.get(namespace, key)
    stats = item.value if item else {"topic": grade.topic, "answered": 0, "correct": 0}
    store.put(
        namespace,
        key,
        {
            "topic": stats["topic"],
            "answered": stats["answered"] + 1,
            "correct": stats["correct"] + int(grade.is_correct),
        },
    )


def load_learner_history(store: BaseStore | None, user_id: str) -> str:
    """Summarize the user's quiz results from the long-term store, weakest topics first."""
    if store is None:
        return NO_HISTORY
    items = store.search(quiz_results_namespace(user_id), limit=100)
    if not items:
        return NO_HISTORY
    stats = sorted((item.value for item in items), key=lambda s: s["correct"] / s["answered"])
    return "\n".join(
        f"- {s['topic']}: {s['correct']}/{s['answered']} correct" for s in stats[:MAX_HISTORY_TOPICS]
    )
