"""Shared paths, constants and functions used by more than one stage.

Every stage imports from this file so that folders, seasons, the cutoff
date and the random seed are defined in exactly one place.
"""

from pathlib import Path

import pandas as pd

# Paths are built from this file's own location (code/helpers.py), so they
# work no matter which folder a script or notebook is started from.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
RESULTS = REPO_ROOT / "results"
FIGURES = REPO_ROOT / "figures"

# Seasons covered by the analysis (Grand Prix races only, no sprints).
SEASONS = [2023, 2024, 2025, 2026]

# Races starting before this date are included (2026 up to Las Vegas).
CUTOFF_DATE = "2026-11-23"

# One seed for every random step, so results can be reproduced.
RANDOM_SEED = 42

# OpenF1 API (free, no login) and the tables downloaded for every race.
API_URL = "https://api.openf1.org/v1"
ENDPOINTS = [
    "drivers",
    "laps",
    "stints",
    "pit",
    "intervals",
    "position",
    "race_control",
    "weather",
    "session_result",
    "overtakes",
]

# The columns that identify one car in one race, and one lap of that car.
KEY = ["session_key", "driver_number"]
LAP_KEY = KEY + ["lap_number"]


def load_races():
    """Return the race index saved by stage 1 (one row per race)."""
    return pd.read_parquet(DATA_RAW / "sessions.parquet")


def load_raw(endpoint, columns=None, number_columns=(), date_columns=()):
    """Combine one raw table over all races, converting the listed columns explicitly."""
    tables = []
    for race in load_races().itertuples():
        path = DATA_RAW / str(race.year) / f"{race.session_key}_{endpoint}.parquet"
        if not path.exists():
            continue  # OpenF1 has no pit table for six 2023 races
        table = pd.read_parquet(path, columns=columns)
        # The raw files keep values as delivered, so the same column can be
        # numbers in one race and text in another. Unexpected text stops the
        # run here instead of silently becoming a missing value.
        for column in number_columns:
            table[column] = pd.to_numeric(table[column])
        for column in date_columns:
            table[column] = pd.to_datetime(table[column], format="ISO8601", utc=True)
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def add_step(cleaning_steps, step, laps_before, laps_affected, action, reason):
    """Add one row to the cleaning table (a list with one dictionary per step)."""
    cleaning_steps.append(
        {"step": step, "laps_before": int(laps_before), "laps_affected": int(laps_affected),
         "action": action, "reason": reason}
    )


def scheduled_start_times(races):
    """Return the scheduled start time of every race, indexed by session_key."""
    return pd.to_datetime(races.set_index("session_key")["date"], format="ISO8601", utc=True)


def find_red_flags(race_control):
    """Return one row per red-flag period: from SESSION ABORTED to the next SESSION STARTED."""
    status = race_control[race_control["category"] == "SessionStatus"].sort_values(["session_key", "date"])
    periods = []
    for session_key, messages in status.groupby("session_key"):
        aborted_at = None
        for message in messages.itertuples():
            if message.message == "SESSION ABORTED":
                aborted_at = message.date
            elif message.message == "SESSION STARTED" and aborted_at is not None:
                periods.append({"session_key": session_key, "red_start": aborted_at, "red_end": message.date})
                aborted_at = None
    return pd.DataFrame(periods)
