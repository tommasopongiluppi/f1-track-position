# f1-track-position

## What the project does

This project asks whether Formula 1 teams give up race time to gain track position over a direct rival, and whether this depends on how hard overtaking is at a circuit. It uses lap and pit stop data from Grand Prix races in the 2023 to 2026 seasons, a tyre model that gives each car's time-optimal pit lap, and a two-car race simulator to compare real pit decisions with time-minimising and position-maximising strategies.

## What to install

Python 3.10 to 3.13 is required. From the repository root:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

TODO: confirm the Python version and the installation steps on Nuvolos.

## What to run, in order

Run every step from the repository root, with the virtual environment active. Open the notebooks with `jupyter lab` and run all cells from top to bottom.

1. `python code/01_get_data.py` downloads the raw data from the OpenF1 API (needs an internet connection). It can be stopped and started again at any time: tables that are already saved are skipped. OpenF1 refuses free requests while an F1 session is live (from 30 minutes before a session to 30 minutes after it); the script then stops with a message and can simply be run again after the session.
2. The cleaning notebooks, in this order:
   1. `code/02a_clean_laps.ipynb` builds one lap table and one pit-stop table from the raw files.
   2. `code/02b_race_situation.ipynb` adds the race situation of every lap (track status, weather, wet races), the pit loss of every race and the flags for clean laps and strategy stops.
   3. `code/02c_positions.ipynb` adds the race position and the gaps at the end of every lap, marks laps in traffic, builds the table of on-track overtakes, marks for every pit stop whether a rival was close, and checks the positions against OpenF1's own position data. It writes the final tables of this stage and the cleaning table.
3. `code/03_tyre_model.ipynb` sets up the tyre model: for every dry race the driver baselines and the lap-number effect (fuel burn and track evolution together), and for three example races the comparison of three Gaussian process kernels and the fitted tyre curves. Fitting the tyre curves of all races is still TODO.
4. `code/04_overtaking.ipynb` (TODO)
5. `code/05_simulator.ipynb` (TODO)
6. `code/06_tests.ipynb` (TODO)
7. `code/07_figures.ipynb` (TODO)

`code/helpers.py` holds the shared paths, constants and functions and is imported by the other files; it is not run on its own.

## How long it takes and what it produces

| Step | Time | Produces |
|------|------|----------|
| `01_get_data.py` | about 45 minutes the first time, a few seconds after that | raw data in `data/raw/` (about 50 MB): the race index `sessions.parquet`, ten tables per race in `data/raw/<year>/`, and `download_log.csv` |
| `02a_clean_laps.ipynb` | about 20 seconds | `laps_02a.parquet`, `stops_02a.parquet` and `cleaning_02a.csv` in `data/processed/`; `results/stint_change_exceptions.csv` |
| `02b_race_situation.ipynb` | about 5 seconds | `laps_02b.parquet`, `stops_02b.parquet`, `races.parquet` and `cleaning_02b.csv` in `data/processed/` |
| `02c_positions.ipynb` | about 15 seconds | `laps.parquet`, `pit_stops.parquet` and `overtakes.parquet` in `data/processed/`; `results/cleaning_table.csv` |
| `03_tyre_model.ipynb` | about 6 minutes | `results/lap_effect.csv` and `results/kernel_comparison.csv`; `lap_effect_by_race.png`, `kernel_comparison.png` and `tyre_curves_examples.png` in `figures/` (more TODO) |
| `04_overtaking.ipynb` | TODO | TODO |
| `05_simulator.ipynb` | TODO | TODO |
| `06_tests.ipynb` | TODO | TODO |
| `07_figures.ipynb` | TODO | figures in `figures/`, tables in `results/` |

## Where the data comes from

The data comes from the free OpenF1 API (https://openf1.org), which needs no login. The raw data is not included in this repository; `code/01_get_data.py` downloads it into `data/raw/`. See `data/README.md` for details and the licence statement.
