"""Tests for reading the configuration from a run config."""

import pytest

from quiz_agent.configuration import Configuration


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_user_id_falls_back_to_default(blank):
    configurable = Configuration.from_runnable_config({"configurable": {"user_id": blank}})
    assert configurable.user_id == "default_user"


def test_user_id_is_read_from_run_config():
    configurable = Configuration.from_runnable_config({"configurable": {"user_id": "bob"}})
    assert configurable.user_id == "bob"
