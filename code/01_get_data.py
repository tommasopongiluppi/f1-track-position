"""Stage 1: download the raw race data from the OpenF1 API into data/raw/.

Run from the repository root:

    python code/01_get_data.py

The script can be stopped and restarted at any time: tables that are already
saved are skipped. To download everything again, delete the data/raw/ folder.
"""

import csv
import time
from datetime import datetime, timezone

import pandas as pd
import pyarrow.parquet as pq
import requests

from helpers import API_URL, CUTOFF_DATE, DATA_PROCESSED, DATA_RAW, ENDPOINTS, SEASONS

SESSIONS_FILE = DATA_RAW / "sessions.parquet"
CANCELLED_FILE = DATA_RAW / "cancelled_races.parquet"
LOG_FILE = DATA_RAW / "download_log.csv"
LOG_COLUMNS = ["timestamp_utc", "session_key", "endpoint", "rows", "status"]

# OpenF1 allows 3 requests per second and 30 per minute without a login,
# so one request every 2 seconds stays inside both limits.
PAUSE_SECONDS = 2
TIMEOUT_SECONDS = 120
# Waits before the 2nd, 3rd, 4th and 5th attempt when the server is busy.
RETRY_WAITS = [5, 15, 45, 120]


def get_json(endpoint, params):
    """Request one table and return (rows, status); status is 'ok', 'empty' or 'error: ...'."""
    status = "error: not requested"
    for wait in RETRY_WAITS + [None]:
        time.sleep(PAUSE_SECONDS)
        try:
            response = requests.get(f"{API_URL}/{endpoint}", params=params, timeout=TIMEOUT_SECONDS)
            code = response.status_code
            if code == 200:
                rows = response.json()
                return rows, "ok" if len(rows) > 0 else "empty"
            # OpenF1 answers 404 "No results found" when it has no rows.
            if code == 404 and "No results found" in response.text:
                return [], "empty"
            status = f"error: HTTP {code}"
            if code != 429 and code < 500:
                return [], status  # a retry would give the same answer
            asked_wait = response.headers.get("Retry-After", "")
            if wait is not None and asked_wait.isdigit():
                wait = max(wait, int(asked_wait))
        except requests.RequestException as error:
            # Timeouts, lost connections and cut-off answers are worth a retry.
            status = f"error: {type(error).__name__}"
        if wait is not None:
            print(f"    {endpoint}: {status}, trying again in {wait} s")
            time.sleep(wait)
    return [], status


def append_log(session_key, endpoint, rows, status):
    """Add one line to the download log, writing the header first if the log is new."""
    is_new = not LOG_FILE.exists()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_FILE, "a", newline="") as file:
        writer = csv.writer(file)
        if is_new:
            writer.writerow(LOG_COLUMNS)
        writer.writerow([now, session_key, endpoint, rows, status])


def read_log():
    """Return the download log as a table (empty if nothing has been requested yet)."""
    if not LOG_FILE.exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(LOG_FILE)


def save_table(rows, path):
    """Save the rows of one table as a parquet file, with the values as delivered."""
    table = pd.DataFrame(rows)
    for column in table.columns:
        values = table[column].dropna()
        # Parquet needs one type per column. Columns that mix numbers and
        # text (for example a gap of 12.3 or "+1 LAP") are stored as text.
        if values.map(type).nunique() > 1:
            table[column] = table[column].map(lambda value: None if pd.isna(value) else str(value))
    # Write under a temporary name first, so that a run stopped half-way
    # never leaves a broken file that the next run would skip.
    temporary_path = path.with_suffix(".tmp")
    table.to_parquet(temporary_path, index=False)
    temporary_path.rename(path)


def list_races():
    """Return the index of Grand Prix races before the cutoff, downloading it if needed."""
    # The index is kept once saved; delete it after changing SEASONS or CUTOFF_DATE.
    if SESSIONS_FILE.exists() and CANCELLED_FILE.exists():
        return pd.read_parquet(SESSIONS_FILE)
    seasons = []
    for year in SEASONS:
        # session_name "Race" leaves out the sprints (their name is "Sprint").
        rows, status = get_json("sessions", {"year": year, "session_name": "Race"})
        append_log("", f"sessions_{year}", len(rows), status)
        if status != "ok":
            raise SystemExit(f"Could not list the {year} races ({status}). Run the script again later.")
        seasons.append(pd.DataFrame(rows))
    sessions = pd.concat(seasons, ignore_index=True)
    sessions = sessions.rename(
        columns={"date_start": "date", "country_name": "country", "circuit_short_name": "circuit"}
    )
    columns = ["year", "date", "country", "circuit", "meeting_key", "session_key"]
    is_before_cutoff = pd.to_datetime(sessions["date"]) < pd.Timestamp(CUTOFF_DATE, tz="UTC")
    is_cancelled = sessions["is_cancelled"].astype(bool)
    races = sessions.loc[is_before_cutoff & ~is_cancelled, columns].sort_values("date")
    cancelled = sessions.loc[is_before_cutoff & is_cancelled, columns].sort_values("date")
    cancelled.to_parquet(CANCELLED_FILE, index=False)
    races.to_parquet(SESSIONS_FILE, index=False)
    return races.reset_index(drop=True)


