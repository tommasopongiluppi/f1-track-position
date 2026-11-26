"""Shared paths, constants and functions used by more than one stage.

Every stage imports from this file so that folders, seasons, the cutoff
date and the random seed are defined in exactly one place.
"""

from pathlib import Path

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
