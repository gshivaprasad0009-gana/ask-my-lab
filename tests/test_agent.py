"""
Tests for LabMind.

Covers the data tools, the tool registry, and the rules-mode agent — all
without a network connection or an API key.

Run from the project root:

    pytest -q
"""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent  # noqa: E402
import tools  # noqa: E402


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """Point the tools at a small, known database."""
    db = tmp_path / "sensors.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE readings (id INTEGER PRIMARY KEY AUTOINCREMENT, device TEXT,"
        " temperature REAL, humidity REAL, light REAL, ts TEXT)"
    )
    conn.executemany(
        "INSERT INTO readings (device, temperature, humidity, light, ts) VALUES (?,?,?,?,?)",
        [
            ("esp32-01", 26.0, 58.0, 50.0, "2026-10-03 09:00:00"),
            ("esp32-01", 27.5, 60.0, 55.0, "2026-10-03 10:00:00"),
            ("esp32-01", 52.0, 61.0, 57.0, "2026-10-03 11:00:00"),   # a spike
            ("esp32-01", 28.0, 59.0, 52.0, "2026-10-03 12:00:00"),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(tools, "DB_PATH", str(db))
    return db


# --- tools ------------------------------------------------------------

def test_count_readings(seeded):
    assert tools.count_readings() == 4


def test_latest_reading_returns_the_newest(seeded):
    latest = tools.latest_reading()
    assert latest["temperature"] == 28.0
    assert latest["ts"] == "2026-10-03 12:00:00"


def test_summary_stats(seeded):
    stats = tools.summary_stats()
    assert stats["readings"] == 4
    assert stats["temperature"]["max"] == 52.0
    assert stats["temperature"]["min"] == 26.0


def test_recent_anomalies_finds_the_spike(seeded):
    spikes = tools.recent_anomalies(threshold=40)
    assert len(spikes) == 1
    assert spikes[0]["temperature"] == 52.0


def test_device_list(seeded):
    assert tools.device_list() == ["esp32-01"]


def test_missing_database_raises_a_helpful_error(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "DB_PATH", str(tmp_path / "nope.db"))
    with pytest.raises(FileNotFoundError) as err:
        tools.count_readings()
    assert "seed_data.py" in str(err.value)


def test_call_tool_by_name(seeded):
    assert tools.call_tool("count_readings") == 4
    assert tools.call_tool("recent_anomalies", {"threshold": 40})[0]["temperature"] == 52.0


def test_call_tool_rejects_an_unknown_name(seeded):
    with pytest.raises(ValueError):
        tools.call_tool("delete_everything")


def test_every_registered_tool_is_callable(seeded):
    """The LLM is told about these tools — each one must actually exist."""
    for spec in tools.TOOLS:
        assert spec["name"] in tools.FUNCTIONS, f"{spec['name']} is advertised but missing"


# --- rules-mode agent -------------------------------------------------

@pytest.mark.parametrize("question,expected_tool", [
    ("What is the latest reading?", "latest_reading"),
    ("What is the average temperature?", "summary_stats"),
    ("Were there any spikes?", "recent_anomalies"),
    ("Any anomalies today?", "recent_anomalies"),
    ("How many readings are there?", "count_readings"),
    ("Which devices reported?", "device_list"),
    ("What happened in the last 6 hours?", "readings_since"),
])
def test_rules_mode_picks_the_right_tool(seeded, question, expected_tool):
    result = agent.ask_with_rules(question)
    assert result["tool"] == expected_tool
    assert result["mode"] == "rules"


def test_rules_mode_answers_with_real_numbers(seeded):
    result = agent.ask_with_rules("What is the average temperature?")
    assert "4 readings" in result["answer"]
    assert "52.0" in result["answer"]        # the real max, not invented


def test_rules_mode_finds_the_spike(seeded):
    result = agent.ask_with_rules("Were there any spikes?")
    assert "52.0" in result["answer"]


def test_unknown_question_gets_help_not_a_crash(seeded):
    result = agent.ask_with_rules("What is the meaning of life?")
    assert result["tool"] is None
    assert "I can answer questions" in result["answer"]


def test_readings_since_hours_argument_is_parsed(seeded):
    _, arguments = agent._pick_tool("What happened in the last 6 hours?")
    assert arguments == {"hours": 6}


def test_ask_falls_back_to_rules_without_configuration(seeded, monkeypatch):
    monkeypatch.setattr(agent, "LLM_BASE_URL", "")
    monkeypatch.setattr(agent, "LLM_API_KEY", "")
    result = agent.ask("How many readings are there?")
    assert result["mode"] == "rules"
    assert "4" in result["answer"]