def table_path(race, endpoint):
    """Return the file path for one race and one endpoint."""
    return DATA_RAW / str(race.year) / f"{race.session_key}_{endpoint}.parquet"


def download_all(races):
    """Download every missing table of every race and return how many requests were made."""
    log = read_log()
    last_status = log.groupby(["session_key", "endpoint"])["status"].last().to_dict()
    requests_made = 0
    for number, race in enumerate(races.itertuples(), start=1):
        (DATA_RAW / str(race.year)).mkdir(exist_ok=True)
        notes = []
        for endpoint in ENDPOINTS:
            path = table_path(race, endpoint)
            # A table the API reported as empty is not asked for again;
            # delete download_log.csv to try those again.
            if path.exists() or last_status.get((race.session_key, endpoint)) == "empty":
                continue
            rows, status = get_json(endpoint, {"session_key": race.session_key})
            requests_made += 1
            if status == "ok":
                try:
                    save_table(rows, path)
                except Exception as error:
                    status = f"error: could not save ({type(error).__name__})"
            append_log(race.session_key, endpoint, len(rows), status)
            notes.append(f"{endpoint} {len(rows)}" if status == "ok" else f"{endpoint} {status}")
        if notes:
            print(f"[{number}/{len(races)}] {race.year} {race.country} ({race.circuit}): " + ", ".join(notes))
    return requests_made


def print_summary(races):
    """Print what is on disk: races and rows per season, gaps, and when it was downloaded."""
    log = read_log()
    log = log[log["session_key"].notna()]  # leave out the requests for the race lists
    last_status = log.groupby(["session_key", "endpoint"])["status"].last().to_dict()

    print("\nRaces per season")
    print(races.groupby("year").size().to_string())
    print(f"Total: {len(races)}")

    cancelled = pd.read_parquet(CANCELLED_FILE)
    print(f"\nCancelled races left out of the index: {len(cancelled)}")
    for race in cancelled.itertuples():
        print(f"  {race.year} {race.country} ({race.circuit}), session_key {race.session_key}")

    counts = []
    gaps = []
    for race in races.itertuples():
        for endpoint in ENDPOINTS:
            path = table_path(race, endpoint)
            if path.exists():
                rows = pq.read_metadata(path).num_rows
                counts.append({"year": race.year, "endpoint": endpoint, "rows": rows})
            else:
                status = last_status.get((race.session_key, endpoint), "not requested")
                gaps.append(f"  {race.year} {race.country} ({race.circuit}), session_key {race.session_key}: {endpoint}: {status}")

    if counts:
        counts = pd.DataFrame(counts)
        print("\nFiles per endpoint and season")
        print(counts.pivot_table(index="endpoint", columns="year", values="rows", aggfunc="count", fill_value=0).reindex(ENDPOINTS).to_string())
        print("\nRows per endpoint and season")
        print(counts.pivot_table(index="endpoint", columns="year", values="rows", aggfunc="sum", fill_value=0).reindex(ENDPOINTS).to_string())

    print(f"\nMissing or empty race and endpoint pairs: {len(gaps)}")
    for gap in gaps:
        print(gap)

    downloaded = log[log["status"] == "ok"]
    if len(downloaded) > 0:
        print(f"\nFirst table downloaded: {downloaded['timestamp_utc'].min()}")
        print(f"Last table downloaded:  {downloaded['timestamp_utc'].max()}")


def main():
    """Run the whole download and print the summary."""
    start = time.time()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    races = list_races()
    print(f"{len(races)} races in the index, {len(ENDPOINTS)} tables each.")
    requests_made = download_all(races)
    print_summary(races)
    minutes = (time.time() - start) / 60
    print(f"\nRequests made in this run: {requests_made}. Running time: {minutes:.1f} minutes.")


if __name__ == "__main__":
    main()
