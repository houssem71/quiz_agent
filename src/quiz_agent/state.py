"""Graph state definitions and data structures for the quiz agent."""

from typing import NotRequired

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

###################
# Structured Outputs
###################

class Grade(BaseModel):
    """The grader's verdict on the user's latest message."""

    is_answer: bool = Field(
        description="True if the user's message is an attempt to answer the quiz question. False if they are choosing a topic, chatting or asking something.",
    )
    is_correct: bool = Field(
        description="True if the answer is correct. Always false when is_answer is false.",
    )
    topic: str = Field(
        description="Short name of the question's topic, for example 'Python lists'.",
    )
    feedback: str = Field(
        description="One sentence explaining why the answer is right or wrong.",
    )


###################
# State Definitions
###################

class QuizState(MessagesState):
    """State shared by every node in the quiz graph.

    Inherits a `messages` list from MessagesState. New messages returned by a
    node are appended to it rather than replacing it.
    """

    # Locked in on the thread's first turn so the system prompt never changes mid-conversation
    difficulty: NotRequired[str]
    # Score for the thread, updated by the grader after each answer
    answered: NotRequired[int]
    correct: NotRequired[int]
