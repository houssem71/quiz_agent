"""Tools and helper functions for the quiz agent."""

from pathlib import Path

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool

NOTES_DIR = Path("notes")
ALLOWED_NOTE_SUFFIXES = {".md", ".txt"}
MAX_NOTES_CHARS = 20000


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
