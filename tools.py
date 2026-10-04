"""
Data tools — the agent's hands.

Each function here answers one factual question about the stored sensor data.
The agent does not guess: it calls one of these and reports what came back.
Keeping them separate means they can be tested on their own, and reused from
anywhere (a script, the dashboard, a different agent).

Database location: the `SENSOR_DB` environment variable, defaulting to
`data/sensors.db` in this project. The schema matches the ESP32 Environment
Monitor, so you can point this at that project's database and it just works.
"""

import os
import sqlite3

DB_PATH = os.environ.get(
    "SENSOR_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sensors.db"),
)


def _connect() -> sqlite3.Connection:
    """Open the database read-only-ish, with rows returned as dictionaries."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"No sensor database at {DB_PATH}. "
            "Run `python seed_data.py` to create one with sample data."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def count_readings() -> int:
    """How many readings are stored in total."""
    conn = _connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    finally:
        conn.close()


def latest_reading() -> dict | None:
    """The most recent reading, or None if there is no data."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT device, temperature, humidity, light, ts "
            "FROM readings ORDER BY ts DESC, id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def summary_stats() -> dict:
    """Minimum, maximum and average for each measurement across all readings."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*)          AS readings,
                AVG(temperature)  AS temp_avg,
                MIN(temperature)  AS temp_min,
                MAX(temperature)  AS temp_max,
                AVG(humidity)     AS humidity_avg,
                AVG(light)        AS light_avg
            FROM readings
            """
        ).fetchone()
        if not row or row["readings"] == 0:
            return {}
        return {
            "readings": row["readings"],
            "temperature": {
                "average": round(row["temp_avg"], 1),
                "min": round(row["temp_min"], 1),
                "max": round(row["temp_max"], 1),
            },
            "humidity_average": round(row["humidity_avg"], 1),
            "light_average": round(row["light_avg"], 1),
        }
    finally:
        conn.close()


def recent_anomalies(threshold: float = 40.0, limit: int = 10) -> list[dict]:
    """Readings whose temperature is above `threshold`, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT device, temperature, humidity, light, ts FROM readings "
            "WHERE temperature > ? ORDER BY ts DESC LIMIT ?",
            (threshold, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def readings_since(hours: int = 24) -> list[dict]:
    """Readings from the last `hours` hours, oldest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT device, temperature, humidity, light, ts FROM readings "
            "WHERE ts >= datetime('now', ?) ORDER BY ts",
            (f"-{int(hours)} hours",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def device_list() -> list[str]:
    """The distinct devices that have reported readings."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT DISTINCT device FROM readings ORDER BY device").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


# --- The tool registry the LLM is given -------------------------------
# Descriptions matter: this is the only thing the model sees when deciding
# which tool to call, so they say precisely what each one answers.
TOOLS = [
    {
        "name": "latest_reading",
        "description": "Get the most recent sensor reading (temperature, humidity, light).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "summary_stats",
        "description": (
            "Get overall statistics: number of readings, and the average, "
            "minimum and maximum temperature, plus average humidity and light."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "recent_anomalies",
        "description": (
            "Find readings where the temperature was unusually high — the "
            "spikes. Use this for questions about anomalies, spikes, alerts "
            "or 'was it too hot'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "description": "Temperature in °C above which a reading counts as an anomaly. Default 40."},
                "limit": {"type": "integer", "description": "Maximum number of readings to return. Default 10."},
            },
            "required": [],
        },
    },
    {
        "name": "readings_since",
        "description": "Get all readings from the last N hours. Use for 'today', 'overnight', 'recently'.",
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
            },
            "required": [],
        },
    },
    {
        "name": "count_readings",
        "description": "Count how many readings are stored in total.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "device_list",
        "description": "List the devices that have reported readings.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

FUNCTIONS = {
    "latest_reading": latest_reading,
    "summary_stats": summary_stats,
    "recent_anomalies": recent_anomalies,
    "readings_since": readings_since,
    "count_readings": count_readings,
    "device_list": device_list,
}


def call_tool(name: str, arguments: dict | None = None):
    """Run a tool by name. Raises ValueError for an unknown tool."""
    if name not in FUNCTIONS:
        raise ValueError(f"Unknown tool: {name}")
    return FUNCTIONS[name](**(arguments or {}))
