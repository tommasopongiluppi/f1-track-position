# Data

The data comes from the free OpenF1 API (https://openf1.org). OpenF1 is an unofficial project and is not associated with Formula 1.

OpenF1 states no licence for redistribution, so the raw data is not included in this repository.

## How to get the data

Run this from the repository root, with an internet connection:

```
python code/01_get_data.py
```

It needs no login. The first run takes about 45 minutes, because the script waits 2 seconds between requests to stay inside the limits of the API (about 910 requests). The script can be stopped and started again: tables that are already saved are skipped, so a second run makes no requests and finishes in a few seconds. OpenF1 refuses free requests while an F1 session is live (from 30 minutes before a session to 30 minutes after it): the script then stops with a message saying so, the tables already saved are kept, and it can be run again after the session.

## What is downloaded

Grand Prix races only (no sprints) of the seasons 2023 to 2026 that started before 23 November 2026: 91 races (22 in 2023, 24 in 2024, 24 in 2025, 21 in 2026). Cancelled races are left out (2023 Imola, 2026 Bahrain at Sakhir, 2026 Saudi Arabia).

Everything is saved in `data/raw/` (about 50 MB):

- `sessions.parquet`: the index of the races (year, date, country, circuit, meeting_key, session_key).
- `cancelled_races.parquet`: the cancelled races that were left out of the index.
- `<year>/<session_key>_<endpoint>.parquet`: one file per race and endpoint. The ten endpoints are drivers, laps, stints, pit, intervals, position, race_control, weather, session_result and overtakes.
- `download_log.csv`: one line per request (time in UTC, session_key, endpoint, rows, status).

The raw files keep the values as OpenF1 delivers them. Dates stay as text, and columns that mix numbers and text (for example a gap of `12.3` or `+1 LAP`) are stored as text. The conversion happens in `code/02a_clean_laps.ipynb`.

The 2026 Bahrain Grand Prix was held at Sepang in Malaysia (circuit `Kuala Lumpur`, session_key 11731), but its country field still says Bahrain. Circuits must therefore be identified by the circuit column, not by the country.

## Known gaps

OpenF1 has no `pit` table for the first six races of 2023 (Bahrain, Saudi Arabia, Australia, Azerbaijan, Miami, Monaco). All other tables exist for all 91 races. The laps on which these cars stopped can still be read from the `stints` table.

## When the data was downloaded

The data used for the paper was downloaded on 26 November 2026 between 15:14 and 15:58 UTC. OpenF1 can correct its data later, so a new download may differ slightly. The script prints the first and last download time, taken from `download_log.csv`.

## Downloading again

- To download everything again, delete the folder `data/raw/`.
- `sessions.parquet` is reused once it is saved. After changing `SEASONS` or `CUTOFF_DATE` in `code/helpers.py`, delete `sessions.parquet` and `cancelled_races.parquet` so that the index is built again.
- A table that OpenF1 reported as empty is not requested again. To try those again, delete `download_log.csv`.
