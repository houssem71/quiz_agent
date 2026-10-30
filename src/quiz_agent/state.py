"""Graph state definitions for the quiz agent."""

from langgraph.graph import MessagesState


class QuizState(MessagesState):
    """State shared by every node in the quiz graph.

    Inherits a `messages` list from MessagesState. New messages returned by a
    node are appended to it rather than replacing it.
    """
