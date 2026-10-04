"""
Sample data generator.

Creates `data/sensors.db` with a day of realistic readings, so this project
runs out of the box with no hardware and no other project needed.

The schema is identical to the ESP32 Environment Monitor, so once you have that
project running you can point this agent at its database instead:

    SENSOR_DB=../esp32-environment-monitor/data/sensors.db python app.py

Usage:
    python seed_data.py
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "sensors.db")

READINGS = 288          # one day at five-minute intervals
ANOMALY_CHANCE = 0.04   # a few temperature spikes, as the real sensor sees


def main():
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)          # start clean each time

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device      TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity    REAL NOT NULL,
            light       REAL,
            ts          TEXT NOT NULL
        )
        """
    )

    rng = random.Random(7)
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = []
    for i in range(READINGS):
        when = start + timedelta(minutes=5 * i)
        hour = when.hour

        # a gentle daily temperature curve, warmer in the afternoon
        base = 26 + 3 * (1 - abs(hour - 15) / 15)
        temperature = round(base + rng.uniform(-0.8, 0.8), 1)
        if rng.random() < ANOMALY_CHANCE:
            temperature = round(rng.uniform(45, 55), 1)     # the spike

        humidity = round(min(80, max(40, rng.gauss(60, 4))), 1)
        light = round(max(0, min(100, 50 + 45 * (1 - abs(hour - 13) / 13) + rng.uniform(-4, 4))), 1)

        rows.append(("esp32-01", temperature, humidity, light, when.strftime("%Y-%m-%d %H:%M:%S")))

    conn.executemany(
        "INSERT INTO readings (device, temperature, humidity, light, ts) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    spikes = conn.execute("SELECT COUNT(*) FROM readings WHERE temperature > 40").fetchone()[0]
    conn.close()

    print(f"Created {DB_PATH}")
    print(f"  {count} readings over the last 24 hours ({spikes} above 40 °C)")


if __name__ == "__main__":
    main()
