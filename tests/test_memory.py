"""Tests for the long-term memory helpers, using an in-memory store."""

from langgraph.store.memory import InMemoryStore

from quiz_agent.state import Grade
from quiz_agent.utils import NO_HISTORY, load_learner_history, save_quiz_result


def grade(topic: str, is_correct: bool) -> Grade:
    return Grade(is_answer=True, is_correct=is_correct, topic=topic, feedback="")


def test_results_on_the_same_topic_add_up():
    store = InMemoryStore()
    save_quiz_result(store, "alice", grade("Python lists", True))
    save_quiz_result(store, "alice", grade("python lists ", False))

    assert load_learner_history(store, "alice") == "- Python lists: 1/2 correct"


def test_history_lists_weakest_topics_first():
    store = InMemoryStore()
    save_quiz_result(store, "alice", grade("Python lists", True))
    save_quiz_result(store, "alice", grade("Python tuples", False))

    assert load_learner_history(store, "alice") == (
        "- Python tuples: 0/1 correct\n- Python lists: 1/1 correct"
    )


def test_users_do_not_share_memory():
    store = InMemoryStore()
    save_quiz_result(store, "alice", grade("Python lists", True))

    assert load_learner_history(store, "bob") == NO_HISTORY


def test_no_store_means_no_memory():
    save_quiz_result(None, "alice", grade("Python lists", True))

    assert load_learner_history(None, "alice") == NO_HISTORY
